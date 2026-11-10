"""Recommendations: intake, replacement proposals, and the human approval gate.

Submitting a plan (initial or replacement) only ever inserts a new PENDING
recommendation row and moves the incident's operational phase — it never
touches assignments or resource status. Dispatch happens exclusively in
`approve_recommendation`, behind `require_coordinator`, so no AI/n8n call can
dispatch anything on its own (INTEGRATION_CONTRACT.md: "Replanning can create
a pending replacement, never dispatch it automatically").

Every write path takes the same fixed lock order as assignment_service:
incident -> recommendation -> the incident's live assignments (by id) ->
resources (by id). Locking the incident row first is what serializes version
numbering, phase checks and approval for one incident; the partial unique
indexes (one PENDING recommendation per incident, one live assignment per
resource) are the database-level backstop if that were ever bypassed.

Versions are never overwritten: each plan is a new row with version
max+1, and earlier versions stay for audit (TEAM_INTEGRATION_PLAN.md D4).
`analysis_revision`, when supplied, is the idempotency key for submissions:
resending the same revision with the same plan replays the existing row.
"""

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.exceptions import (
    ConflictError,
    IdempotencyConflictError,
    InvalidResourcesError,
    NotFoundError,
    PendingPlanExistsError,
    ResourceNotAssignedError,
    ResourceUnavailableError,
    StaleRecommendationError,
)
from app.models.assignment import Assignment
from app.models.enums import AssignmentStatus, IncidentStatus, OperationalPhase, RecommendationState, ResourceStatus
from app.models.incident import Incident
from app.models.recommendation import Recommendation
from app.models.resource import Resource
from app.schemas.recommendation import (
    RecommendationApprove,
    RecommendationCreate,
    RecommendationProposeReplacement,
    RecommendationResponse,
)
from app.services import id_generator
from app.services.action_log_service import record_action
from app.services.operational_revision import bump_operational_revision
from app.services.assignment_service import (
    LIVE_ASSIGNMENT_STATUSES,
    TERMINAL_INCIDENT_STATUSES,
    lock_incident,
    lock_resources,
)
from app.services.state_machine import (
    ALLOWED_ASSIGNMENT_TRANSITIONS,
    ALLOWED_RESOURCE_TRANSITIONS,
    assert_phase_allows,
    assert_transition_allowed,
)


def to_response(recommendation: Recommendation) -> RecommendationResponse:
    return RecommendationResponse.model_validate(recommendation)


def _resources_label(resource_ids: list[str]) -> str:
    # Flat display string, same shape as the frontend mock's event metadata
    # (e.g. "AMB-05 + RESCUE-01").
    return " + ".join(resource_ids)


def get_current_recommendation(db: Session, incident_id: str) -> RecommendationResponse:
    recommendation = _current_recommendation(db, incident_id)
    if recommendation is None:
        raise NotFoundError(f"No recommendation exists for incident '{incident_id}'.")
    return to_response(recommendation)


def _current_recommendation(db: Session, incident_id: str) -> Recommendation | None:
    return (
        db.execute(
            select(Recommendation)
            .where(Recommendation.incident_id == incident_id)
            .order_by(Recommendation.version.desc())
            .limit(1)
        )
        .scalars()
        .first()
    )


def _lock_pending_recommendation(db: Session, incident_id: str) -> Recommendation:
    return (
        db.execute(
            select(Recommendation)
            .where(
                Recommendation.incident_id == incident_id,
                Recommendation.state == RecommendationState.PENDING,
            )
            .with_for_update()
        )
        .scalars()
        .first()
    )


def _lock_incident_for_planning(db: Session, incident_id: str) -> Incident:
    incident = lock_incident(db, incident_id)
    if incident.status in TERMINAL_INCIDENT_STATUSES:
        raise ConflictError(
            f"Incident '{incident.id}' is {incident.status.value}; cannot change its plan."
        )
    return incident


def _replay_if_resubmitted(
    db: Session,
    incident_id: str,
    analysis_revision: str | None,
    resource_ids: list[str],
    replacement_for: str | None,
) -> Recommendation | None:
    """Returns the recommendation an identical earlier submission created, so
    an n8n retry gets the same result instead of a conflict. Must run under
    the incident lock so it can't race the insert it's guarding."""
    if analysis_revision is None:
        return None
    existing = (
        db.execute(
            select(Recommendation)
            .where(
                Recommendation.incident_id == incident_id,
                Recommendation.analysis_revision == analysis_revision,
            )
            .order_by(Recommendation.version.desc())
            .limit(1)
        )
        .scalars()
        .first()
    )
    if existing is None:
        return None
    if existing.recommended_resources != resource_ids or existing.replacement_for_resource_id != replacement_for:
        raise IdempotencyConflictError(
            f"analysis_revision '{analysis_revision}' was already submitted for incident "
            f"'{incident_id}' with a different plan."
        )
    return existing


