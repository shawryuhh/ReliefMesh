from pydantic import BaseModel

from app.schemas.action_log import ActionLogResponse
from app.schemas.incident import IncidentResponse
from app.schemas.resource import ResourceResponse


class IncidentCounts(BaseModel):
    by_status: dict[str, int]
    by_severity: dict[str, int]
    critical_count: int
    high_priority_count: int


class ResourceCounts(BaseModel):
    by_status: dict[str, int]
    by_type: dict[str, int]
    available_count: int


class DashboardResponse(BaseModel):
    incident_counts: IncidentCounts
    resource_counts: ResourceCounts
    active_assignments_count: int
    recent_activity: list[ActionLogResponse]
    current_incidents: list[IncidentResponse]
    current_resources: list[ResourceResponse]
