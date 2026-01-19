"""Pydantic schemas for Venue and VenueProfile."""

from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.models.user_event import EventType, Mode, UserEvent
from app.models.venue import Venue, VenueProfile


class _BaseSchema(BaseModel):
    """Base schema with common configuration."""

    model_config = ConfigDict(from_attributes=True)


# ============================================================================
# Venue Schemas
# ============================================================================


class VenueCreate(_BaseSchema):
    """Schema for creating a venue from provider data."""

    provider_id: str = Field(..., max_length=255, description="Provider's unique ID for this venue")
    provider_name: str = Field(
        ..., max_length=50, description="Provider name (e.g., 'google', 'yelp')"
    )
    name: str = Field(..., max_length=255, description="Venue name")
    categories: list[str] = Field(default_factory=list, description="List of category strings")
    lat: float = Field(..., description="Latitude")
    lng: float = Field(..., description="Longitude")
    address: str | None = Field(None, description="Full address string")
    rating: float | None = Field(None, ge=0, le=5, description="Rating (0-5 scale)")
    price_level: int | None = Field(None, ge=0, le=4, description="Price level (0-4 scale)")
    hours: dict[str, Any] | None = Field(None, description="Structured hours data (JSON)")
    raw_hours: str | None = Field(None, description="Raw hours string from provider")


class VenueUpdate(_BaseSchema):
    """Schema for updating venue data (all fields optional)."""

    name: str | None = Field(None, max_length=255)
    categories: list[str] | None = None
    lat: float | None = None
    lng: float | None = None
    address: str | None = None
    rating: float | None = Field(None, ge=0, le=5)
    price_level: int | None = Field(None, ge=0, le=4)
    hours: dict[str, Any] | None = None
    raw_hours: str | None = None


class VenueResponse(_BaseSchema):
    """Schema for venue API responses."""

    id: UUID
    provider_id: str
    provider_name: str
    name: str
    categories: list[str]
    lat: float
    lng: float
    address: str | None
    rating: float | None
    price_level: int | None
    hours: dict[str, Any] | None
    raw_hours: str | None
    last_seen_at: datetime
    created_at: datetime
    updated_at: datetime


class VenueWithProfile(VenueResponse):
    """Venue response including profile data."""

    profile: VenueProfileResponse | None = None


# ============================================================================
# VenueProfile Schemas
# ============================================================================


class VenueProfileCreate(_BaseSchema):
    """Schema for creating a venue profile."""

    venue_id: UUID
    attribute_scores: dict[str, float] = Field(
        default_factory=dict, description="Attribute scores (0-1 scale)"
    )
    evidence_snippets: dict[str, list[str]] = Field(
        default_factory=dict, description="Evidence snippets per attribute"
    )
    embedding_ref: str | None = Field(
        None, max_length=255, description="Reference to embedding vector"
    )
    expires_at: datetime | None = Field(None, description="When this profile expires")


class VenueProfileResponse(_BaseSchema):
    """Schema for venue profile API responses."""

    id: UUID
    venue_id: UUID
    attribute_scores: dict[str, float]
    evidence_snippets: dict[str, list[str]]
    embedding_ref: str | None
    profiled_at: datetime
    expires_at: datetime | None


# ============================================================================
# UserEvent Schemas
# ============================================================================


class UserEventCreate(_BaseSchema):
    """Schema for creating a user event."""

    user_id: str | None = Field(
        None, max_length=255, description="User ID (nullable for anonymous)"
    )
    event_type: EventType = Field(..., description="Type of event")
    venue_id: UUID | None = Field(None, description="Related venue ID")
    mode: Mode | None = Field(None, description="Recommendation mode context")
    query_context: dict[str, Any] | None = Field(
        None, description="Query context (lat, lng, radius, etc.)"
    )


class UserEventResponse(_BaseSchema):
    """Schema for user event API responses."""

    id: UUID
    user_id: str | None
    event_type: EventType
    venue_id: UUID | None
    mode: Mode | None
    query_context: dict[str, Any] | None
    created_at: datetime


# ============================================================================
# Conversion Functions
# ============================================================================


def venue_to_response(
    venue: Venue, include_profile: bool = False
) -> VenueResponse | VenueWithProfile:
    """Convert SQLAlchemy Venue model to Pydantic response schema.

    Args:
        venue: SQLAlchemy Venue instance
        include_profile: If True, include profile data in response

    Returns:
        VenueResponse or VenueWithProfile schema instance
    """
    if include_profile and venue.profile:
        return VenueWithProfile.model_validate(venue)
    return VenueResponse.model_validate(venue)


def venue_from_create(venue_create: VenueCreate) -> dict[str, Any]:
    """Convert VenueCreate schema to dict for SQLAlchemy model creation.

    Args:
        venue_create: VenueCreate schema instance

    Returns:
        Dictionary of fields for creating Venue model
    """
    return venue_create.model_dump(exclude_unset=True)


def venue_profile_to_response(profile: VenueProfile) -> VenueProfileResponse:
    """Convert SQLAlchemy VenueProfile model to Pydantic response schema.

    Args:
        profile: SQLAlchemy VenueProfile instance

    Returns:
        VenueProfileResponse schema instance
    """
    return VenueProfileResponse.model_validate(profile)


def user_event_to_response(event: UserEvent) -> UserEventResponse:
    """Convert SQLAlchemy UserEvent model to Pydantic response schema.

    Args:
        event: SQLAlchemy UserEvent instance

    Returns:
        UserEventResponse schema instance
    """
    return UserEventResponse.model_validate(event)


def user_event_from_create(event_create: UserEventCreate) -> dict[str, Any]:
    """Convert UserEventCreate schema to dict for SQLAlchemy model creation.

    Args:
        event_create: UserEventCreate schema instance

    Returns:
        Dictionary of fields for creating UserEvent model
    """
    return event_create.model_dump(exclude_unset=True)
