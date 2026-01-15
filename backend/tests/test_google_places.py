"""Unit tests for Google Places API client."""

from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from app.providers.google import GooglePlacesClient
from app.schemas.venue import VenueCreate


class TestGooglePlacesClient:
    """Tests for GooglePlacesClient."""

    def test_init_with_api_key(self):
        """Test initializing client with API key."""
        client = GooglePlacesClient(api_key="test_api_key")
        assert client.api_key == "test_api_key"

    def test_init_without_api_key_raises_error(self):
        """Test that initialization without API key raises ValueError."""
        with patch("app.providers.google.settings") as mock_settings:
            mock_settings.google_places_api_key = ""
            with pytest.raises(ValueError, match="Google Places API key is required"):
                GooglePlacesClient()

    def test_init_uses_settings_api_key(self):
        """Test that client uses settings API key when not provided."""
        with patch("app.providers.google.settings") as mock_settings:
            mock_settings.google_places_api_key = "settings_api_key"
            client = GooglePlacesClient()
            assert client.api_key == "settings_api_key"

    @pytest.mark.asyncio
    async def test_search_nearby_success(self):
        """Test successful nearby search."""
        mock_response_data = {
            "places": [
                {
                    "id": "ChIJN1t_tDeuEmsRUsoyG83frY4",
                    "displayName": {"text": "Blue Bottle Coffee"},
                    "location": {"latitude": 37.7749, "longitude": -122.4194},
                    "types": ["cafe", "coffee_shop", "establishment"],
                    "rating": 4.5,
                    "priceLevel": "PRICE_LEVEL_MODERATE",
                    "formattedAddress": "66 Mint St, San Francisco, CA",
                    "currentOpeningHours": {
                        "weekdayText": ["Monday: 7:00 AM – 6:00 PM"],
                        "openNow": True,
                    },
                }
            ]
        }

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = mock_response_data
        mock_response.raise_for_status = MagicMock()

        client = GooglePlacesClient(api_key="test_key")

        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client.__aenter__.return_value = mock_client
            mock_client.__aexit__.return_value = None
            mock_client.post = AsyncMock(return_value=mock_response)
            mock_client_class.return_value = mock_client

            venues = await client.search_nearby(lat=37.7749, lng=-122.4194, radius_m=1000)

            assert len(venues) == 1
            assert isinstance(venues[0], VenueCreate)
            assert venues[0].name == "Blue Bottle Coffee"
            assert venues[0].lat == 37.7749
            assert venues[0].rating == 4.5
            assert venues[0].price_level == 2  # PRICE_LEVEL_MODERATE maps to 2

    @pytest.mark.asyncio
    async def test_search_nearby_with_filters(self):
        """Test nearby search with optional filters."""
        mock_response_data = {"places": []}

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = mock_response_data
        mock_response.raise_for_status = MagicMock()

        client = GooglePlacesClient(api_key="test_key")

        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client.__aenter__.return_value = mock_client
            mock_client.__aexit__.return_value = None
            mock_client.post = AsyncMock(return_value=mock_response)
            mock_client_class.return_value = mock_client

            await client.search_nearby(
                lat=37.7749,
                lng=-122.4194,
                radius_m=500,
                max_results=10,
                open_now=True,
                price_level=2,
            )

            # Verify request body includes filters
            call_args = mock_client.post.call_args
            request_body = call_args[1]["json"]

            assert request_body["openNow"] is True
            assert request_body["priceLevel"] == "PRICE_LEVEL_MODERATE"
            assert request_body["maxResultCount"] == 10
            assert request_body["locationRestriction"]["circle"]["radius"] == 500

    @pytest.mark.asyncio
    async def test_search_nearby_radius_validation(self):
        """Test that radius exceeding 50000 raises ValueError."""
        client = GooglePlacesClient(api_key="test_key")

        with pytest.raises(ValueError, match="Radius cannot exceed 50000 meters"):
            await client.search_nearby(lat=37.7749, lng=-122.4194, radius_m=60000)

    @pytest.mark.asyncio
    async def test_search_nearby_price_level_validation(self):
        """Test that invalid price level raises ValueError."""
        client = GooglePlacesClient(api_key="test_key")

        with patch("httpx.AsyncClient"):
            with pytest.raises(ValueError, match="Price level must be between 0 and 4"):
                await client.search_nearby(lat=37.7749, lng=-122.4194, price_level=5)

    @pytest.mark.asyncio
    async def test_search_nearby_api_error(self):
        """Test handling of API errors."""
        mock_response = MagicMock()
        mock_response.status_code = 400
        mock_response.text = '{"error": {"message": "Invalid request"}}'
        mock_response.raise_for_status.side_effect = httpx.HTTPStatusError(
            "API Error", request=MagicMock(), response=mock_response
        )

        client = GooglePlacesClient(api_key="test_key")

        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client.__aenter__.return_value = mock_client
            mock_client.__aexit__.return_value = None
            mock_client.post = AsyncMock(return_value=mock_response)
            mock_client_class.return_value = mock_client

            with pytest.raises(httpx.HTTPStatusError):
                await client.search_nearby(lat=37.7749, lng=-122.4194)

    @pytest.mark.asyncio
    async def test_normalize_place_complete_data(self):
        """Test normalization with complete place data."""
        place_data = {
            "id": "ChIJN1t_tDeuEmsRUsoyG83frY4",
            "displayName": {"text": "Test Cafe"},
            "location": {"latitude": 37.7749, "longitude": -122.4194},
            "types": ["cafe", "coffee_shop", "establishment"],
            "rating": 4.5,
            "priceLevel": "PRICE_LEVEL_MODERATE",
            "formattedAddress": "123 Test St",
            "currentOpeningHours": {
                "weekdayText": ["Monday: 8:00 AM – 5:00 PM"],
                "openNow": True,
            },
        }

        client = GooglePlacesClient(api_key="test_key")
        venue = client._normalize_place(place_data)

        assert venue is not None
        assert isinstance(venue, VenueCreate)
        assert venue.name == "Test Cafe"
        assert venue.lat == 37.7749
        assert venue.lng == -122.4194
        assert venue.rating == 4.5
        assert venue.price_level == 2
        assert venue.address == "123 Test St"
        assert venue.hours is not None
        assert venue.hours["open_now"] is True

    @pytest.mark.asyncio
    async def test_normalize_place_missing_location(self):
        """Test normalization with missing location returns None."""
        place_data = {
            "id": "test_id",
            "displayName": {"text": "Test Place"},
            # Missing location
        }

        client = GooglePlacesClient(api_key="test_key")
        venue = client._normalize_place(place_data)

        assert venue is None

    @pytest.mark.asyncio
    async def test_normalize_place_missing_name(self):
        """Test normalization with missing name returns None."""
        place_data = {
            "id": "test_id",
            "location": {"latitude": 37.7749, "longitude": -122.4194},
            # Missing displayName
        }

        client = GooglePlacesClient(api_key="test_key")
        venue = client._normalize_place(place_data)

        assert venue is None

    @pytest.mark.asyncio
    async def test_normalize_place_filters_generic_types(self):
        """Test that generic types are filtered out from categories."""
        place_data = {
            "id": "test_id",
            "displayName": {"text": "Test Place"},
            "location": {"latitude": 37.7749, "longitude": -122.4194},
            "types": [
                "cafe",
                "establishment",
                "point_of_interest",
                "food",
                "store",
                "coffee_shop",
            ],
        }

        client = GooglePlacesClient(api_key="test_key")
        venue = client._normalize_place(place_data)

        assert venue is not None
        # Should only include cafe and coffee_shop, not generic types
        assert "establishment" not in venue.categories
        assert "point_of_interest" not in venue.categories
        assert "food" not in venue.categories
        assert "store" not in venue.categories
        assert "cafe" in [c.lower() for c in venue.categories]
        assert "coffee_shop" in [c.lower().replace(" ", "_") for c in venue.categories]

    @pytest.mark.asyncio
    async def test_normalize_place_price_level_mapping(self):
        """Test price level mapping from Google format to 0-4 scale."""
        price_levels = [
            ("PRICE_LEVEL_FREE", 0),
            ("PRICE_LEVEL_INEXPENSIVE", 1),
            ("PRICE_LEVEL_MODERATE", 2),
            ("PRICE_LEVEL_EXPENSIVE", 3),
            ("PRICE_LEVEL_VERY_EXPENSIVE", 4),
        ]

        client = GooglePlacesClient(api_key="test_key")

        for google_price, expected_level in price_levels:
            place_data = {
                "id": "test_id",
                "displayName": {"text": "Test Place"},
                "location": {"latitude": 37.7749, "longitude": -122.4194},
                "priceLevel": google_price,
            }

            venue = client._normalize_place(place_data)
            assert venue is not None
            assert venue.price_level == expected_level

    @pytest.mark.asyncio
    async def test_normalize_place_uses_regular_opening_hours_fallback(self):
        """Test that regularOpeningHours is used when currentOpeningHours is missing."""
        place_data = {
            "id": "test_id",
            "displayName": {"text": "Test Place"},
            "location": {"latitude": 37.7749, "longitude": -122.4194},
            "regularOpeningHours": {
                "weekdayText": ["Monday: 9:00 AM – 6:00 PM"],
                "openNow": False,
            },
        }

        client = GooglePlacesClient(api_key="test_key")
        venue = client._normalize_place(place_data)

        assert venue is not None
        assert venue.hours is not None
        assert venue.hours["open_now"] is False
        assert "Monday: 9:00 AM – 6:00 PM" in venue.hours["weekday_text"]
