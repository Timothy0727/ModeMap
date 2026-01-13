"""Venue and VenueProfile models."""
import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import ARRAY, JSON, String, Text, ForeignKey, DateTime, Float, Integer
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class Venue(Base):
    """Core venue entity from places provider."""

    __tablename__ = "venues"

    # Primary key
    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        index=True,
    )

    # Provider identification
    provider_id: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    provider_name: Mapped[str] = mapped_column(String(50))  # "google" or "yelp"

    # Basic info
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    categories: Mapped[list[str]] = mapped_column(ARRAY(String), default=list)

    # Location
    lat: Mapped[float] = mapped_column(Float, nullable=False)
    lng: Mapped[float] = mapped_column(Float, nullable=False)
    address: Mapped[Optional[str]] = mapped_column(Text)

    # Ratings and pricing
    rating: Mapped[Optional[float]] = mapped_column(Float)
    price_level: Mapped[Optional[int]] = mapped_column(Integer)  # 0-4 scale

    # Hours (stored as JSON for flexibility)
    hours: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    raw_hours: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Timestamps
    last_seen_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=datetime.utcnow
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=datetime.utcnow
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
    )

    # Relationships
    profile: Mapped[Optional["VenueProfile"]] = relationship(
        "VenueProfile", back_populates="venue", uselist=False
    )

    def __repr__(self) -> str:
        return f"<Venue(id={self.id}, name={self.name}, provider={self.provider_name})>"


class VenueProfile(Base):
    """Enriched venue attributes inferred from reviews/analysis."""

    __tablename__ = "venue_profiles"

    # Primary key
    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        index=True,
    )

    # Foreign key to venue
    venue_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("venues.id", ondelete="CASCADE"),
        unique=True,
        index=True,
        nullable=False,
    )

    # Attribute scores (0-1 scale for each attribute)
    # Example: {"quiet": 0.85, "laptop_friendly": 0.72, "romantic": 0.15, ...}
    attribute_scores: Mapped[dict[str, float]] = mapped_column(
        JSON, default=dict, nullable=False
    )

    # Evidence snippets (top 1-3 snippets per attribute)
    # Example: {"quiet": ["Great for studying", "Very peaceful atmosphere"], ...}
    evidence_snippets: Mapped[dict[str, list[str]]] = mapped_column(
        JSON, default=dict, nullable=False
    )

    # Optional embedding reference (for vector search)
    embedding_ref: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)

    # Timestamps
    profiled_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=datetime.utcnow
    )
    expires_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    # Relationships
    venue: Mapped["Venue"] = relationship("Venue", back_populates="profile")

    def __repr__(self) -> str:
        return f"<VenueProfile(id={self.id}, venue_id={self.venue_id})>"