def _assert_resource_ids_valid(db: Session, resource_ids: list[str]) -> None:
    if len(set(resource_ids)) != len(resource_ids):
        raise InvalidResourcesError("recommended_resources must not contain duplicates.")
    found = set(db.scalars(select(Resource.id).where(Resource.id.in_(resource_ids))).all())
    missing = [rid for rid in resource_ids if rid not in found]
    if missing:
        raise NotFoundError(f"Resource(s) not found: {', '.join(missing)}.")


def _live_assignments(db: Session, incident_id: str, *, lock: bool) -> list[Assignment]:
    stmt = (
        select(Assignment)
        .where(
            Assignment.incident_id == incident_id,
            Assignment.status.in_(LIVE_ASSIGNMENT_STATUSES),
        )
        .order_by(Assignment.id)
    )
    if lock:
        stmt = stmt.with_for_update()
    return list(db.scalars(stmt).all())


def create_recommendation(
    db: Session, incident_id: str, payload: RecommendationCreate
) -> tuple[RecommendationResponse, bool]:
    """Persists the initial PENDING plan (version 1). Returns (plan, created);
    created is False when this was an idempotent replay."""
    try:
        incident = _lock_incident_for_planning(db, incident_id)

        replay = _replay_if_resubmitted(
            db, incident.id, payload.analysis_revision, payload.recommended_resources, None
        )
        if replay is not None:
            return to_response(replay), False

        current = _current_recommendation(db, incident.id)
        if current is not None:
            if current.state == RecommendationState.PENDING:
                raise PendingPlanExistsError(
                    f"Incident '{incident.id}' already has a pending plan (version {current.version})."
                )
            raise StaleRecommendationError(
                f"Incident '{incident.id}' already has a {current.state.value} plan (version "
                f"{current.version}); an initial plan can only be submitted once."
            )
        assert_phase_allows(incident.id, incident.operational_phase, "submit_recommendation")
        _assert_resource_ids_valid(db, payload.recommended_resources)

        recommendation = Recommendation(
            id=id_generator.next_recommendation_id(db),
            incident_id=incident.id,
            version=1,
            state=RecommendationState.PENDING,
            recommended_resources=payload.recommended_resources,
            reason=payload.reason,
            explanation=[item.model_dump() for item in payload.explanation],
            confidence=payload.confidence,
            priority_score=payload.priority_score,
            analysis_revision=payload.analysis_revision,
        )
        db.add(recommendation)
        db.flush()

        # The mock moves recommended -> awaiting_approval in two steps; both
        # happen together here, so both events are logged.
        incident.operational_phase = OperationalPhase.AWAITING_APPROVAL
        metadata = {"recommendation_id": recommendation.id, "version": recommendation.version}
        record_action(
            db,
            source="ai",
            action="recommendation_generated",
            incident_id=incident.id,
            metadata={"resources": _resources_label(payload.recommended_resources), **metadata},
        )
        record_action(db, source="ai", action="approval_requested", incident_id=incident.id, metadata=metadata)

        bump_operational_revision(db)

        db.commit()
        db.refresh(recommendation)
        return to_response(recommendation), True
    except IntegrityError:
        # Backstop: uq_recommendation_pending_incident caught a concurrent
        # second pending plan that got past the incident lock.
        db.rollback()
        raise PendingPlanExistsError(
            f"Incident '{incident_id}' already has a pending plan (created concurrently)."
        )
    except Exception:
        db.rollback()
        raise


