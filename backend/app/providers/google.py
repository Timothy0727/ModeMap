"""Google Places API client using Text Search (New)."""

import logging
from dataclasses import dataclass

import httpx

from app.config import settings
from app.schemas.venue import VenueCreate

logger = logging.getLogger(__name__)

FIELD_MASK = (
    "places.id,"
    "places.displayName,"
    "places.location,"
    "places.rating,"
    "places.priceLevel,"
    "places.types,"
    "places.formattedAddress,"
    "places.currentOpeningHours,"
    "places.regularOpeningHours,"
    "nextPageToken"
)

# Field mask for Place Details (single place lookup — no "places." prefix)
DETAILS_FIELD_MASK = (
    "id,"
    "displayName,"
    "location,"
    "rating,"
    "priceLevel,"
    "types,"
    "formattedAddress,"
    "currentOpeningHours,"
    "regularOpeningHours"
)

# Field mask for fetching review text and editorial summary only
REVIEWS_FIELD_MASK = "reviews,editorialSummary"


@dataclass
class ReviewSnippet:
    """A single text snippet from a venue's reviews or editorial summary."""

    text: str
    rating: float | None = None

PRICE_INT_TO_API = {
    0: "PRICE_LEVEL_FREE",
    1: "PRICE_LEVEL_INEXPENSIVE",
    2: "PRICE_LEVEL_MODERATE",
    3: "PRICE_LEVEL_EXPENSIVE",
    4: "PRICE_LEVEL_VERY_EXPENSIVE",
}

PRICE_API_TO_INT = {v: k for k, v in PRICE_INT_TO_API.items()}


