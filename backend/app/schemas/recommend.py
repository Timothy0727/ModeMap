from pydantic import BaseModel, Field
from app.models.user_event import Mode
from typing import Any

class RecommendRequest(BaseModel):
    """Query parameters for GET /recommend endpoint."""

    mode: Mode
    lat: float = Field(..., ge=-90, le=90, description="User's current latitude")
    lng: float = Field(..., ge=-180, le=180, description="User's current longitude")
    radius: int = Field(1000, ge=100, le=50000, description="Search radius in meters")
    open_now: bool = Field(False, description="Whether to only include venues that are currently open")
    price: int | None = Field(None, ge=0, le=4, description="Price level (0-4), None = any")

class RecommendMeta(BaseModel):
    """Metadata for recommendation responses."""

    mode: Mode
    radius: int
    total_results: int = Field(..., description="Total number of matching venues")
    returned_results: int = Field(..., description="Number of venues returned in this response")
    cache_hit: bool | None = Field(None, description="Whether the response was served from cache")
    time_taken_ms: int | None = Field(None, description="Time taken to generate the response in milliseconds")

class VenueCard(BaseModel):
    """Schema for individual venue cards in recommendation responses."""

    id: str = Field(..., description="Unique identifier for the venue")
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
    explanations: list[str] | None = Field(None, description="Why this venue matches (2-3 bullet points)")

class RecommendResponse(BaseModel):
    """Response schema for GET /recommend endpoint."""

    meta: RecommendMeta
    venues: list[VenueCard] = Field(..., description="List of recommended venues")