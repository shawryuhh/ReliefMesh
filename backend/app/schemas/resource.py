from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.core.domain_values import KNOWN_RESOURCE_TYPES
from app.models.enums import ResourceStatus


class ResourceCreate(BaseModel):
    type: str = Field(
        min_length=1,
        description=(
            "Resource type. Free-text and extensible — common demo values: "
            f"{KNOWN_RESOURCE_TYPES}."
        ),
        examples=["ambulance"],
    )
    location: str = Field(min_length=1)
    latitude: float | None = Field(default=None, ge=-90, le=90)
    longitude: float | None = Field(default=None, ge=-180, le=180)
    capabilities: list[str] = Field(default_factory=list)
    capacity: int | None = Field(default=None, ge=0)

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "type": "ambulance",
                "location": "Sector 12 Depot",
                "latitude": 12.9716,
                "longitude": 77.5946,
                "capabilities": ["medical"],
                "capacity": 2,
            }
        }
    )


class ResourceResponse(BaseModel):
    id: str
    type: str
    location: str
    latitude: float | None
    longitude: float | None
    capabilities: list[str]
    status: ResourceStatus
    capacity: int | None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ResourceStatusUpdate(BaseModel):
    resource_id: str
    status: ResourceStatus
    reason: str | None = None