def propose_replacement(
    db: Session, incident_id: str, payload: RecommendationProposeReplacement
) -> tuple[RecommendationResponse, bool]:
    """Persists a PENDING replacement plan (version max+1) for a blocked
    incident. Reserves and dispatches nothing — the failed resource stays
    dispatched until a coordinator approves the replacement. Returns
    (plan, created) like create_recommendation."""
    try:
        incident = _lock_incident_for_planning(db, incident_id)

        replay = _replay_if_resubmitted(
            db,
            incident.id,
            payload.analysis_revision,
            payload.recommended_resources,
            payload.replacement_for,
        )
        if replay is not None:
            return to_response(replay), False

        if payload.replacement_for in payload.recommended_resources:
            raise InvalidResourcesError(
                f"A replacement plan cannot include the resource it replaces ({payload.replacement_for})."
            )

        current = _current_recommendation(db, incident.id)
        if current is None:
            raise StaleRecommendationError(f"Incident '{incident.id}' has no approved plan to replace.")
        if current.state == RecommendationState.PENDING:
            raise PendingPlanExistsError(
                f"Incident '{incident.id}' already has a pending plan (version {current.version})."
            )
        if current.state != RecommendationState.APPROVED or current.version != payload.base_version:
            raise StaleRecommendationError(
                f"base_version {payload.base_version} is stale; the current plan is version "
                f"{current.version} ({current.state.value})."
            )
        assert_phase_allows(incident.id, incident.operational_phase, "propose_replacement")

        live = _live_assignments(db, incident.id, lock=False)
        replaced = next((a for a in live if a.resource_id == payload.replacement_for), None)
        if replaced is None:
            raise ResourceNotAssignedError(
                f"Resource '{payload.replacement_for}' has no live assignment on incident '{incident.id}'."
            )
        _assert_resource_ids_valid(db, payload.recommended_resources)

        recommendation = Recommendation(
            id=id_generator.next_recommendation_id(db),
            incident_id=incident.id,
            version=current.version + 1,
            state=RecommendationState.PENDING,
            recommended_resources=payload.recommended_resources,
            reason=payload.reason,
            explanation=[item.model_dump() for item in payload.explanation],
            confidence=payload.confidence,
            priority_score=payload.priority_score,
            replacement_for_resource_id=payload.replacement_for,
            replaced_assignment_id=replaced.id,
            analysis_revision=payload.analysis_revision,
        )
        db.add(recommendation)
        db.flush()

        # blocked -> replanning -> awaiting_replacement in one transaction;
        # "replanning" is never left persisted, only logged.
        incident.operational_phase = OperationalPhase.AWAITING_REPLACEMENT
        live_ids = {a.resource_id for a in live}
        newcomers = [rid for rid in payload.recommended_resources if rid not in live_ids]
        metadata = {"recommendation_id": recommendation.id, "version": recommendation.version}
        record_action(
            db,
            source="ai",
            action="replanning_started",
            incident_id=incident.id,
            resource_id=payload.replacement_for,
            assignment_id=replaced.id,
            metadata={"resources": payload.replacement_for},
        )
        record_action(
            db,
            source="ai",
            action="replacement_recommended",
            incident_id=incident.id,
            metadata={
                "resources": _resources_label(newcomers or payload.recommended_resources),
                "replaces": payload.replacement_for,
                **metadata,
            },
        )
        record_action(db, source="ai", action="approval_requested", incident_id=incident.id, metadata=metadata)

        bump_operational_revision(db)

        db.commit()
        db.refresh(recommendation)
        return to_response(recommendation), True
    except IntegrityError:
        db.rollback()
        raise PendingPlanExistsError(
            f"Incident '{incident_id}' already has a pending plan (created concurrently)."
        )
    except Exception:
        db.rollback()
        raise


def _dispatch(
    db: Session, incident: Incident, recommendation: Recommendation, resource: Resource, approved_by: str
) -> Assignment:
    assert_transition_allowed(
        "Resource", resource.status, ResourceStatus.DISPATCHED, ALLOWED_RESOURCE_TRANSITIONS
    )
    resource.status = ResourceStatus.DISPATCHED

    assignment = Assignment(
        id=id_generator.next_assignment_id(db),
        incident_id=incident.id,
        resource_id=resource.id,
        status=AssignmentStatus.ASSIGNED,
        decision_source="coordinator_approval",
        approved_by=approved_by,
        recommendation_id=recommendation.id,
    )
    db.add(assignment)
    db.flush()

    record_action(
        db,
        source="coordinator",
        action="resource_dispatched",
        incident_id=incident.id,
        resource_id=resource.id,
        assignment_id=assignment.id,
        metadata={"recommendation_id": recommendation.id, "approved_by": approved_by},
    )
    return assignment


def _approve_initial(
    db: Session, incident: Incident, recommendation: Recommendation, approved_by: str
) -> None:
    resources = lock_resources(db, recommendation.recommended_resources)
    unavailable = [r.id for r in resources if r.status != ResourceStatus.AVAILABLE]
    if unavailable:
        raise ResourceUnavailableError(f"Resource(s) not AVAILABLE: {', '.join(unavailable)}.")

    if incident.status == IncidentStatus.UNASSIGNED:
        incident.status = IncidentStatus.ASSIGNED

    record_action(
        db,
        source="coordinator",
        action="approved",
        incident_id=incident.id,
        metadata={
            "recommendation_id": recommendation.id,
            "version": recommendation.version,
            "resources": _resources_label(recommendation.recommended_resources),
        },
    )
    for resource in resources:
        _dispatch(db, incident, recommendation, resource, approved_by)


