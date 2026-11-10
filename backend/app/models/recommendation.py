from datetime import datetime

from sqlalchemy import DateTime, Float, ForeignKey, Integer, String, func
from sqlalchemy import Enum as SAEnum
from sqlalchemy.dialects.postgresql import ARRAY, JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.models.enums import RecommendationState


class Recommendation(Base):
    """A versioned, pending-until-approved resource plan for an incident.

    At most one PENDING recommendation may exist per incident at a time —
    enforced by uq_recommendation_pending_incident in the migration, the
    same partial-unique-index pattern used for live assignments. Approving,
    modifying or proposing a replacement never overwrites a row; it inserts
    a new one with an incremented `version`, so every prior version stays
    around for audit (TEAM_INTEGRATION_PLAN.md D4).

    A PENDING recommendation reserves nothing: creating one must never
    touch assignments/resources. Only the (not-yet-implemented) approval
    transaction may do that.
    """

    __tablename__ = "recommendations"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    incident_id: Mapped[str] = mapped_column(
        String, ForeignKey("incidents.id"), nullable=False, index=True
    )
    version: Mapped[int] = mapped_column(Integer, nullable=False)

    state: Mapped[RecommendationState] = mapped_column(
        SAEnum(
            RecommendationState,
            name="recommendation_state_enum",
            # See the matching comment on Incident.operational_phase: name
            # != value here, so SQLAlchemy must be told to send .value.
            values_callable=lambda enum_cls: [member.value for member in enum_cls],
        ),
        nullable=False,
        default=RecommendationState.PENDING,
        index=True,
    )

    recommended_resources: Mapped[list[str]] = mapped_column(
        ARRAY(String), nullable=False
    )
    reason: Mapped[str] = mapped_column(String, nullable=False)
    explanation: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
    priority_score: Mapped[int | None] = mapped_column(Integer, nullable=True)

    # Set only when this recommendation is a replacement proposal raised by
    # a road_obstruction event. Not a hard FK to resources.id: the failed
    # resource's own status can keep changing independently of this record.
    replacement_for_resource_id: Mapped[str | None] = mapped_column(
        String, nullable=True
    )
    replaced_assignment_id: Mapped[str | None] = mapped_column(
        String, ForeignKey("assignments.id", ondelete="SET NULL"), nullable=True
    )

    # Echoed back from the AI service's analysis input revision, so a
    # stale/late AI result can never be persisted over a newer one. Backend
    # does not interpret its contents.
    analysis_revision: Mapped[str | None] = mapped_column(String, nullable=True)

    # Set server-side only, from the authenticated coordinator identity
    # (TEAM_INTEGRATION_PLAN.md D9) — never trusted from a request body.
    decided_by: Mapped[str | None] = mapped_column(String, nullable=True)
    decided_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
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
