from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.models.enums import RecommendationState


class ExplanationItem(BaseModel):
    """Matches frontend's `RecommendationExplanation`: a localized catalog key
    (e.g. "explain.blocked") plus flat params the UI interpolates. The backend
    stores and returns these as-is; it never generates or interprets them."""

    key: str = Field(min_length=1)
    params: dict[str, str | int | float] = Field(default_factory=dict)


class RecommendationCreate(BaseModel):
    """Body for POST .../recommendation — the AI/n8n-produced initial plan.

    Creating it reserves and dispatches nothing; it stays PENDING until a
    coordinator approves it. `analysis_revision` doubles as the idempotency
    key: resending the same revision with the same plan replays the existing
    recommendation instead of failing or creating a second one.
    """

    recommended_resources: list[str] = Field(min_length=1)
    reason: str = Field(min_length=1, description='Localized catalog key, e.g. "plan.reason".')
    explanation: list[ExplanationItem] = Field(default_factory=list)
    confidence: float | None = Field(default=None, ge=0, le=1)
    priority_score: int | None = Field(default=None, ge=0, le=100)
    analysis_revision: str | None = None

    model_config = ConfigDict(
        extra="forbid",
        json_schema_extra={
            "example": {
                "recommended_resources": ["AMB-02", "RESCUE-01"],
                "reason": "plan.reason",
                "explanation": [
                    {"key": "explain.distance", "params": {"id": "AMB-02", "distance": 2.1}},
                    {"key": "explain.water", "params": {"id": "RESCUE-01"}},
                ],
                "confidence": 0.91,
                "priority_score": 94,
                "analysis_revision": "analysis-1",
            }
        },
    )


class RecommendationProposeReplacement(BaseModel):
    """Body for POST .../recommendation/replacement.

    `recommended_resources` is the complete new plan — continuing responders
    included — not just the newcomers, matching the frontend mock's
    replacement plan (["AMB-05", "RESCUE-01"] replacing AMB-02). Approval
    later diffs it against the incident's live assignments.
    """

    base_version: int = Field(gt=0, description="The currently approved version being replaced.")
    replacement_for: str = Field(min_length=1, description="The failed resource, e.g. AMB-02.")
    recommended_resources: list[str] = Field(min_length=1)
    reason: str = Field(min_length=1, description='Localized catalog key, e.g. "plan.replacementReason".')
    explanation: list[ExplanationItem] = Field(default_factory=list)
    confidence: float | None = Field(default=None, ge=0, le=1)
    priority_score: int | None = Field(default=None, ge=0, le=100)
    analysis_revision: str | None = None

    model_config = ConfigDict(
        extra="forbid",
        json_schema_extra={
            "example": {
                "base_version": 1,
                "replacement_for": "AMB-02",
                "recommended_resources": ["AMB-05", "RESCUE-01"],
                "reason": "plan.replacementReason",
                "explanation": [
                    {"key": "explain.blocked", "params": {"id": "AMB-02", "old": 6, "eta": 24}},
                    {"key": "explain.available", "params": {"id": "AMB-05"}},
                    {"key": "explain.eta", "params": {"id": "AMB-05", "eta": 9}},
                    {"key": "explain.continues", "params": {"id": "RESCUE-01"}},
                ],
                "confidence": 0.91,
                "priority_score": 94,
                "analysis_revision": "analysis-2",
            }
        },
    )


class RecommendationApprove(BaseModel):
    """Body for POST .../recommendation/approve.

    Deliberately just the version being approved — no `approved_by`. That
    identity is never taken from the request; it's derived server-side from
    the authenticated coordinator API key (D9). `extra="forbid"` means a
    client that tries to smuggle one in gets a 422, not silent ignoring.
    """

    version: int = Field(gt=0, description="The version of the currently pending plan being approved.")

    model_config = ConfigDict(extra="forbid")


class RecommendationModify(BaseModel):
    """Body for POST .../recommendation/modify.

    Allows a human coordinator to replace the resource list of the currently
    pending recommendation, advancing its version while keeping it PENDING for
    explicit approval.
    """

    version: int = Field(gt=0, description="The version of the currently pending plan being modified.")
    recommended_resources: list[str] = Field(min_length=1)

    model_config = ConfigDict(extra="forbid")


class RecommendationReject(BaseModel):
    """Body for POST .../recommendation/reject.

    Allows a human coordinator to reject the currently pending recommendation
    with an explicit reason without dispatching any new resources.
    """

    version: int = Field(gt=0, description="The version of the currently pending plan being rejected.")
    reason: str = Field(min_length=1, max_length=500, description="Coordinator reason for rejecting the plan.")

    model_config = ConfigDict(extra="forbid")


class RecommendationResponse(BaseModel):
    """Matches frontend's `Recommendation` type (types/index.ts) field-for-field,
    plus internal bookkeeping fields (id, decided_by/at, timestamps) the
    contract doesn't define but doesn't forbid either — existing response
    schemas in this codebase (e.g. AssignmentResponse) take the same
    superset-of-the-documented-shape approach.
    """

    id: str
    # Frontend's Recommendation.incident, not incident_id — the ORM column is
    # incident_id, so this is the one place we alias rather than invent.
    incident: str = Field(validation_alias="incident_id")
    version: int
    state: RecommendationState
    recommended_resources: list[str]
    reason: str
    explanation: list[ExplanationItem]
    confidence: float | None = None
    priority_score: int | None = None
    replacementFor: str | None = Field(default=None, validation_alias="replacement_for_resource_id")
    approval_required: bool = True
    decided_by: str | None = None
    decided_at: datetime | None = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True, populate_by_name=True)
