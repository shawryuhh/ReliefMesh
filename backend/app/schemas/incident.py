from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from app.core.domain_values import KNOWN_INCIDENT_TYPES
from app.models.enums import IncidentStatus, OperationalPhase, Severity
from app.schemas.assignment import AssignmentResponse


class IncidentCreate(BaseModel):
    location: str = Field(min_length=1)
    latitude: float | None = Field(default=None, ge=-90, le=90)
    longitude: float | None = Field(default=None, ge=-180, le=180)
    type: str = Field(
        min_length=1,
        description=(
            "Incident type. Free-text and extensible — common demo values: "
            f"{KNOWN_INCIDENT_TYPES}."
        ),
        examples=["flood"],
    )
    severity: Severity
    people_affected: int | None = Field(default=None, ge=0)
    needs: list[str] = Field(default_factory=list)
    confidence: float | None = Field(
        default=None, ge=0, le=1, description="AI's confidence in this extraction."
    )
    priority_score: int | None = Field(
        default=None, ge=0, le=100, description="AI-supplied priority score, if already known."
    )
    report_metadata: dict[str, Any] | None = Field(
        default=None,
        description=(
            "Not persisted on the incident row. Recorded into the "
            "'incident_received' action log for audit/provenance (e.g. source "
            "channel, raw report text, merged report ids)."
        ),
    )

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "location": "Krishna Apartments, Block C",
                "latitude": 12.9352,
                "longitude": 77.6146,
                "type": "flood",
                "severity": "CRITICAL",
                "people_affected": 4,
                "needs": ["medical", "evacuation"],
                "confidence": 0.88,
                "report_metadata": {
                    "channel": "whatsapp",
                    "raw_text": "Water entering Krishna Apartments Block C. My grandmother cannot walk.",
                },
            }
        }
    )


class IncidentUpdate(BaseModel):
    location: str | None = Field(default=None, min_length=1)
    latitude: float | None = Field(default=None, ge=-90, le=90)
    longitude: float | None = Field(default=None, ge=-180, le=180)
    severity: Severity | None = None
    priority_score: int | None = Field(default=None, ge=0, le=100)
    confidence: float | None = Field(default=None, ge=0, le=1)
    people_affected: int | None = Field(default=None, ge=0)
    needs: list[str] | None = None


class IncidentActionRequest(BaseModel):
    """Body for /incidents/{id}/resolve and /incidents/{id}/cancel."""

    reason: str | None = None


class IncidentResponse(BaseModel):
    id: str
    location: str
    latitude: float | None
    longitude: float | None
    type: str
    severity: Severity
    priority_score: int | None
    confidence: float | None
    people_affected: int | None
    needs: list[str]
    status: IncidentStatus
    operational_phase: OperationalPhase
    created_at: datetime
    updated_at: datetime
    current_assignments: list[AssignmentResponse] = Field(default_factory=list)

    model_config = ConfigDict(from_attributes=True)
