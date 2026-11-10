from datetime import datetime

from sqlalchemy import DateTime, Float, ForeignKey, Index, Integer, String, func, text
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy import Enum as SAEnum

from app.db.base import Base
from app.models.enums import AssignmentStatus

# A resource may have at most one "live" (non-terminal) assignment at a time.
# This is the database-level backstop against double-assignment: even if
# application-level row locking were somehow bypassed, a second concurrent
# INSERT for the same resource fails this constraint instead of succeeding.
LIVE_ASSIGNMENT_STATUSES = (AssignmentStatus.ASSIGNED, AssignmentStatus.ACTIVE)


class Assignment(Base):
    __tablename__ = "assignments"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    incident_id: Mapped[str] = mapped_column(
        String, ForeignKey("incidents.id"), nullable=False, index=True
    )
    resource_id: Mapped[str] = mapped_column(
        String, ForeignKey("resources.id"), nullable=False, index=True
    )

    status: Mapped[AssignmentStatus] = mapped_column(
        SAEnum(AssignmentStatus, name="assignment_status_enum"),
        nullable=False,
        default=AssignmentStatus.ASSIGNED,
        index=True,
    )

    assigned_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    decision_source: Mapped[str] = mapped_column(String, nullable=False)
    approved_by: Mapped[str | None] = mapped_column(String, nullable=True)

    # Traces this assignment back to the approved plan that authorized it
    # (TEAM_INTEGRATION_PLAN.md D4). Nullable: existing/legacy assignments
    # and assignments created outside the recommendation flow have none.
    recommendation_id: Mapped[str | None] = mapped_column(
        String, ForeignKey("recommendations.id", ondelete="SET NULL"), nullable=True
    )

    # Supplied estimate, not invented routing (see plan's "honest ETA"
    # requirement). previous_eta_minutes is set when a road_obstruction
    # event revises eta_minutes, so the prior value isn't lost.
    eta_minutes: Mapped[int | None] = mapped_column(Integer, nullable=True)
    distance_km: Mapped[float | None] = mapped_column(Float, nullable=True)
    previous_eta_minutes: Mapped[int | None] = mapped_column(Integer, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    __table_args__ = (
        Index(
            "uq_assignment_live_resource",
            "resource_id",
            unique=True,
            postgresql_where=text(
                "status IN ('"
                + "', '".join(s.value for s in LIVE_ASSIGNMENT_STATUSES)
                + "')"
            ),
        ),
    )
