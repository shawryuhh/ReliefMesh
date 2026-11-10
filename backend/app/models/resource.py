from datetime import datetime

from sqlalchemy import DateTime, Float, Integer, String, func
from sqlalchemy.dialects.postgresql import ARRAY
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy import Enum as SAEnum

from app.db.base import Base
from app.models.enums import ResourceStatus


class Resource(Base):
    __tablename__ = "resources"

    id: Mapped[str] = mapped_column(String, primary_key=True)

    # Free-text, intentionally not an enum/CHECK constraint — see
    # app.core.domain_values for why.
    type: Mapped[str] = mapped_column(String, nullable=False, index=True)

    location: Mapped[str] = mapped_column(String, nullable=False)
    latitude: Mapped[float | None] = mapped_column(Float, nullable=True)
    longitude: Mapped[float | None] = mapped_column(Float, nullable=True)
    capabilities: Mapped[list[str]] = mapped_column(
        ARRAY(String), nullable=False, default=list
    )

    status: Mapped[ResourceStatus] = mapped_column(
        SAEnum(ResourceStatus, name="resource_status_enum"),
        nullable=False,
        default=ResourceStatus.AVAILABLE,
        index=True,
    )

    # Descriptive only in the MVP — not decremented/consumed by assignment
    # logic. Exists so shelters/hospitals/volunteer groups can use it later
    # without a schema change.
    capacity: Mapped[int | None] = mapped_column(Integer, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )
