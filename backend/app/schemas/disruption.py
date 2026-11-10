from pydantic import BaseModel, ConfigDict, Field


class DisruptionReport(BaseModel):
    """Body for POST .../disruptions — n8n reporting that a dispatched
    responder is obstructed (e.g. a road block).

    The ETAs are supplied estimates, never computed here (the plan's "honest
    ETA" requirement). `previous_eta_minutes` is only used when the
    assignment has no stored ETA yet; otherwise the stored one is kept as the
    previous value.
    """

    resource_id: str = Field(min_length=1)
    eta_minutes: int = Field(ge=0)
    previous_eta_minutes: int | None = Field(default=None, ge=0)
    reason: str = "road_blocked"

    model_config = ConfigDict(
        extra="forbid",
        json_schema_extra={
            "example": {
                "resource_id": "AMB-02",
                "eta_minutes": 24,
                "previous_eta_minutes": 6,
                "reason": "road_blocked",
            }
        },
    )
