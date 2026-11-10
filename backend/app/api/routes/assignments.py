from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.api.common_responses import CONFLICT, NOT_FOUND, VALIDATION_FAILED, responses
from app.api.deps import get_db, verify_api_key
from app.models.enums import AssignmentStatus
from app.schemas.assignment import AssignmentCreate, AssignmentResponse, AssignmentStatusUpdate
from app.services import assignment_service

router = APIRouter(prefix="/assignments", tags=["assignments"], dependencies=[Depends(verify_api_key)])


@router.post(
    "",
    response_model=list[AssignmentResponse],
    status_code=201,
    summary="Assign resources to an incident",
    description="Used after human/AI approval to atomically assign one or more AVAILABLE "
    "resources to an incident. All-or-nothing: if any requested resource isn't available, "
    "none are assigned.",
    responses=responses(NOT_FOUND, CONFLICT),
)
def create_assignment(
    payload: AssignmentCreate, db: Session = Depends(get_db)
) -> list[AssignmentResponse]:
    return assignment_service.create_assignment(db, payload)


@router.get(
    "",
    response_model=list[AssignmentResponse],
    summary="List assignments",
)
def list_assignments(
    incident_id: str | None = Query(default=None),
    resource_id: str | None = Query(default=None),
    status: AssignmentStatus | None = Query(default=None),
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
) -> list[AssignmentResponse]:
    return assignment_service.list_assignments(
        db,
        incident_id_filter=incident_id,
        resource_id_filter=resource_id,
        status_filter=status,
        limit=limit,
        offset=offset,
    )


@router.get(
    "/{assignment_id}",
    response_model=AssignmentResponse,
    summary="Get an assignment",
    responses=responses(NOT_FOUND),
)
def get_assignment(assignment_id: str, db: Session = Depends(get_db)) -> AssignmentResponse:
    return assignment_service.get_assignment(db, assignment_id)


@router.post(
    "/{assignment_id}/status",
    response_model=AssignmentResponse,
    summary="Transition an assignment's status",
    description="Valid targets: ACTIVE (resource arrived on scene), COMPLETED, CANCELLED. "
    "Frees or re-parks the resource as part of the same transaction. SUPERSEDED is only "
    "ever set by approving a replacement plan, never directly through this endpoint.",
    responses=responses(NOT_FOUND, CONFLICT, VALIDATION_FAILED),
)
def update_assignment_status(
    assignment_id: str, payload: AssignmentStatusUpdate, db: Session = Depends(get_db)
) -> AssignmentResponse:
    return assignment_service.update_assignment_status(db, assignment_id, payload)
