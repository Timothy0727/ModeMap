"""FastAPI application main module."""

from fastapi import Depends, FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware

from app.models.user_event import Mode
from app.schemas.recommend import RecommendMeta, RecommendRequest, RecommendResponse, VenueCard
from app.schemas.venue import VenueCreate

MODE_PLACE_TYPES: dict[Mode, list[str]] = {
    Mode.WORK: [
        "cafe",
        "coffee_shop",
        "library",
        "internet_cafe",
    ],
    Mode.DATE: [
        "restaurant",
        "fine_dining_restaurant",
        "bar",
        "wine_bar",
        "cafe",
        "steak_house",
        "sushi_restaurant",
    ],
    Mode.QUICK_BITE: [
        "fast_food_restaurant",
        "cafe",
        "coffee_shop",
        "bakery",
        "sandwich_shop",
        "pizza_restaurant",
        "diner",
        "donut_shop",
        "meal_takeaway",
    ],
    Mode.BUDGET: [
        "restaurant",
        "cafe",
        "fast_food_restaurant",
        "meal_takeaway",
        "bakery",
        "diner",
        "pizza_restaurant",
        "sandwich_shop",
    ],
}

# Default place types when mode has no mapping (fallback for provider)
_DEFAULT_PLACE_TYPES = [
    "restaurant",
    "cafe",
    "bar",
    "meal_takeaway",
    "meal_delivery",
    "bakery",
]


def _distance_sq(center_lat: float, center_lng: float, lat: float, lng: float) -> float:
    """Squared distance (proxy for ordering: smaller = closer)."""
    return (lat - center_lat) ** 2 + (lng - center_lng) ** 2


def _venue_create_to_card(v: VenueCreate) -> VenueCard:
    """Convert VenueCreate to VenueCard with stable id and placeholder explanations."""
    return VenueCard(
        id=v.provider_id,
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
    params: RecommendRequest = Depends(get_recommend_params),
    max_results: int = Query(20, ge=1, le=20, description="Max venues to return"),
):
    """Return ranked nearby venues for the given mode and filters."""
    try:
        from app.providers import GooglePlacesClient

        include_types = MODE_PLACE_TYPES.get(params.mode, _DEFAULT_PLACE_TYPES)

        client = GooglePlacesClient()
        venues = await client.search_nearby(
            lat=params.lat,
            lng=params.lng,
            radius_m=params.radius,
            open_now=params.open_now,
            price_level=params.price,
            max_results=max_results,
            include_types=include_types,
        )

        # Dummy ranking: rating (desc, None last) then distance (asc)
        def sort_key(v: VenueCreate) -> tuple:
            rating = -(v.rating if v.rating is not None else -1)  # None last
            dist_sq = _distance_sq(params.lat, params.lng, v.lat, v.lng)
            return (rating, dist_sq)

        venues = sorted(venues, key=sort_key)

        cards = [_venue_create_to_card(v) for v in venues]
        total = len(cards)

        meta = RecommendMeta(
            mode=params.mode,
            radius=params.radius,
            total_results=total,
            returned_results=total,
            cache_hit=None,
            time_taken_ms=None,
        )
        return RecommendResponse(meta=meta, venues=cards)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error fetching places: {str(e)}") from e
