"""Shared helper for writing audit entries.

Every state-changing service function calls `record_action` as part of its
own transaction — logging is baked into the write path, not left as an
optional step for callers to remember. This function only adds to the
session; the caller's transaction commit persists it alongside the state
change it documents.
"""

from datetime import datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.exceptions import NotFoundError, ValidationFailedError
from app.models.action_log import ActionLog
from app.services.operational_revision import bump_operational_revision
from app.schemas.action_log import ActionLogCreate, ActionLogResponse


def record_action(
    db: Session,
    *,
    source: str,
    action: str,
    reason: str | None = None,
    result: str = "success",
    incident_id: str | None = None,
    resource_id: str | None = None,
    assignment_id: str | None = None,
    metadata: dict[str, Any] | None = None,
) -> ActionLog:
    log = ActionLog(
        source=source,
        action=action,
        reason=reason,
        result=result,
        incident_id=incident_id,
        resource_id=resource_id,
        assignment_id=assignment_id,
        log_metadata=metadata,
    )
    db.add(log)
    db.flush()
    return log


def to_response(log: ActionLog) -> ActionLogResponse:
    return ActionLogResponse.model_validate(log)


def get_action_log_or_404(db: Session, log_id: int) -> ActionLog:
    log = db.get(ActionLog, log_id)
    if log is None:
        raise NotFoundError(f"Activity log entry '{log_id}' not found.")
    return log


def get_action_log(db: Session, log_id: int) -> ActionLogResponse:
    return to_response(get_action_log_or_404(db, log_id))


def create_manual_entry(db: Session, payload: ActionLogCreate) -> ActionLogResponse:
    """Handles POST /activity-log — for events that don't map to a dedicated
    state-changing endpoint. Everything else in the system logs through
    `record_action` as part of its own transaction; this is the one place a
    log entry is committed on its own."""
    try:
        log = record_action(
            db,
            source=payload.source,
            action=payload.action,
            reason=payload.reason,
            result=payload.result or "success",
            incident_id=payload.incident_id,
            resource_id=payload.resource_id,
            assignment_id=payload.assignment_id,
            metadata=payload.metadata,
        )
        bump_operational_revision(db)
        db.commit()
        db.refresh(log)
        return to_response(log)
    except IntegrityError:
        db.rollback()
        raise ValidationFailedError(
            "incident_id, resource_id and assignment_id must refer to existing records, if provided."
        )
    except Exception:
        db.rollback()
        raise


def list_action_logs(
    db: Session,
    *,
    source: str | None = None,
    action: str | None = None,
    incident_id: str | None = None,
    resource_id: str | None = None,
    assignment_id: str | None = None,
    since: datetime | None = None,
    limit: int = 100,
    offset: int = 0,
) -> list[ActionLogResponse]:
    """Read-only, filterable view of the audit trail. There is deliberately no
    update/delete counterpart — action log entries are immutable once
    written; the only way to add to the history is `record_action` (internal)
    or `create_manual_entry` (POST /activity-log), and both only ever
    append."""
    stmt = select(ActionLog)
    if source is not None:
        stmt = stmt.where(ActionLog.source == source)
    if action is not None:
        stmt = stmt.where(ActionLog.action == action)
    if incident_id is not None:
        stmt = stmt.where(ActionLog.incident_id == incident_id)
    if resource_id is not None:
        stmt = stmt.where(ActionLog.resource_id == resource_id)
    if assignment_id is not None:
        stmt = stmt.where(ActionLog.assignment_id == assignment_id)
    if since is not None:
        stmt = stmt.where(ActionLog.timestamp >= since)
    stmt = stmt.order_by(ActionLog.timestamp.desc(), ActionLog.id.desc()).limit(limit).offset(offset)

    logs = db.scalars(stmt).all()
    return [to_response(log) for log in logs]
