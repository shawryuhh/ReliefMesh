from datetime import datetime

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.api.common_responses import NOT_FOUND, VALIDATION_FAILED, responses
from app.api.deps import get_db, verify_api_key
from app.schemas.action_log import ActionLogCreate, ActionLogResponse
from app.services import action_log_service

router = APIRouter(
    prefix="/activity-log", tags=["activity-log"], dependencies=[Depends(verify_api_key)]
)

# No PATCH/PUT/DELETE anywhere in this router, on purpose — the audit trail
# is append-only. State-changing endpoints elsewhere log their own entries
# automatically; this router only adds entries for things that don't map to
# one of those (e.g. an upstream duplicate merge) and lets you read history.


@router.post(
    "",
    response_model=ActionLogResponse,
    status_code=201,
    summary="Record an activity log entry",
    description="For events that don't map to a dedicated state-changing endpoint, e.g. a "
    "duplicate merge decided upstream by the AI service.",
    responses=responses(VALIDATION_FAILED),
)
def create_activity_log_entry(
    payload: ActionLogCreate, db: Session = Depends(get_db)
) -> ActionLogResponse:
    return action_log_service.create_manual_entry(db, payload)


@router.get(
    "",
    response_model=list[ActionLogResponse],
    summary="List activity log entries",
    description="Read-only audit trail, newest first. Supports filtering by entity/source/action "
    "and a `since` timestamp for incremental polling from n8n or the frontend.",
)
def list_activity_log(
    source: str | None = Query(default=None),
    action: str | None = Query(default=None),
    incident_id: str | None = Query(default=None),
    resource_id: str | None = Query(default=None),
    assignment_id: str | None = Query(default=None),
    since: datetime | None = Query(
        default=None, description="Only entries at or after this timestamp."
    ),
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
) -> list[ActionLogResponse]:
    return action_log_service.list_action_logs(
        db,
        source=source,
        action=action,
        incident_id=incident_id,
        resource_id=resource_id,
        assignment_id=assignment_id,
        since=since,
        limit=limit,
        offset=offset,
    )


@router.get(
    "/{log_id}",
    response_model=ActionLogResponse,
    summary="Get a single activity log entry",
    responses=responses(NOT_FOUND),
)
def get_activity_log_entry(log_id: int, db: Session = Depends(get_db)) -> ActionLogResponse:
    return action_log_service.get_action_log(db, log_id)
