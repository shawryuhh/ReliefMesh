from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.exceptions import NotFoundError, ValidationFailedError
from app.models.enums import ResourceStatus
from app.models.resource import Resource
from app.services import id_generator
from app.services.action_log_service import record_action
from app.services.operational_revision import bump_operational_revision
from app.services.state_machine import ALLOWED_RESOURCE_TRANSITIONS, assert_transition_allowed
from app.schemas.resource import ResourceCreate, ResourceResponse, ResourceStatusUpdate


def _to_response(resource: Resource) -> ResourceResponse:
    return ResourceResponse.model_validate(resource)


def get_resource_or_404(db: Session, resource_id: str) -> Resource:
    resource = db.get(Resource, resource_id)
    if resource is None:
        raise NotFoundError(f"Resource '{resource_id}' not found.")
    return resource


def create_resource(db: Session, payload: ResourceCreate) -> ResourceResponse:
    try:
        resource_id = id_generator.next_resource_id(db, payload.type)
        resource = Resource(
            id=resource_id,
            type=payload.type,
            location=payload.location,
            latitude=payload.latitude,
            longitude=payload.longitude,
            capabilities=payload.capabilities,
            capacity=payload.capacity,
            status=ResourceStatus.AVAILABLE,
        )
        db.add(resource)
        db.flush()

        record_action(
            db,
            source="system",
            action="resource_registered",
            resource_id=resource.id,
        )

        bump_operational_revision(db)

        db.commit()
        db.refresh(resource)
        return _to_response(resource)
    except Exception:
        db.rollback()
        raise


def list_resources(
    db: Session,
    status_filter: ResourceStatus | None = None,
    type_filter: str | None = None,
    limit: int = 100,
    offset: int = 0,
) -> list[ResourceResponse]:
    stmt = select(Resource)
    if status_filter is not None:
        stmt = stmt.where(Resource.status == status_filter)
    if type_filter is not None:
        stmt = stmt.where(Resource.type == type_filter)
    stmt = stmt.order_by(Resource.created_at.desc()).limit(limit).offset(offset)

    resources = db.scalars(stmt).all()
    return [_to_response(r) for r in resources]


def get_resource(db: Session, resource_id: str) -> ResourceResponse:
    resource = get_resource_or_404(db, resource_id)
    return _to_response(resource)


def update_resource_status(
    db: Session, resource_id: str, payload: ResourceStatusUpdate
) -> ResourceResponse:
    if payload.resource_id != resource_id:
        raise ValidationFailedError(
            "resource_id in the request body does not match the URL path."
        )
    try:
        resource = get_resource_or_404(db, resource_id)
        assert_transition_allowed(
            "Resource", resource.status, payload.status, ALLOWED_RESOURCE_TRANSITIONS
        )
        resource.status = payload.status
        db.flush()

        record_action(
            db,
            source="human",
            action="resource_status_changed",
            reason=payload.reason,
            resource_id=resource.id,
            metadata={"new_status": payload.status.value},
        )
        bump_operational_revision(db)
        db.commit()
        db.refresh(resource)
        return _to_response(resource)
    except Exception:
        db.rollback()
        raise
