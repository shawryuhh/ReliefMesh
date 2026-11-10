"""Disruptions: n8n reporting that a dispatched responder is obstructed.

This only records the fact — the incident moves to the `blocked` phase and
the affected assignment's ETA is revised (keeping the previous value). The
obstructed resource stays DISPATCHED: releasing it is part of approving a
replacement plan (recommendation_service), never a side effect of the report
itself. The backend doesn't decide *that* a road is blocked or compute any
ETA; both arrive in the payload.
"""

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.exceptions import ConflictError, ResourceNotAssignedError
from app.models.assignment import Assignment
from app.models.enums import OperationalPhase
from app.schemas.disruption import DisruptionReport
from app.schemas.incident import IncidentResponse
from app.services.action_log_service import record_action
from app.services.operational_revision import bump_operational_revision
from app.services.assignment_service import LIVE_ASSIGNMENT_STATUSES, TERMINAL_INCIDENT_STATUSES, lock_incident
from app.services.incident_service import to_response as incident_to_response
from app.services.state_machine import assert_phase_allows


def report_disruption(db: Session, incident_id: str, payload: DisruptionReport) -> IncidentResponse:
    try:
        # Same lock order as everywhere else: incident, then assignment.
        incident = lock_incident(db, incident_id)
        if incident.status in TERMINAL_INCIDENT_STATUSES:
            raise ConflictError(
                f"Incident '{incident.id}' is {incident.status.value}; cannot report a disruption."
            )
        assert_phase_allows(incident.id, incident.operational_phase, "report_disruption")

        assignment = db.execute(
            select(Assignment)
            .where(
                Assignment.incident_id == incident.id,
                Assignment.resource_id == payload.resource_id,
                Assignment.status.in_(LIVE_ASSIGNMENT_STATUSES),
            )
            .with_for_update()
        ).scalar_one_or_none()
        if assignment is None:
            raise ResourceNotAssignedError(
                f"Resource '{payload.resource_id}' has no live assignment on incident '{incident.id}'."
            )

        previous_eta = (
            assignment.eta_minutes if assignment.eta_minutes is not None else payload.previous_eta_minutes
        )
        assignment.previous_eta_minutes = previous_eta
        assignment.eta_minutes = payload.eta_minutes
        incident.operational_phase = OperationalPhase.BLOCKED
        db.flush()

        # Flat metadata in the shape the frontend's route-disruption UI reads
        # ({resources, old, eta}).
        metadata: dict[str, str | int] = {"resources": payload.resource_id, "eta": payload.eta_minutes}
        if previous_eta is not None:
            metadata["old"] = previous_eta
        record_action(
            db,
            source="automation",
            action="road_block_detected",
            reason=payload.reason,
            incident_id=incident.id,
            resource_id=payload.resource_id,
            assignment_id=assignment.id,
            metadata=metadata,
        )

        bump_operational_revision(db)

        db.commit()
        db.refresh(incident)
        return incident_to_response(db, incident)
    except Exception:
        db.rollback()
        raise
