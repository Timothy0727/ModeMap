"""UserEvent model for telemetry and feedback."""
import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import JSON, String, Text, ForeignKey, DateTime, Enum as SQLEnum
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column
import enum

from app.db.base import Base


class EventType(str, enum.Enum):
    """User event types."""

    IMPRESSION = "impression"
    CLICK = "click"
    SAVE = "save"
    THUMBS_UP = "thumbs_up"
    THUMBS_DOWN = "thumbs_down"
    NAVIGATE = "navigate"


class Mode(str, enum.Enum):
    """Recommendation modes."""

    WORK = "work"
    DATE = "date"
    QUICK_BITE = "quick_bite"
    BUDGET = "budget"


class UserEvent(Base):
    """User interaction events for telemetry and personalization."""

    __tablename__ = "user_events"

    # Primary key
    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        index=True,
    )

    # User identification (nullable for anonymous/incognito)
    user_id: Mapped[Optional[str]] = mapped_column(String(255), nullable=True, index=True)

    # Event type
    event_type: Mapped[EventType] = mapped_column(
        SQLEnum(EventType, name="event_type_enum"), nullable=False, index=True
    )

    # Venue reference (nullable for some event types)
    venue_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("venues.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    # Mode context
    mode: Mapped[Optional[Mode]] = mapped_column(
        SQLEnum(Mode, name="mode_enum"), nullable=True, index=True
    )

    # Query context (lat/lng tile, radius, filters)
    # Example: {"lat": 37.7749, "lng": -122.4194, "radius": 1000, "tile": "9q8yy", ...}
    query_context: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)

    # Timestamp
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=datetime.utcnow, index=True
    )

    def __repr__(self) -> str:
        return (
            f"<UserEvent(id={self.id}, type={self.event_type.value}, "
            f"user_id={self.user_id})>"
        )
