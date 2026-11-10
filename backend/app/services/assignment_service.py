"""Assignment creation and lifecycle.

This is the concurrency-sensitive core of the backend: turning an
approved resource plan into real assignments must never let two requests
hand the same resource to two incidents. Safety here is layered, not relied
on from a single mechanism:

1. `SELECT ... FOR UPDATE` on the target incident, the authorizing
   recommendation and the resources, taken in a fixed order (incident,
   then recommendation, then resources sorted by id), so concurrent
   requests serialize instead of deadlocking each other.
2. Re-checking resource status *after* the lock is held, before writing
   anything.
3. The partial unique index on `assignments(resource_id) WHERE status IN
   (...)` (see the initial migration) as a database-level backstop that
   holds even if the above were ever bypassed — caught here and turned into
   a 409 instead of a raw 500.

All writes for one call (incident status, resource status(es), assignment
row(s), action log entries) happen in a single transaction: either all of it
commits, or none of it does.

POST /assignments is *not* a first-dispatch gate (Phase 4): every call must
reference the incident's current APPROVED recommendation, and every
requested resource must belong to it — an arbitrary decision_source like
"ai" no longer authorizes anything by itself. Real dispatch happens as part
of approving a recommendation (recommendation_service.approve_recommendation
creates the assignments directly, in the same transaction as the approval).
This endpoint's remaining role is a compatibility one — confirming/creating
an assignment for a resource that's genuinely part of an already-approved
plan, idempotently returning the existing live assignment for a pair that's
already been dispatched, per INTEGRATION_CONTRACT.md's createAssignment.
"""

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.exceptions import (
    ApprovalRequiredError,
    ConflictError,
    NotFoundError,
    ResourceUnavailableError,
    StaleRecommendationError,
    ValidationFailedError,
)
from app.models.assignment import Assignment
from app.models.enums import AssignmentStatus, IncidentStatus, RecommendationState, ResourceStatus
from app.models.incident import Incident
from app.models.recommendation import Recommendation
from app.models.resource import Resource
from app.schemas.assignment import AssignmentCreate, AssignmentResponse, AssignmentStatusUpdate
from app.services import id_generator
from app.services.action_log_service import record_action
from app.services.operational_revision import bump_operational_revision
from app.services.state_machine import (
    ALLOWED_ASSIGNMENT_TRANSITIONS,
    ALLOWED_RESOURCE_TRANSITIONS,
    assert_transition_allowed,
)

LIVE_ASSIGNMENT_STATUSES = (AssignmentStatus.ASSIGNED, AssignmentStatus.ACTIVE)
TERMINAL_INCIDENT_STATUSES = (IncidentStatus.RESOLVED, IncidentStatus.CANCELLED)

# Resource status a resource should land in when an assignment moves to each
# of these statuses. SUPERSEDED is deliberately absent: it's only ever set by
# replacement approval (recommendation_service), which handles the resource
# hand-off itself.
_RESOURCE_STATUS_FOR_ASSIGNMENT_STATUS = {
    AssignmentStatus.ACTIVE: ResourceStatus.ACTIVE,
    AssignmentStatus.COMPLETED: ResourceStatus.AVAILABLE,
    AssignmentStatus.CANCELLED: ResourceStatus.AVAILABLE,
}


def to_response(assignment: Assignment) -> AssignmentResponse:
    return AssignmentResponse.model_validate(assignment)


def get_assignment_or_404(db: Session, assignment_id: str) -> Assignment:
    assignment = db.get(Assignment, assignment_id)
    if assignment is None:
        raise NotFoundError(f"Assignment '{assignment_id}' not found.")
    return assignment


def lock_incident(db: Session, incident_id: str) -> Incident:
    incident = db.execute(
        select(Incident).where(Incident.id == incident_id).with_for_update()
    ).scalar_one_or_none()
    if incident is None:
        raise NotFoundError(f"Incident '{incident_id}' not found.")
    return incident