def _approve_replacement(
    db: Session, incident: Incident, recommendation: Recommendation, approved_by: str
) -> None:
    """Applies a replacement plan as a delta against the live assignments,
    per INTEGRATION_CONTRACT.md: release responders removed from the plan,
    keep continuing ones untouched (same assignment row, same
    recommendation_id), dispatch the newcomers."""
    plan = recommendation.recommended_resources
    live = _live_assignments(db, incident.id, lock=True)
    live_resource_ids = {a.resource_id for a in live}
    to_release = [a for a in live if a.resource_id not in plan]
    to_add = [rid for rid in plan if rid not in live_resource_ids]

    resources_by_id = {
        r.id: r for r in lock_resources(db, [a.resource_id for a in to_release] + to_add)
    }
    unavailable = [rid for rid in to_add if resources_by_id[rid].status != ResourceStatus.AVAILABLE]
    if unavailable:
        raise ResourceUnavailableError(f"Resource(s) not AVAILABLE: {', '.join(unavailable)}.")

    record_action(
        db,
        source="coordinator",
        action="replacement_approved",
        incident_id=incident.id,
        metadata={
            "recommendation_id": recommendation.id,
            "version": recommendation.version,
            "resources": _resources_label(plan),
        },
    )

    for assignment in to_release:
        assert_transition_allowed(
            "Assignment", assignment.status, AssignmentStatus.SUPERSEDED, ALLOWED_ASSIGNMENT_TRANSITIONS
        )
        assignment.status = AssignmentStatus.SUPERSEDED
        resource = resources_by_id[assignment.resource_id]
        if resource.status != ResourceStatus.AVAILABLE:
            assert_transition_allowed(
                "Resource", resource.status, ResourceStatus.AVAILABLE, ALLOWED_RESOURCE_TRANSITIONS
            )
            resource.status = ResourceStatus.AVAILABLE
        db.flush()
        record_action(
            db,
            source="coordinator",
            action="assignment_superseded",
            reason="replaced",
            incident_id=incident.id,
            resource_id=resource.id,
            assignment_id=assignment.id,
            metadata={
                "recommendation_id": recommendation.id,
                "replaced_by": _resources_label(to_add),
            },
        )

    for resource_id in to_add:
        _dispatch(db, incident, recommendation, resources_by_id[resource_id], approved_by)

    record_action(
        db,
        source="automation",
        action="redispatched",
        incident_id=incident.id,
        metadata={"recommendation_id": recommendation.id, "resources": _resources_label(plan)},
    )


def approve_recommendation(
    db: Session, incident_id: str, payload: RecommendationApprove, approved_by: str
) -> RecommendationResponse:
    try:
        incident = lock_incident(db, incident_id)
        if incident.status in TERMINAL_INCIDENT_STATUSES:
            raise ConflictError(
                f"Incident '{incident.id}' is {incident.status.value}; cannot approve a recommendation."
            )

        recommendation = _lock_pending_recommendation(db, incident_id)
        if recommendation is None:
            raise StaleRecommendationError(
                f"Incident '{incident_id}' has no pending recommendation to approve."
            )
        if recommendation.version != payload.version:
            raise StaleRecommendationError(
                f"Recommendation version {payload.version} is stale; the current pending "
                f"version is {recommendation.version}."
            )

        is_replacement = recommendation.replacement_for_resource_id is not None
        assert_phase_allows(
            incident.id,
            incident.operational_phase,
            "approve_replacement" if is_replacement else "approve_recommendation",
        )

        if is_replacement:
            _approve_replacement(db, incident, recommendation, approved_by)
        else:
            _approve_initial(db, incident, recommendation, approved_by)

        recommendation.state = RecommendationState.APPROVED
        recommendation.decided_by = approved_by
        recommendation.decided_at = func.now()
        incident.operational_phase = OperationalPhase.DISPATCHED

        bump_operational_revision(db)

        db.commit()
        db.refresh(recommendation)
        return to_response(recommendation)
    except IntegrityError:
        # Backstop: a race that got past the row locks above is caught by
        # the partial unique index and surfaced as a 409, not a raw 500.
        db.rollback()
        raise ConflictError(
            "One or more resources were assigned to another incident concurrently. Retry."
        )
    except Exception:
        db.rollback()
        raise
