"""FastAPI application main module."""

import logging
import math
import time

import httpx
from fastapi import Depends, FastAPI, HTTPException, Query, Response
from fastapi.middleware.cors import CORSMiddleware

from app.cache import build_recommend_cache_key, get_cached_recommend, set_cached_recommend
from app.config import settings
from app.models.user_event import Mode
from app.schemas.recommend import RecommendMeta, RecommendRequest, RecommendResponse, VenueCard
from app.schemas.venue import VenueCreate

logger = logging.getLogger(__name__)


class ModeSearch:
    """Text Search queries for a given mode.

    When strict filters (price, open_now) are active, the simple_query is used
    to avoid conflicts between descriptive natural-language queries and Google's
    structured filters.  The descriptive text_query is used when no strict
    filters are set.
    """

    def __init__(
        self,
        text_query: str,
        simple_query: str,
        included_type: str | None = None,
    ):
        self.text_query = text_query
        self.simple_query = simple_query
        self.included_type = included_type


MODE_SEARCH: dict[Mode, ModeSearch] = {
    Mode.WORK: ModeSearch(
        text_query="quiet cafe or coworking space with wifi",
        simple_query="cafe",
        included_type="cafe",
    ),
    Mode.DATE: ModeSearch(
        text_query="romantic restaurant or bar for a date",
        simple_query="restaurant",
        included_type="restaurant",
    ),
    Mode.QUICK_BITE: ModeSearch(
        text_query="quick food or fast casual restaurant",
        simple_query="restaurant",
        included_type="restaurant",
    ),
    Mode.BUDGET: ModeSearch(
        text_query="affordable restaurant or cheap eats",
        simple_query="restaurant",
        included_type="restaurant",
    ),
}

_DEFAULT_SEARCH = ModeSearch(
    text_query="restaurant",
    simple_query="restaurant",
    included_type="restaurant",
)


def _radius_query_suffix(radius_m: int) -> str:
    """Return a phrase like ' within 2.5 km' or ' within 500 m' for the text query."""
    if radius_m < 1000:
        return f" within {radius_m} m"
    km = radius_m / 1000.0
    if km == int(km):
        return f" within {int(km)} km"
    return f" within {km:.1f} km"


def _distance_sq(center_lat: float, center_lng: float, lat: float, lng: float) -> float:
    """Squared distance (proxy for ordering: smaller = closer)."""
    return (lat - center_lat) ** 2 + (lng - center_lng) ** 2


def _distance_m(center_lat: float, center_lng: float, lat: float, lng: float) -> float:
    """Great-circle distance in meters between two lat/lng points."""
    # Haversine formula
    radius_earth_m = 6_371_000.0
    phi1 = math.radians(center_lat)
    phi2 = math.radians(lat)
    d_phi = math.radians(lat - center_lat)
    d_lambda = math.radians(lng - center_lng)

    a = math.sin(d_phi / 2.0) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(
        d_lambda / 2.0
    ) ** 2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1.0 - a))
    return radius_earth_m * c


def _venue_create_to_card(v: VenueCreate, distance_m: float | None = None) -> VenueCard:
    """Convert VenueCreate to VenueCard with stable id and placeholder explanations."""
    return VenueCard(
        id=v.provider_id,
        provider_id=v.provider_id,
        provider_name=v.provider_name,
        name=v.name,
        categories=v.categories,
        lat=v.lat,
        lng=v.lng,
        distance_m=distance_m,
        address=v.address,
        rating=v.rating,
        price_level=v.price_level,
        hours=v.hours,
        raw_hours=v.raw_hours,
        explanations=[],
    )


def get_recommend_params(
    mode: Mode = Query(..., description="Recommendation mode: work, date, quick_bite, budget"),
    lat: float = Query(..., ge=-90, le=90, description="Latitude"),
    lng: float = Query(..., ge=-180, le=180, description="Longitude"),
    radius: int = Query(1000, ge=100, le=50000, description="Search radius in meters"),
    open_now: bool = Query(False, description="Only include venues open now"),
    price: int | None = Query(None, ge=0, le=4, description="Price level 0-4, omit for any"),
) -> RecommendRequest:
    """Dependency to validate and build RecommendRequest from query params."""
    return RecommendRequest(
        mode=mode,
        lat=lat,
        lng=lng,
        radius=radius,
        open_now=open_now,
        price=price,
    )


app = FastAPI(title="ModeMap API")

origins = ["http://localhost", "http://localhost:3000"]
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
def health():
    """Health check endpoint."""
    return {"status": "ok"}


@app.get("/hello")
def hello():
    """Hello endpoint."""
    return {"message": "hello"}


