from datetime import datetime

from sqlalchemy import DateTime, Float, Integer, String, func
from sqlalchemy.dialects.postgresql import ARRAY
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy import Enum as SAEnum

from app.db.base import Base
from app.models.enums import IncidentStatus, OperationalPhase, Severity


class Incident(Base):
    __tablename__ = "incidents"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    location: Mapped[str] = mapped_column(String, nullable=False)
    latitude: Mapped[float | None] = mapped_column(Float, nullable=True)
    longitude: Mapped[float | None] = mapped_column(Float, nullable=True)

    # Free-text, intentionally not an enum/CHECK constraint — see
    # app.core.domain_values for why.
    type: Mapped[str] = mapped_column(String, nullable=False, index=True)

    severity: Mapped[Severity] = mapped_column(
        SAEnum(Severity, name="severity_enum"), nullable=False
    )
    priority_score: Mapped[int | None] = mapped_column(Integer, nullable=True)
    confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
    people_affected: Mapped[int | None] = mapped_column(Integer, nullable=True)
    needs: Mapped[list[str]] = mapped_column(
        ARRAY(String), nullable=False, default=list
    )

    status: Mapped[IncidentStatus] = mapped_column(
        SAEnum(IncidentStatus, name="incident_status_enum"),
        nullable=False,
        default=IncidentStatus.UNASSIGNED,
        index=True,
    )

    # Frontend-facing lifecycle phase (TEAM_INTEGRATION_PLAN.md D2). Kept
    # alongside `status` above rather than replacing it: `status` remains
    # the broad internal state machine services validate transitions
    # against; `operational_phase` is the finer-grained projection the
    # frontend's IncidentStatus union expects. The service layer is
    # responsible for keeping the two consistent.
    operational_phase: Mapped[OperationalPhase] = mapped_column(
        SAEnum(
            OperationalPhase,
            name="operational_phase_enum",
            # Without this, SQLAlchemy sends the Python member NAME
            # ("RECEIVED") rather than its lowercase VALUE ("received") —
            # the two diverge here (unlike IncidentStatus/Severity, where
            # name == value), and the DB enum only has the lowercase values.
            values_callable=lambda enum_cls: [member.value for member in enum_cls],
        ),
        nullable=False,
        default=OperationalPhase.RECEIVED,
        index=True,
    )

    # Numeric 1-5 severity from AI analysis, kept alongside the legacy
    # `severity` bucket above rather than replacing it (D2). Nullable
    # because it is only populated once analysis has run.
    severity_score: Mapped[int | None] = mapped_column(Integer, nullable=True)

    # Structured vulnerability codes (e.g. "elderly_mobility"), matching
    # frontend's Incident.vulnerabilities. See domain_values-style free-text
    # rationale; not an enum for the same extensibility reason as `type`.
    vulnerabilities: Mapped[list[str]] = mapped_column(
        ARRAY(String), nullable=False, default=list
    )

    # Count of reports merged into this incident as duplicates (excludes the
    # original report itself). Maintained by the report-intake service, not
    # derived from a live COUNT() query.
    duplicate_count: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )
