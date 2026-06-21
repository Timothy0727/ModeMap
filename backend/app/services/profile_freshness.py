"""Shared profile freshness checks for enrichment and job scheduling."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from app.models.venue import VenueProfile

PROFILE_TTL_DAYS = 7


def is_profile_fresh(profile: VenueProfile | None, ttl_days: int = PROFILE_TTL_DAYS) -> bool:
    """Return True if the profile exists and was profiled within ttl_days."""
    if profile is None:
        return False
    profiled = profile.profiled_at
    if profiled is None:
        return False
    if profiled.tzinfo is None:
        profiled = profiled.replace(tzinfo=UTC)
    return (datetime.now(UTC) - profiled) < timedelta(days=ttl_days)
