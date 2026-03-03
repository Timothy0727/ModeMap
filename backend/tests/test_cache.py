"""Tests for recommend cache key and Redis get/set."""

from unittest.mock import patch

import pytest

from app.cache import build_recommend_cache_key, get_cached_recommend, set_cached_recommend
from app.models.user_event import Mode
from app.schemas.recommend import RecommendMeta, RecommendResponse, VenueCard

# ─── Cache key unit tests ───────────────────────────────────────────────────


def test_build_recommend_cache_key_same_params_same_key():
    """Same (lat, lng, radius, mode, open_now, price) and same time bucket produce the same key."""
    with patch("app.cache.time") as mock_time:
        mock_time.time.return_value = 1000000.0  # fixed time bucket
        key1 = build_recommend_cache_key(
            lat=37.7749,
            lng=-122.4194,
            radius=1000,
            mode=Mode.WORK,
            open_now=False,
            price=None,
        )
        key2 = build_recommend_cache_key(
            lat=37.7749,
            lng=-122.4194,
            radius=1000,
            mode=Mode.WORK,
            open_now=False,
            price=None,
        )
    assert key1 == key2
    assert key1.startswith("recommend:")


def test_build_recommend_cache_key_different_params_different_keys():
    """Different params produce different cache keys."""
    with patch("app.cache.time") as mock_time:
        mock_time.time.return_value = 1000000.0

        base = build_recommend_cache_key(
            lat=37.7749,
            lng=-122.4194,
            radius=1000,
            mode=Mode.WORK,
            open_now=False,
            price=None,
        )

        different_lat = build_recommend_cache_key(
            lat=37.8,
            lng=-122.4194,
            radius=1000,
            mode=Mode.WORK,
            open_now=False,
            price=None,
        )
        different_radius = build_recommend_cache_key(
            lat=37.7749,
            lng=-122.4194,
            radius=2000,
            mode=Mode.WORK,
            open_now=False,
            price=None,
        )
        different_mode = build_recommend_cache_key(
            lat=37.7749,
            lng=-122.4194,
            radius=1000,
            mode=Mode.DATE,
            open_now=False,
            price=None,
        )
        different_open_now = build_recommend_cache_key(
            lat=37.7749,
            lng=-122.4194,
            radius=1000,
            mode=Mode.WORK,
            open_now=True,
            price=None,
        )
        different_price = build_recommend_cache_key(
            lat=37.7749,
            lng=-122.4194,
            radius=1000,
            mode=Mode.WORK,
            open_now=False,
            price=2,
        )

    assert base != different_lat
    assert base != different_radius
    assert base != different_mode
    assert base != different_open_now
    assert base != different_price


# ─── Cache get/set tests (in-memory fake) ────────────────────────────────────


@pytest.fixture
def fake_redis_storage():
    """In-memory dict and async context manager yielding a client that uses it."""
    storage = {}

    class FakeClient:
        async def get(self, key):
            return storage.get(key)

        async def set(self, key, value, ex=None):
            storage[key] = value

    class AsyncCm:
        def __init__(self):
            self._client = FakeClient()

        async def __aenter__(self):
            return self._client

        async def __aexit__(self, *args):
            pass

    def from_url(_url):
        return AsyncCm()

    return storage, from_url


@pytest.mark.asyncio
async def test_get_set_cached_recommend_roundtrip(fake_redis_storage):
    """Set a response, get it back; assert equality and that cache can be read."""
    storage, from_url = fake_redis_storage
    meta = RecommendMeta(
        mode=Mode.WORK,
        radius=1000,
        total_results=1,
        returned_results=1,
        cache_hit=False,
        time_taken_ms=100,
    )
    card = VenueCard(
        id="place_1",
        provider_id="place_1",
        provider_name="google",
        name="Test Cafe",
        categories=["cafe"],
        lat=37.77,
        lng=-122.42,
        distance_m=500.0,
        address="123 Test St",
        rating=4.5,
        price_level=2,
        hours=None,
        raw_hours=None,
        explanations=[],
    )
    response = RecommendResponse(meta=meta, venues=[card])
    cache_key = "recommend:9q8yy:1000:1111:work:false:any"

    with patch("app.cache.Redis") as MockRedis:
        MockRedis.from_url = from_url

        await set_cached_recommend(cache_key, response, ttl_seconds=60)
        assert cache_key in storage

        got = await get_cached_recommend(cache_key)
        assert got is not None
        assert got.meta.mode == response.meta.mode
        assert got.meta.radius == response.meta.radius
        assert got.meta.cache_hit == response.meta.cache_hit
        assert len(got.venues) == 1
        assert got.venues[0].id == card.id
        assert got.venues[0].name == card.name


@pytest.mark.asyncio
async def test_get_cached_recommend_miss_returns_none(fake_redis_storage):
    """get_cached_recommend returns None when key is not in cache."""
    _, from_url = fake_redis_storage
    with patch("app.cache.Redis") as MockRedis:
        MockRedis.from_url = from_url
        got = await get_cached_recommend("recommend:nonexistent:1000:1111:work:false:any")
    assert got is None