class GooglePlacesClient:
    """Client for Google Places API (New) — Text Search endpoint."""

    TEXT_SEARCH_URL = "https://places.googleapis.com/v1/places:searchText"

    def __init__(self, api_key: str | None = None):
        self.api_key = api_key or settings.google_places_api_key
        if not self.api_key:
            raise ValueError("Google Places API key is required. Set GOOGLE_PLACES_API_KEY in .env")

    async def text_search(
        self,
        text_query: str,
        lat: float,
        lng: float,
        radius_m: int = 1000,
        included_type: str | None = None,
        open_now: bool = False,
        price_level: int | None = None,
        max_results: int = 20,
    ) -> list[VenueCreate]:
        """Search for places via Text Search (New), paginating up to 60.

        If Google rejects the request (HTTP 400) the method retries once with a
        simplified body (drops ``includedType`` and ``priceLevels``) so that
        conflicting filter combinations degrade gracefully instead of returning
        an error to the user.

        Args:
            text_query: Required search string (e.g. "cafe", "restaurant").
            lat: Center latitude for location bias.
            lng: Center longitude for location bias.
            radius_m: Bias radius in meters (max 50000).
            included_type: Single Table A type filter (e.g. "cafe").
            open_now: If True, only return places currently open.
            price_level: Price level filter (0-4), or None for any.
            max_results: Maximum total venues to return (up to 60).

        Returns:
            List of VenueCreate schemas.
        """
        if radius_m > 50000:
            raise ValueError("Radius cannot exceed 50000 meters")

        if price_level is not None and (price_level < 0 or price_level > 4):
            raise ValueError("Price level must be between 0 and 4")

        body = self._build_body(
            text_query,
            lat,
            lng,
            radius_m,
            included_type,
            open_now,
            price_level,
        )
        headers = {
            "Content-Type": "application/json",
            "X-Goog-Api-Key": self.api_key,
            "X-Goog-FieldMask": FIELD_MASK,
        }

        try:
            return await self._paginated_fetch(body, headers, max_results)
        except httpx.HTTPStatusError as first_err:
            if first_err.response.status_code != 400:
                raise

            # Retry with a stripped-down body (no includedType / priceLevels)
            logger.warning("Text Search returned 400; retrying without includedType/priceLevels")
            fallback_body = self._build_body(
                text_query,
                lat,
                lng,
                radius_m,
                included_type=None,
                open_now=open_now,
                price_level=None,
            )
            return await self._paginated_fetch(fallback_body, headers, max_results)

    # ── private helpers ────────────────────────────────────────

    @staticmethod
    def _build_body(
        text_query: str,
        lat: float,
        lng: float,
        radius_m: int,
        included_type: str | None,
        open_now: bool,
        price_level: int | None,
    ) -> dict:
        body: dict = {
            "textQuery": text_query,
            "locationBias": {
                "circle": {
                    "center": {"latitude": lat, "longitude": lng},
                    "radius": float(radius_m),
                }
            },
            "pageSize": 20,
        }

        if included_type:
            body["includedType"] = included_type
        if open_now:
            body["openNow"] = True
        if price_level is not None:
            body["priceLevels"] = [PRICE_INT_TO_API[price_level]]

        return body

    async def _paginated_fetch(
        self,
        body: dict,
        headers: dict,
        max_results: int,
    ) -> list[VenueCreate]:
        venues: list[VenueCreate] = []
        max_pages = min((max_results + 19) // 20, 3)

        async with httpx.AsyncClient(timeout=10.0) as client:
            for page in range(max_pages):
                request_body = dict(body)
                try:
                    response = await client.post(
                        self.TEXT_SEARCH_URL,
                        json=request_body,
                        headers=headers,
                    )
                    response.raise_for_status()
                    data = response.json()
                except httpx.HTTPStatusError as e:
                    logger.error(
                        "Google Text Search API error (page %d): %d - %s",
                        page,
                        e.response.status_code,
                        e.response.text,
                    )
                    raise
                except httpx.RequestError as e:
                    logger.error("Google Text Search API request error: %s", e)
                    raise

                for place in data.get("places", []):
                    venue = self._normalize_place(place)
                    if venue:
                        venues.append(venue)

                next_token = data.get("nextPageToken")
                if not next_token or len(venues) >= max_results:
                    break

                body["pageToken"] = next_token

        venues = venues[:max_results]
        logger.info(
            "Text Search returned %d venues across %d page(s)",
            len(venues),
            page + 1,
        )
        return venues

    async def fetch_place_details(self, provider_place_id: str) -> VenueCreate | None:
        """Fetch basic venue details for a single place by its provider ID.

        Uses the Place Details (New) endpoint:
          GET https://places.googleapis.com/v1/places/{place_id}

        Args:
            provider_place_id: The Google Places place ID.

        Returns:
            VenueCreate schema on success, or None if the place can't be normalized.
        """
        url = f"https://places.googleapis.com/v1/places/{provider_place_id}"
        headers = {
            "X-Goog-Api-Key": self.api_key,
            "X-Goog-FieldMask": DETAILS_FIELD_MASK,
        }
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(url, headers=headers)
            response.raise_for_status()
            data = response.json()
        return self._normalize_place(data)

    async def fetch_place_reviews(
        self,
        provider_place_id: str,
        max_snippets: int = 10,
    ) -> list[ReviewSnippet]:
        """Fetch review snippets and editorial summary for a single place.

        Returns up to ``max_snippets`` short text excerpts suitable for
        heuristic attribute inference.  The editorial summary (when present)
        is prepended so it is always considered by the pipeline.

        Args:
            provider_place_id: The Google Places place ID.
            max_snippets: Maximum total snippets to return.

        Returns:
            List of ReviewSnippet objects (may be empty if none are available).
        """
        url = f"https://places.googleapis.com/v1/places/{provider_place_id}"
        headers = {
            "X-Goog-Api-Key": self.api_key,
            "X-Goog-FieldMask": REVIEWS_FIELD_MASK,
        }
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(url, headers=headers)
            response.raise_for_status()
            data = response.json()

        snippets: list[ReviewSnippet] = []

        # Editorial summary (one per place, no rating)
        editorial = data.get("editorialSummary") or {}
        editorial_text = editorial.get("text", "").strip()
        if editorial_text:
            snippets.append(ReviewSnippet(text=editorial_text[:300]))

        # Review texts (up to 5 from Google)
        for review in data.get("reviews", []):
            text_obj = review.get("text") or {}
            text = (text_obj.get("text") or "").strip() if isinstance(text_obj, dict) else ""
            if not text:
                continue
            rating = review.get("rating")
            snippets.append(ReviewSnippet(text=text[:300], rating=rating))
            if len(snippets) >= max_snippets:
                break

        logger.debug(
            "fetch_place_reviews(%s): %d snippets returned", provider_place_id, len(snippets)
        )
        return snippets[:max_snippets]

    # Keep backward-compatible alias for test endpoint
    async def search_nearby(
        self,
        lat: float,
        lng: float,
        radius_m: int = 1000,
        max_results: int = 20,
        include_types: list[str] | None = None,
        open_now: bool = False,
        price_level: int | None = None,
        rank_preference: str | None = None,
    ) -> list[VenueCreate]:
        """Legacy wrapper: delegates to text_search for backward compatibility."""
        text_query = "restaurant"
        included_type = include_types[0] if include_types else None
        return await self.text_search(
            text_query=text_query,
            lat=lat,
            lng=lng,
            radius_m=radius_m,
            included_type=included_type,
            open_now=open_now,
            price_level=price_level,
            max_results=max_results,
        )

    def _normalize_place(self, place: dict) -> VenueCreate | None:
        """Normalize a Google Places response object to VenueCreate."""
        try:
            location = place.get("location", {})
            lat = location.get("latitude")
            lng = location.get("longitude")

            if not lat or not lng:
                logger.warning(f"Place missing location: {place.get('id')}")
                return None

            display_name = place.get("displayName", {})
            name = display_name.get("text", "")
            if not name:
                logger.warning(f"Place missing name: {place.get('id')}")
                return None

            types = place.get("types", [])
            excluded_types = {"establishment", "point_of_interest", "food", "store"}
            categories = [t.replace("_", " ").title() for t in types if t not in excluded_types][:5]

            price_level = None
            price_str = place.get("priceLevel")
            if price_str:
                price_level = PRICE_API_TO_INT.get(price_str)

            hours = None
            raw_hours = None
            opening_hours = place.get("currentOpeningHours") or place.get("regularOpeningHours")
            if opening_hours:
                weekday_text = opening_hours.get("weekdayDescriptions", [])
                if weekday_text:
                    raw_hours = "\n".join(weekday_text)
                    hours = {
                        "weekday_text": weekday_text,
                        "open_now": opening_hours.get("openNow", False),
                        "periods": opening_hours.get("periods", []),
                    }

            return VenueCreate(
                provider_id=place.get("id", ""),
                provider_name="google",
                name=name,
                categories=categories,
                lat=lat,
                lng=lng,
                address=place.get("formattedAddress"),
                rating=place.get("rating"),
                price_level=price_level,
                hours=hours,
                raw_hours=raw_hours,
            )
        except Exception as e:
            logger.error(f"Error normalizing place {place.get('id', 'unknown')}: {e}")
            return None
