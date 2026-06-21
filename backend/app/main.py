"""FastAPI application main module."""

import asyncio
import logging
import math
import time
import uuid

import httpx
from fastapi import Depends, FastAPI, HTTPException, Query, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address
from sqlalchemy.ext.asyncio import AsyncSession

from app.cache import build_recommend_cache_key, get_cached_recommend, set_cached_recommend
from app.config import settings
from app.db.session import AsyncSessionLocal, get_db
from app.models.job import JobStatus, JobType
from app.models.user_event import Mode
from app.ranking import score_and_explain
from app.schemas.job import JobListResponse, JobResponse, JobSummaryResponse
from app.schemas.recommend import RecommendMeta, RecommendRequest, RecommendResponse, VenueCard
from app.schemas.venue import VenueCreate, VenueProfileResponse

logger = logging.getLogger(__name__)
limiter = Limiter(key_func=get_remote_address)


async def _persist_venues_background(venues: list[VenueCreate]) -> None:
    """Best-effort upsert of recommend results so enrichment can find venues in DB."""
    try:
        from app.services.venues import upsert_venues_from_provider

        async with AsyncSessionLocal() as session:
            await upsert_venues_from_provider(session, venues)
    except Exception as e:
        logger.warning("Background venue persist failed: %s", e)


async def _schedule_enrichment_background(provider_ids: list[str]) -> None:
    """Best-effort scheduling of background enrichment jobs for recommend results."""
    try:
        from redis.asyncio import Redis

        from app.services.jobs import schedule_enrich_for_provider_ids

        redis = Redis.from_url(settings.celery_broker_url)
        try:
            async with AsyncSessionLocal() as session:
                await schedule_enrich_for_provider_ids(provider_ids, session, redis)
        finally:
            await redis.aclose()
    except Exception as e:
        logger.warning("Background enrichment schedule failed: %s", e)


def _require_admin_api() -> None:
    """Return 404 when admin endpoints are disabled."""
    if not settings.admin_api_enabled:
        raise HTTPException(status_code=404, detail="Not found")


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

    a = math.sin(d_phi / 2.0) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(d_lambda / 2.0) ** 2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1.0 - a))
    return radius_earth_m * c


def _venue_create_to_card(
    v: VenueCreate,
    distance_m: float | None = None,
    explanations: list[str] | None = None,
) -> VenueCard:
    """Convert VenueCreate to VenueCard with stable id and optional explanations."""
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
        explanations=explanations if explanations is not None else [],
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
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

origins = ["http://localhost", "http://localhost:3000"]
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def _provider_error_response(detail: str, provider_status: int) -> HTTPException:
    """Map Google Places provider failures to actionable API errors."""
    if provider_status == 403 or "PERMISSION_DENIED" in detail:
        return HTTPException(
            status_code=503,
            detail=(
                "Google Places API access denied. Enable 'Places API (New)' in Google Cloud "
                "Console, enable billing, and ensure GOOGLE_PLACES_API_KEY in .env is valid with "
                "no referrer/IP restrictions blocking server requests. "
                "See backend/GOOGLE_PLACES_SETUP.md."
            ),
        )
    return HTTPException(status_code=502, detail=f"Provider error: {detail}")


@app.get("/health")
def health():
    """Health check endpoint."""
    return {"status": "ok"}


@app.get("/hello")
def hello():
    """Hello endpoint."""
    return {"message": "hello"}


