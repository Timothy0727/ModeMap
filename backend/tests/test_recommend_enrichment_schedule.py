"""Integration tests for /recommend enrichment scheduling."""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.schemas.venue import VenueCreate

pytestmark = pytest.mark.jobs


def _make_recommend_url(**overrides: str) -> str:
    params = {
        "mode": "work",
        "lat": "37.7749",
        "lng": "-122.4194",
        "radius": "1000",
        "open_now": "false",
        "max_results": "2",
        "cache": "0",
    }
    params.update(overrides)
    query = "&".join(f"{k}={v}" for k, v in params.items())
    return f"/recommend?{query}"


@pytest.fixture(autouse=True)
def disable_limiter():
    app.state.limiter.enabled = False
    yield
    app.state.limiter.enabled = True


def test_recommend_schedules_enrichment(monkeypatch):
    venues = [
        VenueCreate(
            provider_id="ChIJ_schedule_a",
            provider_name="google",
            name="Venue A",
            categories=["cafe"],
            lat=37.7749,
            lng=-122.4194,
            address="A St",
            rating=4.5,
            price_level=2,
            hours={"open_now": True},
            raw_hours=None,
        ),
        VenueCreate(
            provider_id="ChIJ_schedule_b",
            provider_name="google",
            name="Venue B",
            categories=["cafe"],
            lat=37.7750,
            lng=-122.4195,
            address="B St",
            rating=4.3,
            price_level=1,
            hours={"open_now": True},
            raw_hours=None,
        ),
    ]

    class DummyClient:
        def __init__(self, *args, **kwargs) -> None:
            pass

        async def text_search(self, *args, **kwargs):
            return venues

    scheduled_ids: list[str] = []

    async def capture_schedule(provider_ids: list[str]) -> None:
        scheduled_ids.extend(provider_ids)

    monkeypatch.setattr("app.providers.GooglePlacesClient", DummyClient)
    monkeypatch.setattr("app.main._schedule_enrichment_background", capture_schedule)
    monkeypatch.setattr("app.main._persist_venues_background", AsyncMock())

    with TestClient(app) as client:
        resp = client.get(_make_recommend_url())

    assert resp.status_code == 200
    assert "ChIJ_schedule_a" in scheduled_ids
    assert "ChIJ_schedule_b" in scheduled_ids


def test_recommend_response_unaffected_by_scheduling(monkeypatch):
    venues = [
        VenueCreate(
            provider_id="ChIJ_fast",
            provider_name="google",
            name="Fast Venue",
            categories=["cafe"],
            lat=37.7749,
            lng=-122.4194,
            address="Fast St",
            rating=4.8,
            price_level=2,
            hours={"open_now": True},
            raw_hours=None,
        ),
    ]

    class DummyClient:
        def __init__(self, *args, **kwargs) -> None:
            pass

        async def text_search(self, *args, **kwargs):
            return venues

    monkeypatch.setattr("app.providers.GooglePlacesClient", DummyClient)
    monkeypatch.setattr("app.main._schedule_enrichment_background", AsyncMock())
    monkeypatch.setattr("app.main._persist_venues_background", AsyncMock())

    client = TestClient(app)
    resp = client.get(_make_recommend_url())
    assert resp.status_code == 200
    body = resp.json()
    assert body["venues"][0]["provider_id"] == "ChIJ_fast"
    assert "attribute_scores" not in body["venues"][0]
