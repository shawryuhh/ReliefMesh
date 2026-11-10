from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.models.enums import AssignmentStatus
from app.schemas.ai import AIRecommendation


class AssignmentCreate(BaseModel):
    incident_id: str
    resource_ids: list[str] = Field(
        min_length=1,
        description="One or more resources to assign to the incident in a single atomic operation.",
    )
    recommendation_id: str = Field(
        description="The incident's current APPROVED recommendation authorizing this dispatch. "
        "Every requested resource must be a member of its recommended_resources — this is the "
        "human approval gate; there is no direct-dispatch path that skips it (Phase 4)."
    )
    decision_source: str = Field(
        description='Who/what triggered this call, e.g. "ai", "human", "n8n" — descriptive only, '
        "not itself an authorization; approved_by is always derived from the recommendation."
    )
    approved_by: str | None = Field(
        default=None,
        description="Ignored. approved_by is always overwritten server-side from the "
        "recommendation's own decided_by — never trusted from the request body.",
    )
    reason: str | None = None
    ai_recommendation: AIRecommendation | None = Field(
        default=None,
        description="Optional pass-through of the AI recommendation this assignment fulfills, for audit logging.",
    )

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "incident_id": "INC-1042",
                "resource_ids": ["AMB-02", "RESCUE-01"],
                "recommendation_id": "REC-01",
                "decision_source": "n8n",
                "reason": "Confirming dispatch of the approved plan",
            }
        }
    )


class AssignmentResponse(BaseModel):
    id: str
    incident_id: str
    resource_id: str
    status: AssignmentStatus
    assigned_at: datetime
    completed_at: datetime | None
    decision_source: str
    approved_by: str | None
    recommendation_id: str | None = None
    eta_minutes: int | None = None
    previous_eta_minutes: int | None = None
    distance_km: float | None = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class AssignmentStatusUpdate(BaseModel):
    status: AssignmentStatus
    reason: str | None = None

