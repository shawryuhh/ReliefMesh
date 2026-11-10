from datetime import datetime
from typing import Any

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class ActionLog(Base):
    __tablename__ = "action_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    timestamp: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False, index=True
    )

    source: Mapped[str] = mapped_column(String, nullable=False)
    # Open string, not an enum — the set of action types is illustrative and
    # expected to grow as ingestion/AI/n8n evolve.
    action: Mapped[str] = mapped_column(String, nullable=False, index=True)
    reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    result: Mapped[str | None] = mapped_column(String, nullable=True)

    incident_id: Mapped[str | None] = mapped_column(
        String, ForeignKey("incidents.id", ondelete="SET NULL"), nullable=True, index=True
    )
    resource_id: Mapped[str | None] = mapped_column(
        String, ForeignKey("resources.id", ondelete="SET NULL"), nullable=True, index=True
    )
    assignment_id: Mapped[str | None] = mapped_column(
        String, ForeignKey("assignments.id", ondelete="SET NULL"), nullable=True, index=True
    )

    log_metadata: Mapped[dict[str, Any] | None] = mapped_column(
        "metadata", JSONB, nullable=True
    )