@app.get("/test/google-places")
async def test_google_places(lat: float = 37.7749, lng: float = -122.4194, radius: int = 1000):
    """Test endpoint for Google Places API integration.

    Args:
        lat: Latitude (default: San Francisco)
        lng: Longitude (default: San Francisco)
        radius: Search radius in meters (default: 1000)

    Returns:
        List of nearby venues
    """
    try:
        from app.providers import GooglePlacesClient

        client = GooglePlacesClient()
        venues = await client.search_nearby(
            lat=lat,
            lng=lng,
            radius_m=radius,
            max_results=10,
        )

        return {
            "status": "success",
            "count": len(venues),
            "venues": [venue.model_dump() for venue in venues],
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error fetching places: {str(e)}") from e


@app.get("/recommend", response_model=RecommendResponse)
async def recommend(
    response: Response,
    params: RecommendRequest = Depends(get_recommend_params),
    max_results: int = Query(60, ge=1, le=60, description="Max venues to return"),
    cache: int = Query(1, ge=0, le=1, description="1=use Redis cache, 0=bypass for benchmarking"),
):
    """Return ranked nearby venues for the given mode and filters."""
    try:
        t0 = time.perf_counter()

        if cache == 0:
            response.headers["X-Cache"] = "BYPASS"
            # Skip Redis; go straight to provider and return (no cache write).
        else:
            cache_key = build_recommend_cache_key(
                lat=params.lat,
                lng=params.lng,
                radius=params.radius,
                mode=params.mode,
                open_now=params.open_now,
                price=params.price,
            )
            cached = await get_cached_recommend(cache_key)
            if cached is not None:
                response.headers["X-Cache"] = "HIT"
                elapsed_ms = int((time.perf_counter() - t0) * 1000)
                meta = RecommendMeta(
                    mode=cached.meta.mode,
                    radius=cached.meta.radius,
                    total_results=cached.meta.total_results,
                    returned_results=cached.meta.returned_results,
                    cache_hit=True,
                    time_taken_ms=elapsed_ms,
                )
                response.headers["Server-Timing"] = f"app;dur={(time.perf_counter() - t0) * 1000:.2f}"
                return RecommendResponse(meta=meta, venues=cached.venues)
            response.headers["X-Cache"] = "MISS"

        from app.providers import GooglePlacesClient

        t0_fetch = time.perf_counter()
        mode_search = MODE_SEARCH.get(params.mode, _DEFAULT_SEARCH)

        has_strict_filters = params.price is not None or params.open_now
        base_query = mode_search.simple_query if has_strict_filters else mode_search.text_query
        text_query = base_query + _radius_query_suffix(params.radius)

        client = GooglePlacesClient()
        venues = await client.text_search(
            text_query=text_query,
            lat=params.lat,
            lng=params.lng,
            radius_m=params.radius,
            included_type=mode_search.included_type,
            open_now=params.open_now,
            price_level=params.price,
            max_results=max_results,
        )
        # Attach real distances, filter to within radius, then optionally to open-now only.
        scored: list[tuple[VenueCreate, float]] = []
        for v in venues:
            dist_m = _distance_m(params.lat, params.lng, v.lat, v.lng)
            if dist_m <= params.radius:
                scored.append((v, dist_m))

        if params.open_now:
            # When user asked for "open now", drop venues we know are closed.
            scored = [
                (v, d)
                for v, d in scored
                if v.hours is None or v.hours.get("open_now") is True
            ]

        def sort_key(item: tuple[VenueCreate, float]) -> tuple:
            venue, dist_m = item
            rating = -(venue.rating if venue.rating is not None else -1)
            return (rating, dist_m)

        scored = sorted(scored, key=sort_key)

        cards = [_venue_create_to_card(v, distance_m=dist_m) for v, dist_m in scored]
        total = len(cards)
        elapsed_ms = int((time.perf_counter() - t0_fetch) * 1000)

        meta = RecommendMeta(
            mode=params.mode,
            radius=params.radius,
            total_results=total,
            returned_results=total,
            cache_hit=False,
            time_taken_ms=elapsed_ms,
        )
        result = RecommendResponse(meta=meta, venues=cards)
        if cache == 1:
            await set_cached_recommend(cache_key, result, settings.recommend_cache_ttl_seconds)
        response.headers["Server-Timing"] = f"app;dur={(time.perf_counter() - t0) * 1000:.2f}"
        return result
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    except httpx.HTTPStatusError as e:
        detail = e.response.text if e.response else str(e)
        logger.error("Provider HTTP error in /recommend: %s", detail)
        raise HTTPException(
            status_code=502,
            detail=f"Provider error: {detail}",
        ) from e
    except Exception as e:
        logger.error("Unexpected error in /recommend: %s", e)
        raise HTTPException(status_code=500, detail=f"Error fetching places: {str(e)}") from e
