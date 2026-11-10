from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class Report(Base):
    """An immutable original emergency report attached to an incident.

    `original_text`/`original_language` are never overwritten by anything,
    including translation — see INTEGRATION_CONTRACT.md EmergencyReport and
    TEAM_INTEGRATION_PLAN.md D3/D10. Translation only adds
    `translated_text`/`translated_language`.

    `source_report_id` + `producer_identity` give the ingesting side (n8n)
    an idempotency key: resending the same report never creates a second
    row (see uq_reports_producer_source in the migration).
    """

    __tablename__ = "reports"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    incident_id: Mapped[str] = mapped_column(
        String, ForeignKey("incidents.id"), nullable=False, index=True
    )

    source_report_id: Mapped[str | None] = mapped_column(String, nullable=True)
    producer_identity: Mapped[str | None] = mapped_column(String, nullable=True)
    channel: Mapped[str | None] = mapped_column(String, nullable=True)

    original_text: Mapped[str] = mapped_column(Text, nullable=False)
    original_language: Mapped[str] = mapped_column(String, nullable=False)

    # Populated only after a translation has been requested and returned by
    # the AI service (POST /ai/translate-report, not yet implemented here).
    translated_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    translated_language: Mapped[str | None] = mapped_column(String, nullable=True)

    received_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
