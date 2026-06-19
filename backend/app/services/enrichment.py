"""
Venue enrichment service.

enrich_venue_profile(provider_id, session)
  1. Locate the Venue in DB by provider_id; if absent, fetch details from
     Google Places and create the record.
  2. Check whether the existing VenueProfile is fresh (within TTL).
  3. If stale or missing: call Google Places reviews endpoint, run heuristic
     text analysis, then upsert VenueProfile.
  4. Return the current VenueProfileResponse.

This function is designed so that Step 6 can wrap it in a Celery task without
refactoring the core logic.
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.venue import Venue, VenueProfile
from app.providers.google import GooglePlacesClient
from app.schemas.venue import VenueProfileResponse
from app.text_attributes.heuristics import infer_attributes_from_text

logger = logging.getLogger(__name__)

# Profiles older than this are considered stale and will be re-inferred.
PROFILE_TTL_DAYS = 7


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


async def enrich_venue_profile(
    provider_id: str,
    session: AsyncSession,
    ttl_days: int = PROFILE_TTL_DAYS,
) -> VenueProfileResponse:
    """Enrich a venue with heuristic attribute scores derived from its reviews.

    If the venue is not yet in the DB it is created automatically from the
    Google Places Details API.  If the profile already exists and is within
    ``ttl_days`` days of its ``profiled_at`` timestamp it is returned as-is.

    Args:
        provider_id: Google Places place ID (matches Venue.provider_id).
        session: Active async SQLAlchemy session.
        ttl_days: Number of days before a profile is considered stale.

    Returns:
        VenueProfileResponse with the current (or freshly computed) profile.

    Raises:
        ValueError: If the place cannot be found via the provider API.
        httpx.HTTPStatusError: If the provider API returns an error.
    """
    venue = await _get_or_create_venue(provider_id, session)

    # Re-load with profile relationship to avoid lazy-load issues
    result = await session.execute(
        select(Venue).where(Venue.id == venue.id).options(selectinload(Venue.profile))
    )
    venue = result.scalars().one()

    if _is_fresh(venue.profile, ttl_days):
        logger.debug("enrich_venue_profile(%s): profile is fresh, skipping", provider_id)
        return VenueProfileResponse.model_validate(venue.profile)

    logger.info("enrich_venue_profile(%s): enriching venue", provider_id)

    # Fetch review snippets from provider
    client = GooglePlacesClient()
    snippets = await client.fetch_place_reviews(provider_id)
    texts = [s.text for s in snippets]

    # Run heuristic text pipeline
    scores, evidence = infer_attributes_from_text(texts)

    logger.debug(
        "enrich_venue_profile(%s): inferred %d attributes from %d snippets",
        provider_id,
        len(scores),
        len(texts),
    )

    # Upsert VenueProfile
    now = datetime.now(UTC)
    expires_at = now + timedelta(days=ttl_days)

    if venue.profile:
        venue.profile.attribute_scores = scores
        venue.profile.evidence_snippets = evidence
        venue.profile.profiled_at = now
        venue.profile.expires_at = expires_at
    else:
        profile = VenueProfile(
            venue_id=venue.id,
            attribute_scores=scores,
            evidence_snippets=evidence,
            profiled_at=now,
            expires_at=expires_at,
        )
        session.add(profile)
        venue.profile = profile

    await session.commit()
    await session.refresh(venue.profile)
    return VenueProfileResponse.model_validate(venue.profile)


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


async def _get_or_create_venue(provider_id: str, session: AsyncSession) -> Venue:
    """Return an existing Venue or create one from Google Places Details."""
    result = await session.execute(
        select(Venue).where(Venue.provider_id == provider_id)
    )
    venue = result.scalars().first()
    if venue:
        return venue

    # Venue is not in DB yet — fetch basic info from Google Places Details
    client = GooglePlacesClient()
    venue_create = await client.fetch_place_details(provider_id)
    if not venue_create:
        raise ValueError(f"Place not found in provider: {provider_id}")

    now = datetime.now(UTC)
    venue = Venue(
        provider_id=venue_create.provider_id,
        provider_name=venue_create.provider_name,
        name=venue_create.name,
        categories=venue_create.categories,
        lat=venue_create.lat,
        lng=venue_create.lng,
        address=venue_create.address,
        rating=venue_create.rating,
        price_level=venue_create.price_level,
        hours=venue_create.hours,
        raw_hours=venue_create.raw_hours,
        last_seen_at=now,
        created_at=now,
        updated_at=now,
    )
    session.add(venue)
    await session.flush()  # Populate venue.id before profile FK is set
    logger.info("enrich_venue_profile: created venue %s (%s)", venue.name, provider_id)
    return venue


def _is_fresh(profile: VenueProfile | None, ttl_days: int) -> bool:
    """Return True if the profile exists and was profiled within ttl_days."""
    if profile is None:
        return False
    profiled = profile.profiled_at
    if profiled is None:
        return False
    if profiled.tzinfo is None:
        profiled = profiled.replace(tzinfo=UTC)
    return (datetime.now(UTC) - profiled) < timedelta(days=ttl_days)
