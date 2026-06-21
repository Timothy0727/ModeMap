"""Service-level tests for venue enrichment and persistence."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock

import pytest
import pytest_asyncio
from sqlalchemy import select

from app.models.venue import Venue, VenueProfile
from app.providers.google import ReviewSnippet
from app.schemas.venue import VenueCreate
from app.services.enrichment import enrich_venue_profile
from app.services.venues import upsert_venues_from_provider

pytestmark = pytest.mark.enrichment


def _venue_create(provider_id: str = "ChIJ_test_place") -> VenueCreate:
    return VenueCreate(
        provider_id=provider_id,
        provider_name="google",
        name="Test Cafe",
        categories=["cafe"],
        lat=37.77,
        lng=-122.42,
        address="123 Test St",
        rating=4.2,
        price_level=2,
        hours={"open_now": True},
        raw_hours=None,
    )


class FakeGoogleClient:
    """Minimal Google Places client stub for enrichment tests."""

    def __init__(
        self,
        reviews: list[ReviewSnippet] | None = None,
        details: VenueCreate | None = None,
    ):
        self.reviews = reviews or [
            ReviewSnippet(text="Quiet cafe with great wifi and fast service."),
            ReviewSnippet(text="Good value and romantic atmosphere for date night."),
        ]
        self.details = details or _venue_create()

    async def fetch_place_reviews(self, provider_place_id: str, max_snippets: int = 10):
        return self.reviews[:max_snippets]

    async def fetch_place_details(self, provider_place_id: str):
        return self.details


@pytest_asyncio.fixture
async def sample_venue(test_session):
    """Persist a venue row for enrichment tests."""
    venue = Venue(
        provider_id="ChIJ_test_place",
        provider_name="google",
        name="Test Cafe",
        categories=["cafe"],
        lat=37.77,
        lng=-122.42,
        address="123 Test St",
        rating=4.2,
        price_level=2,
        hours={"open_now": True},
        last_seen_at=datetime.now(UTC),
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )
    test_session.add(venue)
    await test_session.commit()
    await test_session.refresh(venue)
    return venue


@pytest.mark.asyncio
async def test_enrich_creates_profile_from_reviews(test_session, sample_venue):
    client = FakeGoogleClient()
    result = await enrich_venue_profile(
        sample_venue.provider_id,
        test_session,
        client=client,  # type: ignore[arg-type]
    )

    assert result.venue_id == sample_venue.id
    assert result.attribute_scores
    assert "quiet" in result.attribute_scores or "laptop_friendly" in result.attribute_scores
    assert result.evidence_snippets

    row = await test_session.execute(
        select(VenueProfile).where(VenueProfile.venue_id == sample_venue.id)
    )
    profile = row.scalars().one()
    assert profile.attribute_scores == result.attribute_scores


@pytest.mark.asyncio
async def test_enrich_skips_fresh_profile(test_session, sample_venue):
    fresh = VenueProfile(
        venue_id=sample_venue.id,
        attribute_scores={"quiet": 0.9},
        evidence_snippets={"quiet": ["Already profiled"]},
        profiled_at=datetime.now(UTC),
        expires_at=datetime.now(UTC) + timedelta(days=7),
    )
    test_session.add(fresh)
    await test_session.commit()

    client = FakeGoogleClient()
    client.fetch_place_reviews = AsyncMock(return_value=[ReviewSnippet(text="should not run")])

    result = await enrich_venue_profile(
        sample_venue.provider_id,
        test_session,
        client=client,  # type: ignore[arg-type]
    )

    assert result.attribute_scores == {"quiet": 0.9}
    client.fetch_place_reviews.assert_not_called()


@pytest.mark.asyncio
async def test_enrich_creates_venue_when_missing(test_session):
    client = FakeGoogleClient(details=_venue_create("ChIJ_new_place"))
    result = await enrich_venue_profile(
        "ChIJ_new_place",
        test_session,
        client=client,  # type: ignore[arg-type]
    )

    row = await test_session.execute(select(Venue).where(Venue.provider_id == "ChIJ_new_place"))
    venue = row.scalars().one()
    assert venue.name == "Test Cafe"
    assert result.venue_id == venue.id
    assert result.attribute_scores


@pytest.mark.asyncio
async def test_upsert_venues_inserts_and_updates(test_session):
    v1 = _venue_create("ChIJ_upsert_a")
    inserted = await upsert_venues_from_provider(test_session, [v1])
    assert inserted == 1

    v2 = v1.model_copy(update={"name": "Updated Cafe"})
    updated = await upsert_venues_from_provider(test_session, [v2])
    assert updated == 1

    row = await test_session.execute(select(Venue).where(Venue.provider_id == "ChIJ_upsert_a"))
    venue = row.scalars().one()
    assert venue.name == "Updated Cafe"
