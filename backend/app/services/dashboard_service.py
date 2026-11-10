"""Frontend command-center aggregation.

Everything here is computed live from the incidents/resources/assignments/
action_logs tables — there is no separate dashboard table and nothing is
cached or precomputed, so this can never drift from the state the rest of
the API reports.
"""

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.action_log import ActionLog
from app.models.assignment import Assignment
from app.models.enums import AssignmentStatus, IncidentStatus, ResourceStatus, Severity
from app.models.incident import Incident
from app.models.resource import Resource
from app.schemas.action_log import ActionLogResponse
from app.schemas.dashboard import DashboardResponse, IncidentCounts, ResourceCounts
from app.schemas.resource import ResourceResponse
from app.services.incident_service import to_response as incident_to_response

TERMINAL_INCIDENT_STATUSES = (IncidentStatus.RESOLVED, IncidentStatus.CANCELLED)
LIVE_ASSIGNMENT_STATUSES = (AssignmentStatus.ASSIGNED, AssignmentStatus.ACTIVE)
# Severity, not a numeric priority_score cutoff — severity is the field
# ingestion/AI sets directly, so this doesn't invent a new threshold.
HIGH_PRIORITY_SEVERITIES = (Severity.HIGH, Severity.CRITICAL)


def _incident_counts(db: Session) -> IncidentCounts:
    status_rows = db.execute(
        select(Incident.status, func.count()).group_by(Incident.status)
    ).all()
    severity_rows = db.execute(
        select(Incident.severity, func.count()).group_by(Incident.severity)
    ).all()

    # Scoped to non-terminal incidents: a resolved/cancelled CRITICAL incident
    # no longer needs anyone's attention, so it shouldn't inflate these.
    critical_count = db.scalar(
        select(func.count())
        .select_from(Incident)
        .where(
            Incident.severity == Severity.CRITICAL,
            Incident.status.notin_(TERMINAL_INCIDENT_STATUSES),
        )
    )
    high_priority_count = db.scalar(
        select(func.count())
        .select_from(Incident)
        .where(
            Incident.severity.in_(HIGH_PRIORITY_SEVERITIES),
            Incident.status.notin_(TERMINAL_INCIDENT_STATUSES),
        )
    )

    return IncidentCounts(
        by_status={status.value: count for status, count in status_rows},
        by_severity={severity.value: count for severity, count in severity_rows},
        critical_count=critical_count or 0,
        high_priority_count=high_priority_count or 0,
    )


def _resource_counts(db: Session) -> ResourceCounts:
    status_rows = db.execute(
        select(Resource.status, func.count()).group_by(Resource.status)
    ).all()
    type_rows = db.execute(select(Resource.type, func.count()).group_by(Resource.type)).all()
    available_count = db.scalar(
        select(func.count())
        .select_from(Resource)
        .where(Resource.status == ResourceStatus.AVAILABLE)
    )

    return ResourceCounts(
        by_status={status.value: count for status, count in status_rows},
        by_type=dict(type_rows),
        available_count=available_count or 0,
    )


def get_dashboard(db: Session, activity_limit: int = 20) -> DashboardResponse:
    active_assignments_count = db.scalar(
        select(func.count())
        .select_from(Assignment)
        .where(Assignment.status.in_(LIVE_ASSIGNMENT_STATUSES))
    )

    recent_logs = db.scalars(
        select(ActionLog)
        .order_by(ActionLog.timestamp.desc(), ActionLog.id.desc())
        .limit(activity_limit)
    ).all()

    # "Current" incidents/resources means what needs attention right now —
    # resolved/cancelled incidents fall out of this list but stay queryable
    # via GET /incidents and the audit trail.
    current_incidents = db.scalars(
        select(Incident)
        .where(Incident.status.notin_(TERMINAL_INCIDENT_STATUSES))
        .order_by(Incident.created_at.desc())
    ).all()
    current_resources = db.scalars(select(Resource).order_by(Resource.created_at.desc())).all()

    return DashboardResponse(
        incident_counts=_incident_counts(db),
        resource_counts=_resource_counts(db),
        active_assignments_count=active_assignments_count or 0,
        recent_activity=[ActionLogResponse.model_validate(log) for log in recent_logs],
        current_incidents=[incident_to_response(db, incident) for incident in current_incidents],
        current_resources=[ResourceResponse.model_validate(r) for r in current_resources],
    )
