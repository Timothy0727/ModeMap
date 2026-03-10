"""Redis cache for /recommend responses."""

import logging
import time
from typing import TYPE_CHECKING

import pygeohash
from redis.asyncio import Redis

from app.config import settings

if TYPE_CHECKING:
    from app.models.user_event import Mode
    from app.schemas.recommend import RecommendResponse

logger = logging.getLogger(__name__)

# Discrete radius buckets (meters) for cache key; same bucket = shared cache.
RADIUS_BUCKETS = (500, 1000, 2000, 5000, 10000, 20000, 50000)
TIME_BUCKET_SECONDS = 900  # 15 minutes


def _radius_bucket(radius: int) -> int:
    """Map radius to the smallest bucket >= radius, or max bucket."""
    for b in RADIUS_BUCKETS:
        if radius <= b:
            return b
    return RADIUS_BUCKETS[-1]


def build_recommend_cache_key(
    lat: float,
    lng: float,
    radius: int,
    mode: "Mode",
    open_now: bool,
    price: int | None,
) -> str:
    """Build a cache key for /recommend from request params.

    Key includes: geohash tile, radius bucket, time bucket, mode, open_now, price.
    """
    geohash_str = pygeohash.encode(lat, lng, precision=6)
    radius_b = _radius_bucket(radius)
    time_b = int(time.time() // TIME_BUCKET_SECONDS)
    mode_str = str(mode.value) if hasattr(mode, "value") else str(mode)
    open_str = "true" if open_now else "false"
    price_str = "any" if price is None else str(price)
    return f"recommend:{geohash_str}:{radius_b}:{time_b}:{mode_str}:{open_str}:{price_str}"


async def get_cached_recommend(cache_key: str) -> "RecommendResponse | None":
    """Return cached RecommendResponse if present; None on miss or error."""
    from app.schemas.recommend import RecommendResponse

    try:
        async with Redis.from_url(settings.redis_url) as client:
            payload = await client.get(cache_key)
    except Exception as e:
        logger.warning("Redis get failed for recommend cache: %s", e)
        return None

    if payload is None:
        return None

    try:
        return RecommendResponse.model_validate_json(payload)
    except Exception as e:
        logger.warning("Failed to deserialize cached recommend response: %s", e)
        return None


async def set_cached_recommend(
    cache_key: str,
    response: "RecommendResponse",
    ttl_seconds: int,
) -> None:
    """Store RecommendResponse in Redis with the given TTL. Logs and skips on error."""
    try:
        payload = response.model_dump_json()
        async with Redis.from_url(settings.redis_url) as client:
            await client.set(cache_key, payload, ex=ttl_seconds)
    except Exception as e:
        logger.warning("Redis set failed for recommend cache: %s", e)
