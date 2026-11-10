from pydantic import BaseModel, Field


class AIRecommendation(BaseModel):
    """Integration contract for a recommendation produced by the AI service.

    The backend never computes any of these values — it only validates,
    persists (via an action_log entry), and enforces safety rules when the
    recommendation is actually turned into an assignment.
    """

    incident_id: str
    priority_score: int = Field(ge=0, le=100)
    recommended_resources: list[str] = Field(min_length=1)
    reason: str
    approval_required: bool = True
    confidence: float | None = Field(default=None, ge=0, le=1)

    model_config = {
        "json_schema_extra": {
            "example": {
                "incident_id": "INC-1042",
                "priority_score": 94,
                "recommended_resources": ["AMB-02", "RESCUE-01"],
                "reason": "Medical emergency involving a vulnerable person",
                "approval_required": True,
                "confidence": 0.91,
            }
        }
    }
