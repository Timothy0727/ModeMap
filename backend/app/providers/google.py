"""Google Places API client using Places API (New)."""

import logging

import httpx

from app.config import settings
from app.schemas.venue import VenueCreate

logger = logging.getLogger(__name__)


class GooglePlacesClient:
    """Client for Google Places API (New) using REST API with API key."""

    BASE_URL = "https://places.googleapis.com/v1/places:searchNearby"

    def __init__(self, api_key: str | None = None):
        """Initialize Google Places client.

        Args:
            api_key: Google Places API key. If None, uses settings.google_places_api_key
        """
        self.api_key = api_key or settings.google_places_api_key
        if not self.api_key:
            raise ValueError("Google Places API key is required. Set GOOGLE_PLACES_API_KEY in .env")

    async def search_nearby(
        self,
        lat: float,
        lng: float,
        radius_m: int = 1000,
        max_results: int = 20,
        open_now: bool = False,
        price_level: int | None = None,
        rank_preference: str | None = None,
    ) -> list[VenueCreate]:
        """Search for nearby places using Google Places API.

        Args:
            lat: Latitude
            lng: Longitude
            radius_m: Search radius in meters (max 50000, default 1000)
            max_results: Maximum number of results (default 20)
            open_now: Filter for places open now
            price_level: Filter by price level (0-4)
            keyword: Optional keyword search

        Returns:
            List of VenueCreate schemas

        Raises:
            httpx.HTTPError: If API request fails
            ValueError: If API key is missing or invalid parameters
        """
        if not self.api_key:
            raise ValueError("Google Places API key is required")

        if radius_m > 50000:
            raise ValueError("Radius cannot exceed 50000 meters")

        # Prepare request body
        body = {
            "includedTypes": [
                "restaurant",
                "cafe",
                "bar",
                "meal_takeaway",
                "meal_delivery",
                "bakery",
            ],
            "maxResultCount": min(max_results, 20),  # API limit is 20
            "locationRestriction": {
                "circle": {
                    "center": {"latitude": lat, "longitude": lng},
                    "radius": float(radius_m),
                }
            },
        }

        # Add optional filters
        if open_now:
            body["openNow"] = True

        if price_level is not None:
            if price_level < 0 or price_level > 4:
                raise ValueError("Price level must be between 0 and 4")
            price_map = {
                0: "PRICE_LEVEL_FREE",
                1: "PRICE_LEVEL_INEXPENSIVE",
                2: "PRICE_LEVEL_MODERATE",
                3: "PRICE_LEVEL_EXPENSIVE",
                4: "PRICE_LEVEL_VERY_EXPENSIVE",
            }
            body["priceLevel"] = price_map[price_level]

        if rank_preference:
            if rank_preference not in ["DISTANCE", "POPULARITY"]:
                raise ValueError("rank_preference must be 'DISTANCE' or 'POPULARITY'")
            body["rankPreference"] = rank_preference

        # Prepare headers
        headers = {
            "Content-Type": "application/json",
            "X-Goog-Api-Key": self.api_key,
            "X-Goog-FieldMask": (
                "places.id,"
                "places.displayName,"
                "places.location,"
                "places.rating,"
                "places.priceLevel,"
                "places.types,"
                "places.formattedAddress,"
                "places.currentOpeningHours,"
                "places.regularOpeningHours"
            ),
        }

        # Make API request
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.post(
                    self.BASE_URL,
                    json=body,
                    headers=headers,
                )
                response.raise_for_status()
                data = response.json()
        except httpx.HTTPStatusError as e:
            logger.error(f"Google Places API error: {e.response.status_code} - {e.response.text}")
            raise
        except httpx.RequestError as e:
            logger.error(f"Google Places API request error: {e}")
            raise

        # Normalize to VenueCreate schemas
        venues = []
        for place in data.get("places", []):
            venue = self._normalize_place(place)
            if venue:
                venues.append(venue)

        logger.info(f"Found {len(venues)} venues from Google Places API")
        return venues

    def _normalize_place(self, place: dict) -> VenueCreate | None:
        """Normalize Google Places API response to VenueCreate schema.

        Args:
            place: Place data from Google API

        Returns:
            VenueCreate instance or None if invalid
        """
        try:
            # Extract location
            location = place.get("location", {})
            lat = location.get("latitude")
            lng = location.get("longitude")

            if not lat or not lng:
                logger.warning(f"Place missing location: {place.get('id')}")
                return None

            # Extract name
            display_name = place.get("displayName", {})
            name = display_name.get("text", "")
            if not name:
                logger.warning(f"Place missing name: {place.get('id')}")
                return None

            # Extract categories from types
            types = place.get("types", [])
            # Filter out generic types and format
            excluded_types = {
                "establishment",
                "point_of_interest",
                "food",
                "store",
            }
            categories = [t.replace("_", " ").title() for t in types if t not in excluded_types][
                :5
            ]  # Limit to 5 categories

            # Map price level from Google format to 0-4 scale
            price_level = None
            price_str = place.get("priceLevel")
            if price_str:
                price_map = {
                    "PRICE_LEVEL_FREE": 0,
                    "PRICE_LEVEL_INEXPENSIVE": 1,
                    "PRICE_LEVEL_MODERATE": 2,
                    "PRICE_LEVEL_EXPENSIVE": 3,
                    "PRICE_LEVEL_VERY_EXPENSIVE": 4,
                }
                price_level = price_map.get(price_str)

            # Extract hours
            hours = None
            raw_hours = None

            # Try currentOpeningHours first, then regularOpeningHours
            opening_hours = place.get("currentOpeningHours") or place.get("regularOpeningHours")
            if opening_hours:
                weekday_text = opening_hours.get("weekdayText", [])
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