@app.get("/venues/{provider_id}/profile", response_model=VenueProfileResponse)
async def get_venue_profile(
    provider_id: str,
    session: AsyncSession = Depends(get_db),
):
    """Return enriched attribute profile for a venue.

    Triggers heuristic enrichment (reviews → attribute scores + evidence
    snippets) if the profile is missing or older than the TTL.  Returns
    immediately when the profile is already fresh.

    Args:
        provider_id: Google Places place ID (e.g. ``ChIJ...``).

    Returns:
        VenueProfileResponse with attribute_scores and evidence_snippets.
    """
    from redis.asyncio import Redis

    from app.services.enrichment import enrich_venue_profile
    from app.services.jobs import profile_is_fresh_for_provider, schedule_enrich_venue

    try:
        if not await profile_is_fresh_for_provider(session, provider_id):
            try:
                redis = Redis.from_url(settings.celery_broker_url)
                try:
                    await schedule_enrich_venue(provider_id, session, redis)
                finally:
                    await redis.aclose()
            except Exception as schedule_err:
                logger.warning(
                    "Background enrichment schedule failed for profile %s: %s",
                    provider_id,
                    schedule_err,
                )
        return await enrich_venue_profile(provider_id, session)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    except httpx.HTTPStatusError as e:
        detail = e.response.text if e.response else str(e)
        logger.error("Provider error enriching venue %s: %s", provider_id, detail)
        provider_status = e.response.status_code if e.response else 0
        raise _provider_error_response(detail, provider_status) from e
    except Exception as e:
        logger.error("Unexpected error enriching venue %s: %s", provider_id, e)
        raise HTTPException(status_code=500, detail="Enrichment failed") from e


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
@limiter.limit("60/minute")
async def recommend(
    request: Request,
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
                response.headers["Server-Timing"] = (
                    f"app;dur={(time.perf_counter() - t0) * 1000:.2f}"
                )
                return RecommendResponse(meta=meta, venues=cached.venues)
            response.headers["X-Cache"] = "MISS"

        from app.providers import GooglePlacesClient

        t0_fetch = time.perf_counter()
        mode_search = MODE_SEARCH.get(params.mode, _DEFAULT_SEARCH)

        has_strict_filters = params.price is not None or params.open_now
        base_query = mode_search.simple_query if has_strict_filters else mode_search.text_query
        text_query = base_query + _radius_query_suffix(params.radius)

        client = GooglePlacesClient()
        max_attempts = 3
        backoff_seconds = [1.0, 2.0, 4.0]
        venues_list: list[VenueCreate] | None = None
        last_err: Exception | None = None
        for attempt in range(max_attempts):
            try:
                venues_list = await client.text_search(
                    text_query=text_query,
                    lat=params.lat,
                    lng=params.lng,
                    radius_m=params.radius,
                    included_type=mode_search.included_type,
                    open_now=params.open_now,
                    price_level=params.price,
                    max_results=max_results,
                )
                break
            except httpx.HTTPStatusError as e:
                last_err = e
                status = e.response.status_code if e.response else 0
                if attempt < max_attempts - 1 and (status >= 500 or status == 429):
                    delay = backoff_seconds[attempt]
                    logger.warning(
                        "Provider %s (attempt %d/%d), retrying in %.1fs",
                        status,
                        attempt + 1,
                        max_attempts,
                        delay,
                    )
                    await asyncio.sleep(delay)
                else:
                    raise
            except Exception as e:
                last_err = e
                if attempt < max_attempts - 1:
                    delay = backoff_seconds[attempt]
                    logger.warning(
                        "Provider error (attempt %d/%d): %s, retrying in %.1fs",
                        attempt + 1,
                        max_attempts,
                        e,
                        delay,
                    )
                    await asyncio.sleep(delay)
                else:
                    raise
        if venues_list is None and last_err is not None:
            # All attempts failed; re-raise the last error.
            raise last_err
        venues = venues_list or []
        if venues:
            asyncio.create_task(_persist_venues_background(venues))
            provider_ids = [v.provider_id for v in venues]
            asyncio.create_task(_schedule_enrichment_background(provider_ids))
        # Attach real distances, filter to within radius, then optionally to open-now only.
        scored: list[tuple[VenueCreate, float]] = []
        for v in venues:
            dist_m = _distance_m(params.lat, params.lng, v.lat, v.lng)
            if dist_m <= params.radius:
                scored.append((v, dist_m))

        if params.open_now:
            # When user asked for "open now", drop venues we know are closed.
            scored = [
                (v, d) for v, d in scored if v.hours is None or v.hours.get("open_now") is True
            ]

        # Mode-specific ranking: score and explanations from app.ranking
        ranked: list[tuple[VenueCreate, float, float, list[str]]] = []
        for v, dist_m in scored:
            score, explanations = score_and_explain(v, dist_m, params.radius, params.mode)
            ranked.append((v, dist_m, score, explanations))
        ranked.sort(key=lambda x: x[2], reverse=True)

        cards = [
            _venue_create_to_card(v, distance_m=dist_m, explanations=explanations)
            for v, dist_m, _score, explanations in ranked[:max_results]
        ]
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
        provider_status = e.response.status_code if e.response else 0
        logger.error("Provider HTTP error in /recommend: %s", detail)
        raise _provider_error_response(detail, provider_status) from e
    except Exception as e:
        logger.error("Unexpected error in /recommend: %s", e)
        raise HTTPException(status_code=500, detail=f"Error fetching places: {str(e)}") from e


@app.get("/admin/jobs/summary", response_model=JobSummaryResponse)
async def admin_jobs_summary(session: AsyncSession = Depends(get_db)):
    """Return job counts grouped by status."""
    _require_admin_api()
    from app.services.jobs import get_job_summary

    counts = await get_job_summary(session)
    return JobSummaryResponse(counts=counts, total=sum(counts.values()))


@app.get("/admin/jobs", response_model=JobListResponse)
async def admin_list_jobs(
    session: AsyncSession = Depends(get_db),
    status: JobStatus | None = Query(None, description="Filter by job status"),
    job_type: JobType | None = Query(None, description="Filter by job type"),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
):
    """List background jobs with optional filters."""
    _require_admin_api()
    from app.services.jobs import list_jobs

    jobs, total = await list_jobs(
        session,
        status=status,
        job_type=job_type,
        limit=limit,
        offset=offset,
    )
    return JobListResponse(
        jobs=[JobResponse.model_validate(job) for job in jobs],
        total=total,
        limit=limit,
        offset=offset,
    )


@app.get("/admin/jobs/{job_id}", response_model=JobResponse)
async def admin_get_job(
    job_id: uuid.UUID,
    session: AsyncSession = Depends(get_db),
):
    """Return a single background job by ID."""
    _require_admin_api()
    from app.services.jobs import get_job_by_id

    job = await get_job_by_id(session, job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found")
    return JobResponse.model_validate(job)