def lock_resources(db: Session, resource_ids: list[str]) -> list[Resource]:
    # Sorted so any two requests touching overlapping resource sets always
    # acquire row locks in the same order and can't deadlock each other.
    unique_ids = sorted(set(resource_ids))
    resources = (
        db.execute(
            select(Resource)
            .where(Resource.id.in_(unique_ids))
            .order_by(Resource.id)
            .with_for_update()
        )
        .scalars()
        .all()
    )

    found_ids = {r.id for r in resources}
    missing = [rid for rid in unique_ids if rid not in found_ids]
    if missing:
        raise NotFoundError(f"Resource(s) not found: {', '.join(missing)}.")
    return resources


def _lock_authorizing_recommendation(db: Session, incident_id: str, recommendation_id: str) -> Recommendation:
    recommendation = db.execute(
        select(Recommendation).where(Recommendation.id == recommendation_id).with_for_update()
    ).scalar_one_or_none()
    if recommendation is None:
        raise NotFoundError(f"Recommendation '{recommendation_id}' not found.")
    if recommendation.incident_id != incident_id:
        raise ApprovalRequiredError(
            f"Recommendation '{recommendation_id}' does not belong to incident '{incident_id}'."
        )

    current_version = db.execute(
        select(func.max(Recommendation.version)).where(Recommendation.incident_id == incident_id)
    ).scalar_one()
    if recommendation.version != current_version:
        raise StaleRecommendationError(
            f"Recommendation '{recommendation_id}' (version {recommendation.version}) is no "
            f"longer current for incident '{incident_id}'; version {current_version} is."
        )

    if recommendation.state != RecommendationState.APPROVED:
        raise ApprovalRequiredError(
            f"Recommendation '{recommendation_id}' is {recommendation.state.value}, not approved; "
            "dispatch requires an approved recommendation."
        )
    return recommendation


def create_assignment(db: Session, payload: AssignmentCreate) -> list[AssignmentResponse]:
    try:
        incident = lock_incident(db, payload.incident_id)
        if incident.status in TERMINAL_INCIDENT_STATUSES:
            raise ConflictError(
                f"Incident '{incident.id}' is {incident.status.value}; cannot assign resources."
            )

        recommendation = _lock_authorizing_recommendation(db, incident.id, payload.recommendation_id)
        not_approved = [
            rid for rid in payload.resource_ids if rid not in recommendation.recommended_resources
        ]
        if not_approved:
            raise ApprovalRequiredError(
                f"Resource(s) not part of approved recommendation '{recommendation.id}': "
                f"{', '.join(not_approved)}."
            )

        resources = lock_resources(db, payload.resource_ids)

        # Idempotent per INTEGRATION_CONTRACT.md's createAssignment: a
        # resource that already has a live assignment for *this* incident
        # (most commonly because approving the recommendation already
        # dispatched it) is returned as-is, not re-created or rejected as
        # unavailable.
        existing_live_by_resource = {
            a.resource_id: a
            for a in db.execute(
                select(Assignment).where(
                    Assignment.incident_id == incident.id,
                    Assignment.resource_id.in_([r.id for r in resources]),
                    Assignment.status.in_(LIVE_ASSIGNMENT_STATUSES),
                )
            ).scalars()
        }

        to_create = [r for r in resources if r.id not in existing_live_by_resource]
        unavailable = [r.id for r in to_create if r.status != ResourceStatus.AVAILABLE]
        if unavailable:
            raise ResourceUnavailableError(
                f"Resource(s) not AVAILABLE: {', '.join(unavailable)}."
            )

        # UNASSIGNED -> ASSIGNED on first resource; already-ASSIGNED/ACTIVE
        # incidents just gain another live assignment with no status change.
        if to_create and incident.status == IncidentStatus.UNASSIGNED:
            incident.status = IncidentStatus.ASSIGNED

        if payload.ai_recommendation is not None:
            record_action(
                db,
                source="ai",
                action="ai_recommendation_received",
                incident_id=incident.id,
                metadata=payload.ai_recommendation.model_dump(),
            )

        created: list[Assignment] = []
        for resource in to_create:
            assert_transition_allowed(
                "Resource", resource.status, ResourceStatus.DISPATCHED, ALLOWED_RESOURCE_TRANSITIONS
            )
            resource.status = ResourceStatus.DISPATCHED

            assignment = Assignment(
                id=id_generator.next_assignment_id(db),
                incident_id=incident.id,
                resource_id=resource.id,
                status=AssignmentStatus.ASSIGNED,
                decision_source=payload.decision_source,
                approved_by=recommendation.decided_by,
                recommendation_id=recommendation.id,
            )
            db.add(assignment)
            db.flush()
            created.append(assignment)

            record_action(
                db,
                source=payload.decision_source,
                action="assignment_created",
                reason=payload.reason,
                incident_id=incident.id,
                resource_id=resource.id,
                assignment_id=assignment.id,
                metadata={"approved_by": recommendation.decided_by, "recommendation_id": recommendation.id},
            )

        bump_operational_revision(db)

        db.commit()
        result_assignments = [*existing_live_by_resource.values(), *created]
        for assignment in result_assignments:
            db.refresh(assignment)
        return [to_response(assignment) for assignment in result_assignments]
    except IntegrityError:
        # Backstop: the partial unique index caught a race that somehow got
        # past the row locks above (e.g. a concurrent writer outside this
        # code path). Surface it as a normal conflict, not a 500.
        db.rollback()
        raise ConflictError(
            "One or more resources were assigned to another incident concurrently. Retry."
        )
    except Exception:
        db.rollback()
        raise


