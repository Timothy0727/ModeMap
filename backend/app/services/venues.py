"""Venue persistence helpers."""

from __future__ import annotations

import logging
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.venue import Venue
from app.schemas.venue import VenueCreate

logger = logging.getLogger(__name__)


async def upsert_venues_from_provider(
    session: AsyncSession,
    venues: list[VenueCreate],
) -> int:
    """Insert or update venues returned from the provider.

    Called after /recommend cache misses so enrichment can find venues in DB
    without an extra Place Details call.

    Args:
        session: Active async SQLAlchemy session.
        venues: Normalized provider venues from a search response.

    Returns:
        Number of venues upserted.
    """
    if not venues:
        return 0

    now = datetime.now(UTC)
    count = 0

    for v in venues:
        result = await session.execute(select(Venue).where(Venue.provider_id == v.provider_id))
        existing = result.scalars().first()

        if existing:
            existing.name = v.name
            existing.categories = v.categories
            existing.lat = v.lat
            existing.lng = v.lng
            existing.address = v.address
            existing.rating = v.rating
            existing.price_level = v.price_level
            existing.hours = v.hours
            existing.raw_hours = v.raw_hours
            existing.last_seen_at = now
            existing.updated_at = now
        else:
            session.add(
                Venue(
                    provider_id=v.provider_id,
                    provider_name=v.provider_name,
                    name=v.name,
                    categories=v.categories,
                    lat=v.lat,
                    lng=v.lng,
                    address=v.address,
                    rating=v.rating,
                    price_level=v.price_level,
                    hours=v.hours,
                    raw_hours=v.raw_hours,
                    last_seen_at=now,
                    created_at=now,
                    updated_at=now,
                )
            )
        count += 1

    await session.commit()
    logger.debug("upsert_venues_from_provider: upserted %d venues", count)
    return count
