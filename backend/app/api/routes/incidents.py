from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.api.common_responses import CONFLICT, NOT_FOUND, responses
from app.api.deps import get_db, verify_api_key
from app.models.enums import IncidentStatus
from app.schemas.incident import (
    IncidentActionRequest,
    IncidentCreate,
    IncidentResponse,
    IncidentUpdate,
)
from app.services import incident_service

router = APIRouter(prefix="/incidents", tags=["incidents"], dependencies=[Depends(verify_api_key)])


@router.post(
    "",
    response_model=IncidentResponse,
    status_code=201,
    summary="Create an incident",
    description="Used by ingestion/n8n to store an incident structured by the AI service.",
)
def create_incident(payload: IncidentCreate, db: Session = Depends(get_db)) -> IncidentResponse:
    return incident_service.create_incident(db, payload)


@router.get(
    "",
    response_model=list[IncidentResponse],
    summary="List incidents",
    description="Used by the frontend command center and by n8n to find incidents needing action.",
)
def list_incidents(
    status: IncidentStatus | None = Query(default=None),
    severity: str | None = Query(default=None),
    type: str | None = Query(default=None),
    min_priority: int | None = Query(default=None, ge=0, le=100),
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
) -> list[IncidentResponse]:
    return incident_service.list_incidents(
        db,
        status_filter=status,
        severity_filter=severity,
        type_filter=type,
        min_priority=min_priority,
        limit=limit,
        offset=offset,
    )


@router.get(
    "/{incident_id}",
    response_model=IncidentResponse,
    summary="Get an incident",
    responses=responses(NOT_FOUND),
)
def get_incident(incident_id: str, db: Session = Depends(get_db)) -> IncidentResponse:
    return incident_service.get_incident(db, incident_id)


@router.patch(
    "/{incident_id}",
    response_model=IncidentResponse,
    summary="Update incident fields",
    description="Partial update for fields such as severity, priority_score, confidence, needs. "
    "Status is not settable here — use /resolve or /cancel.",
    responses=responses(NOT_FOUND),
)
def update_incident(
    incident_id: str, payload: IncidentUpdate, db: Session = Depends(get_db)
) -> IncidentResponse:
    return incident_service.update_incident(db, incident_id, payload)


@router.post(
    "/{incident_id}/resolve",
    response_model=IncidentResponse,
    summary="Resolve an incident",
    description="Only valid when the incident is ACTIVE.",
    responses=responses(NOT_FOUND, CONFLICT),
)
def resolve_incident(
    incident_id: str, payload: IncidentActionRequest | None = None, db: Session = Depends(get_db)
) -> IncidentResponse:
    reason = payload.reason if payload else None
    return incident_service.resolve_incident(db, incident_id, reason)


@router.post(
    "/{incident_id}/cancel",
    response_model=IncidentResponse,
    summary="Cancel an incident",
    description="Valid from UNASSIGNED or ASSIGNED, e.g. for false alarms or duplicates.",
    responses=responses(NOT_FOUND, CONFLICT),
)
def cancel_incident(
    incident_id: str, payload: IncidentActionRequest | None = None, db: Session = Depends(get_db)
) -> IncidentResponse:
    reason = payload.reason if payload else None
    return incident_service.cancel_incident(db, incident_id, reason)
