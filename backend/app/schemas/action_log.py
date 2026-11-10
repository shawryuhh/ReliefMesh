from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class ActionLogCreate(BaseModel):
    """Body for POST /activity-log — lets n8n/AI record events that don't map
    to a dedicated state-changing endpoint (e.g. a duplicate merge decided
    upstream, or a roadblock detection before replanning is triggered)."""

    source: str = Field(description='e.g. "ai", "n8n", "human", "system".')
    action: str = Field(description='e.g. "duplicate_merged", "ai_recommendation_received".')
    reason: str | None = None
    result: str | None = None
    incident_id: str | None = None
    resource_id: str | None = None
    assignment_id: str | None = None
    metadata: dict[str, Any] | None = None

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "source": "ai",
                "action": "duplicate_merged",
                "reason": "Two WhatsApp reports described the same flooding event",
                "incident_id": "INC-1042",
                "metadata": {"merged_report_ids": ["wa-8123", "wa-8124"]},
            }
        }
    )


class ActionLogResponse(BaseModel):
    id: int
    timestamp: datetime
    source: str
    action: str
    reason: str | None
    result: str | None
    incident_id: str | None
    resource_id: str | None
    assignment_id: str | None
    metadata: dict[str, Any] | None = Field(validation_alias="log_metadata")

    model_config = ConfigDict(from_attributes=True, populate_by_name=True)