def list_assignments(
    db: Session,
    incident_id_filter: str | None = None,
    resource_id_filter: str | None = None,
    status_filter: AssignmentStatus | None = None,
    limit: int = 100,
    offset: int = 0,
) -> list[AssignmentResponse]:
    stmt = select(Assignment)
    if incident_id_filter is not None:
        stmt = stmt.where(Assignment.incident_id == incident_id_filter)
    if resource_id_filter is not None:
        stmt = stmt.where(Assignment.resource_id == resource_id_filter)
    if status_filter is not None:
        stmt = stmt.where(Assignment.status == status_filter)
    stmt = stmt.order_by(Assignment.created_at.desc()).limit(limit).offset(offset)

    assignments = db.scalars(stmt).all()
    return [to_response(a) for a in assignments]


def get_assignment(db: Session, assignment_id: str) -> AssignmentResponse:
    assignment = get_assignment_or_404(db, assignment_id)
    return to_response(assignment)


def update_assignment_status(
    db: Session, assignment_id: str, payload: AssignmentStatusUpdate
) -> AssignmentResponse:
    if payload.status == AssignmentStatus.SUPERSEDED:
        raise ValidationFailedError(
            "SUPERSEDED is only set by approving a replacement plan, not directly."
        )

    try:
        assignment = db.execute(
            select(Assignment).where(Assignment.id == assignment_id).with_for_update()
        ).scalar_one_or_none()
        if assignment is None:
            raise NotFoundError(f"Assignment '{assignment_id}' not found.")

        assert_transition_allowed(
            "Assignment", assignment.status, payload.status, ALLOWED_ASSIGNMENT_TRANSITIONS
        )

        resource = db.execute(
            select(Resource).where(Resource.id == assignment.resource_id).with_for_update()
        ).scalar_one_or_none()
        if resource is None:
            raise NotFoundError(f"Resource '{assignment.resource_id}' not found.")

        resource_target = _RESOURCE_STATUS_FOR_ASSIGNMENT_STATUS[payload.status]
        if resource.status != resource_target:
            assert_transition_allowed(
                "Resource", resource.status, resource_target, ALLOWED_RESOURCE_TRANSITIONS
            )
            resource.status = resource_target

        assignment.status = payload.status
        if payload.status in (AssignmentStatus.COMPLETED, AssignmentStatus.CANCELLED):
            assignment.completed_at = func.now()

        db.flush()
        record_action(
            db,
            source="human",
            action="assignment_status_changed",
            reason=payload.reason,
            incident_id=assignment.incident_id,
            resource_id=assignment.resource_id,
            assignment_id=assignment.id,
            metadata={"new_status": payload.status.value},
        )
        bump_operational_revision(db)
        db.commit()
        db.refresh(assignment)
        return to_response(assignment)
    except Exception:
        db.rollback()
        raise
