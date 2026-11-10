from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.common_responses import CONFLICT, NOT_FOUND, responses
from app.api.deps import get_db, verify_any_api_key
from app.schemas.disruption import DisruptionReport
from app.schemas.incident import IncidentResponse
from app.services import disruption_service

router = APIRouter(
    prefix="/integration/v1/incidents",
    tags=["disruptions"],
    dependencies=[Depends(verify_any_api_key)],
)


@router.post(
    "/{incident_id}/disruptions",
    response_model=IncidentResponse,
    summary="Report that a dispatched responder is obstructed",
    description="Revises the responder's ETA (keeping the previous one) and moves the incident "
    "to `blocked`. The resource stays dispatched; replacing it requires proposing a replacement "
    "plan and a coordinator approving it.",
    responses=responses(NOT_FOUND, CONFLICT),
)
def report_disruption(
    incident_id: str, payload: DisruptionReport, db: Session = Depends(get_db)
) -> IncidentResponse:
    return disruption_service.report_disruption(db, incident_id, payload)
