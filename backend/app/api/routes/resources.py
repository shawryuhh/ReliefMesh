from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.api.common_responses import CONFLICT, NOT_FOUND, VALIDATION_FAILED, responses
from app.api.deps import get_db, verify_api_key
from app.models.enums import ResourceStatus
from app.schemas.resource import ResourceCreate, ResourceResponse, ResourceStatusUpdate
from app.services import resource_service

router = APIRouter(prefix="/resources", tags=["resources"], dependencies=[Depends(verify_api_key)])


@router.post(
    "",
    response_model=ResourceResponse,
    status_code=201,
    summary="Register a resource",
    description="Used to seed/register ambulances, rescue units, shelters, etc. New resources start AVAILABLE.",
)
def create_resource(payload: ResourceCreate, db: Session = Depends(get_db)) -> ResourceResponse:
    return resource_service.create_resource(db, payload)


@router.get(
    "",
    response_model=list[ResourceResponse],
    summary="List resources",
    description="Used by the AI service and dashboard to find available resources for an incident.",
)
def list_resources(
    status: ResourceStatus | None = Query(default=None),
    type: str | None = Query(default=None),
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
) -> list[ResourceResponse]:
    return resource_service.list_resources(
        db,
        status_filter=status,
        type_filter=type,
        limit=limit,
        offset=offset,
    )


@router.get(
    "/{resource_id}",
    response_model=ResourceResponse,
    summary="Get a resource",
    responses=responses(NOT_FOUND),
)
def get_resource(resource_id: str, db: Session = Depends(get_db)) -> ResourceResponse:
    return resource_service.get_resource(db, resource_id)


@router.post(
    "/{resource_id}/status",
    response_model=ResourceResponse,
    summary="Change a resource's status",
    description="Direct status transition, e.g. marking a resource UNAVAILABLE for maintenance. "
    "Assignment creation/completion moves resource status automatically elsewhere.",
    responses=responses(NOT_FOUND, CONFLICT, VALIDATION_FAILED),
)
def update_resource_status(
    resource_id: str, payload: ResourceStatusUpdate, db: Session = Depends(get_db)
) -> ResourceResponse:
    return resource_service.update_resource_status(db, resource_id, payload)
