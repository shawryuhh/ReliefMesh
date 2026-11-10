from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.exceptions import ConflictError, NotFoundError
from app.models.assignment import Assignment
from app.models.enums import AssignmentStatus, IncidentStatus, OperationalPhase, ResourceStatus
from app.models.incident import Incident
from app.models.resource import Resource
from app.services import id_generator
from app.services.operational_revision import bump_operational_revision
from app.services.action_log_service import record_action
from app.services.state_machine import ALLOWED_INCIDENT_TRANSITIONS, assert_transition_allowed
from app.schemas.assignment import AssignmentResponse
from app.schemas.incident import IncidentCreate, IncidentResponse, IncidentUpdate

LIVE_ASSIGNMENT_STATUSES = (AssignmentStatus.ASSIGNED, AssignmentStatus.ACTIVE)


def to_response(db: Session, incident: Incident) -> IncidentResponse:
    live_assignments = db.scalars(
        select(Assignment).where(
            Assignment.incident_id == incident.id,
            Assignment.status.in_(LIVE_ASSIGNMENT_STATUSES),
        )
    ).all()
    response = IncidentResponse.model_validate(incident)
    response.current_assignments = [
        AssignmentResponse.model_validate(a) for a in live_assignments
    ]
    return response


def get_incident_or_404(db: Session, incident_id: str) -> Incident:
    incident = db.get(Incident, incident_id)
    if incident is None:
        raise NotFoundError(f"Incident '{incident_id}' not found.")
    return incident


def create_incident(db: Session, payload: IncidentCreate) -> IncidentResponse:
    try:
        incident_id = id_generator.next_incident_id(db)
        incident = Incident(
            id=incident_id,
            location=payload.location,
            latitude=payload.latitude,
            longitude=payload.longitude,
            type=payload.type,
            severity=payload.severity,
            priority_score=payload.priority_score,
            confidence=payload.confidence,
            people_affected=payload.people_affected,
            needs=payload.needs,
            status=IncidentStatus.UNASSIGNED,
        )
        db.add(incident)
        db.flush()

        record_action(
            db,
            source="ingestion",
            action="incident_received",
            incident_id=incident.id,
            metadata=payload.report_metadata,
        )

        bump_operational_revision(db)
        db.commit()
        db.refresh(incident)
        return to_response(db, incident)
    except Exception:
        db.rollback()
        raise


def list_incidents(
    db: Session,
    status_filter: IncidentStatus | None = None,
    severity_filter: str | None = None,
    type_filter: str | None = None,
    min_priority: int | None = None,
    limit: int = 100,
    offset: int = 0,
) -> list[IncidentResponse]:
    stmt = select(Incident)
    if status_filter is not None:
        stmt = stmt.where(Incident.status == status_filter)
    if severity_filter is not None:
        stmt = stmt.where(Incident.severity == severity_filter)
    if type_filter is not None:
        stmt = stmt.where(Incident.type == type_filter)
    if min_priority is not None:
        stmt = stmt.where(Incident.priority_score >= min_priority)
    stmt = stmt.order_by(Incident.created_at.desc()).limit(limit).offset(offset)

    incidents = db.scalars(stmt).all()
    return [to_response(db, incident) for incident in incidents]


def get_incident(db: Session, incident_id: str) -> IncidentResponse:
    incident = get_incident_or_404(db, incident_id)
    return to_response(db, incident)


def update_incident(db: Session, incident_id: str, payload: IncidentUpdate) -> IncidentResponse:
    try:
        incident = get_incident_or_404(db, incident_id)

        updates = payload.model_dump(exclude_unset=True)
        for field, value in updates.items():
            setattr(incident, field, value)

        db.flush()
        record_action(
            db,
            source="human",
            action="incident_updated",
            incident_id=incident.id,
            metadata={"updated_fields": list(updates.keys())},
        )
        bump_operational_revision(db)
        db.commit()
        db.refresh(incident)
        return to_response(db, incident)
    except Exception:
        db.rollback()
        raise


def resolve_incident(db: Session, incident_id: str, reason: str | None) -> IncidentResponse:
    try:
        incident = db.scalars(
            select(Incident).where(Incident.id == incident_id).with_for_update()
        ).first()
        if incident is None:
            raise NotFoundError(f"Incident '{incident_id}' not found.")

        assert_transition_allowed(
            "Incident", incident.status, IncidentStatus.RESOLVED, ALLOWED_INCIDENT_TRANSITIONS
        )
        if incident.operational_phase in (
            OperationalPhase.AWAITING_APPROVAL,
            OperationalPhase.AWAITING_REPLACEMENT,
            OperationalPhase.BLOCKED,
            OperationalPhase.REPLANNING,
        ):
            raise ConflictError(
                f"Incident '{incident.id}' cannot be resolved while in phase '{incident.operational_phase.value}'.",
                code="STALE_PLAN",
            )

        live_assignments = list(
            db.scalars(
                select(Assignment)
                .where(
                    Assignment.incident_id == incident.id,
                    Assignment.status.in_(LIVE_ASSIGNMENT_STATUSES),
                )
                .order_by(Assignment.id)
                .with_for_update()
            ).all()
        )
        if live_assignments:
            resource_ids = sorted({a.resource_id for a in live_assignments})
            resources = {
                r.id: r
                for r in db.scalars(
                    select(Resource)
                    .where(Resource.id.in_(resource_ids))
                    .order_by(Resource.id)
                    .with_for_update()
                ).all()
            }
            for assignment in live_assignments:
                assignment.status = AssignmentStatus.COMPLETED
                assignment.completed_at = func.now()
                resource = resources.get(assignment.resource_id)
                if resource is not None and resource.status in (
                    ResourceStatus.DISPATCHED,
                    ResourceStatus.ACTIVE,
                ):
                    resource.status = ResourceStatus.AVAILABLE

        incident.status = IncidentStatus.RESOLVED
        incident.operational_phase = OperationalPhase.RESOLVED
        db.flush()

        record_action(
            db,
            source="coordinator",
            action="incident_resolved",
            reason=reason,
            incident_id=incident.id,
            metadata={"people": incident.people_affected or 0},
        )
        bump_operational_revision(db)
        db.commit()
        db.refresh(incident)
        return to_response(db, incident)
    except Exception:
        db.rollback()
        raise


def cancel_incident(db: Session, incident_id: str, reason: str | None) -> IncidentResponse:
    try:
        incident = get_incident_or_404(db, incident_id)
        assert_transition_allowed(
            "Incident", incident.status, IncidentStatus.CANCELLED, ALLOWED_INCIDENT_TRANSITIONS
        )
        incident.status = IncidentStatus.CANCELLED
        db.flush()

        record_action(
            db,
            source="human",
            action="incident_cancelled",
            reason=reason,
            incident_id=incident.id,
        )
        bump_operational_revision(db)
        db.commit()
        db.refresh(incident)
        return to_response(db, incident)
    except Exception:
        db.rollback()
        raise
