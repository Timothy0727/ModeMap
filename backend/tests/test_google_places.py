"""Unit tests for Google Places API client."""

from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from app.providers.google import GooglePlacesClient
from app.schemas.venue import VenueCreate

SAMPLE_PLACE = {
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


def _make_mock_response(data: dict) -> MagicMock:
    resp = MagicMock()
    resp.status_code = 200
    resp.json.return_value = data
    resp.raise_for_status = MagicMock()
    return resp


def _mock_http_client(mock_response: MagicMock):
    """Return a patched httpx.AsyncClient context-manager mock."""
    mock_client = AsyncMock()
    mock_client.__aenter__.return_value = mock_client
    mock_client.__aexit__.return_value = None
    mock_client.post = AsyncMock(return_value=mock_response)
    return mock_client


class TestGooglePlacesClient:
    """Tests for GooglePlacesClient."""

    def test_init_with_api_key(self):
        client = GooglePlacesClient(api_key="test_api_key")
        assert client.api_key == "test_api_key"

    def test_init_without_api_key_raises_error(self):
        with patch("app.providers.google.settings") as mock_settings:
            mock_settings.google_places_api_key = ""
            with pytest.raises(ValueError, match="Google Places API key is required"):
                GooglePlacesClient()

    def test_init_uses_settings_api_key(self):
        with patch("app.providers.google.settings") as mock_settings:
            mock_settings.google_places_api_key = "settings_api_key"
            client = GooglePlacesClient()
            assert client.api_key == "settings_api_key"

    # ── text_search tests ──────────────────────────────────────

    @pytest.mark.asyncio
    async def test_text_search_success(self):
        """Single-page text search returns normalized venues."""
        mock_resp = _make_mock_response({"places": [SAMPLE_PLACE]})
        mock_client = _mock_http_client(mock_resp)

        client = GooglePlacesClient(api_key="test_key")

        with patch("httpx.AsyncClient", return_value=mock_client):
            venues = await client.text_search(
                text_query="cafe", lat=37.7749, lng=-122.4194, radius_m=1000,
            )

        assert len(venues) == 1
        assert isinstance(venues[0], VenueCreate)
        assert venues[0].name == "Blue Bottle Coffee"
        assert venues[0].rating == 4.5
        assert venues[0].price_level == 2

    @pytest.mark.asyncio
    async def test_text_search_request_body_filters(self):
        """Verify the request body sent to Google includes all filters."""
        mock_resp = _make_mock_response({"places": []})
        mock_client = _mock_http_client(mock_resp)

        client = GooglePlacesClient(api_key="test_key")

        with patch("httpx.AsyncClient", return_value=mock_client):
            await client.text_search(
                text_query="restaurant",
                lat=37.7749,
                lng=-122.4194,
                radius_m=500,
                included_type="restaurant",
                open_now=True,
                price_level=2,
                max_results=20,
            )

        body = mock_client.post.call_args[1]["json"]
        assert body["textQuery"] == "restaurant"
        assert body["openNow"] is True
        assert body["priceLevels"] == ["PRICE_LEVEL_MODERATE"]
        assert body["includedType"] == "restaurant"
        assert body["pageSize"] == 20
        assert body["locationBias"]["circle"]["radius"] == 500.0

    @pytest.mark.asyncio
    async def test_text_search_pagination(self):
        """Text search paginates up to 3 pages using nextPageToken."""
        page1 = {"places": [SAMPLE_PLACE], "nextPageToken": "token_page2"}
        page2_place = {**SAMPLE_PLACE, "id": "place_2", "displayName": {"text": "Venue 2"}}
        page2 = {"places": [page2_place], "nextPageToken": "token_page3"}
        page3_place = {**SAMPLE_PLACE, "id": "place_3", "displayName": {"text": "Venue 3"}}
        page3 = {"places": [page3_place]}

        responses = [
            _make_mock_response(page1),
            _make_mock_response(page2),
            _make_mock_response(page3),
        ]

        mock_client = AsyncMock()
        mock_client.__aenter__.return_value = mock_client
        mock_client.__aexit__.return_value = None
        mock_client.post = AsyncMock(side_effect=responses)

        client = GooglePlacesClient(api_key="test_key")

        with patch("httpx.AsyncClient", return_value=mock_client):
            venues = await client.text_search(
                text_query="cafe", lat=37.7749, lng=-122.4194, max_results=60,
            )

        assert len(venues) == 3
        assert mock_client.post.call_count == 3

        # Page 2+ requests must keep the original body and add pageToken
        second_call_body = mock_client.post.call_args_list[1][1]["json"]
        assert second_call_body.get("pageToken") == "token_page2"
        assert "locationBias" in second_call_body
        assert second_call_body["textQuery"] == "cafe"

    @pytest.mark.asyncio
    async def test_text_search_stops_when_max_results_reached(self):
        """Pagination stops once enough venues are collected."""
        page1 = {"places": [SAMPLE_PLACE], "nextPageToken": "token_page2"}
        mock_resp = _make_mock_response(page1)
        mock_client = _mock_http_client(mock_resp)

        client = GooglePlacesClient(api_key="test_key")

        with patch("httpx.AsyncClient", return_value=mock_client):
            venues = await client.text_search(
                text_query="cafe", lat=37.7749, lng=-122.4194, max_results=1,
            )

        assert len(venues) == 1
        assert mock_client.post.call_count == 1

    @pytest.mark.asyncio
    async def test_text_search_radius_validation(self):
        client = GooglePlacesClient(api_key="test_key")
        with pytest.raises(ValueError, match="Radius cannot exceed 50000 meters"):
            await client.text_search(
                text_query="cafe", lat=37.7749, lng=-122.4194, radius_m=60000,
            )

    @pytest.mark.asyncio
    async def test_text_search_price_level_validation(self):
        client = GooglePlacesClient(api_key="test_key")
        with pytest.raises(ValueError, match="Price level must be between 0 and 4"):
            await client.text_search(
                text_query="cafe", lat=37.7749, lng=-122.4194, price_level=5,
            )

    @pytest.mark.asyncio
    async def test_text_search_400_retries_without_filters(self):
        """On 400, text_search retries once without includedType/priceLevels."""
        err_resp = MagicMock()
        err_resp.status_code = 400
        err_resp.text = '{"error": {"message": "Invalid request"}}'
        err_resp.raise_for_status.side_effect = httpx.HTTPStatusError(
            "API Error", request=MagicMock(), response=err_resp,
        )

        ok_resp = _make_mock_response({"places": [SAMPLE_PLACE]})

        mock_client = AsyncMock()
        mock_client.__aenter__.return_value = mock_client
        mock_client.__aexit__.return_value = None
        mock_client.post = AsyncMock(side_effect=[err_resp, ok_resp])

        client = GooglePlacesClient(api_key="test_key")

        with patch("httpx.AsyncClient", return_value=mock_client):
            venues = await client.text_search(
                text_query="restaurant",
                lat=37.7749,
                lng=-122.4194,
                included_type="restaurant",
                price_level=2,
            )

        assert len(venues) == 1
        assert mock_client.post.call_count == 2

        # The fallback request should NOT have includedType or priceLevels
        fallback_body = mock_client.post.call_args_list[1][1]["json"]
        assert "includedType" not in fallback_body
        assert "priceLevels" not in fallback_body
        assert fallback_body["textQuery"] == "restaurant"

    @pytest.mark.asyncio
    async def test_text_search_non_400_error_raises_immediately(self):
        """Non-400 errors (e.g. 500, 403) are raised without retry."""
        err_resp = MagicMock()
        err_resp.status_code = 403
        err_resp.text = '{"error": {"message": "Forbidden"}}'
        err_resp.raise_for_status.side_effect = httpx.HTTPStatusError(
            "Forbidden", request=MagicMock(), response=err_resp,
        )

        mock_client = _mock_http_client(err_resp)
        client = GooglePlacesClient(api_key="test_key")

        with patch("httpx.AsyncClient", return_value=mock_client):
            with pytest.raises(httpx.HTTPStatusError):
                await client.text_search(
                    text_query="cafe", lat=37.7749, lng=-122.4194,
                )

        assert mock_client.post.call_count == 1

    @pytest.mark.asyncio
    async def test_text_search_400_fallback_also_fails(self):
        """If the fallback also returns 400, the error propagates."""
        err_resp = MagicMock()
        err_resp.status_code = 400
        err_resp.text = '{"error": {"message": "Bad request"}}'
        err_resp.raise_for_status.side_effect = httpx.HTTPStatusError(
            "Bad request", request=MagicMock(), response=err_resp,
        )

        mock_client = AsyncMock()
        mock_client.__aenter__.return_value = mock_client
        mock_client.__aexit__.return_value = None
        mock_client.post = AsyncMock(side_effect=[err_resp, err_resp])

        client = GooglePlacesClient(api_key="test_key")

        with patch("httpx.AsyncClient", return_value=mock_client):
            with pytest.raises(httpx.HTTPStatusError):
                await client.text_search(
                    text_query="restaurant",
                    lat=37.7749,
                    lng=-122.4194,
                    included_type="restaurant",
                    price_level=2,
                )

        assert mock_client.post.call_count == 2

    # ── search_nearby (legacy wrapper) ─────────────────────────

    @pytest.mark.asyncio
    async def test_search_nearby_delegates_to_text_search(self):
        """Legacy search_nearby delegates to text_search."""
        mock_resp = _make_mock_response({"places": [SAMPLE_PLACE]})
        mock_client = _mock_http_client(mock_resp)
        client = GooglePlacesClient(api_key="test_key")

        with patch("httpx.AsyncClient", return_value=mock_client):
            venues = await client.search_nearby(lat=37.7749, lng=-122.4194, radius_m=1000)

        assert len(venues) == 1
        body = mock_client.post.call_args[1]["json"]
        assert "textQuery" in body

    # ── _normalize_place tests ─────────────────────────────────

    def test_normalize_place_complete_data(self):
        client = GooglePlacesClient(api_key="test_key")
        venue = client._normalize_place(SAMPLE_PLACE)

        assert venue is not None
        assert isinstance(venue, VenueCreate)
        assert venue.name == "Blue Bottle Coffee"
        assert venue.lat == 37.7749
        assert venue.lng == -122.4194
        assert venue.rating == 4.5
        assert venue.price_level == 2
        assert venue.address == "66 Mint St, San Francisco, CA"
        assert venue.hours is not None
        assert venue.hours["open_now"] is True

    def test_normalize_place_missing_location(self):
        place = {"id": "test_id", "displayName": {"text": "Test Place"}}
        client = GooglePlacesClient(api_key="test_key")
        assert client._normalize_place(place) is None

    def test_normalize_place_missing_name(self):
        place = {"id": "test_id", "location": {"latitude": 37.7749, "longitude": -122.4194}}
        client = GooglePlacesClient(api_key="test_key")
        assert client._normalize_place(place) is None

    def test_normalize_place_filters_generic_types(self):
        place = {
            "id": "test_id",
            "displayName": {"text": "Test Place"},
            "location": {"latitude": 37.7749, "longitude": -122.4194},
            "types": ["cafe", "establishment", "point_of_interest", "food", "store", "coffee_shop"],
        }
        client = GooglePlacesClient(api_key="test_key")
        venue = client._normalize_place(place)

        assert venue is not None
        lower_cats = [c.lower() for c in venue.categories]
        assert "establishment" not in lower_cats
        assert "point of interest" not in lower_cats
        assert "food" not in lower_cats
        assert "store" not in lower_cats
        assert "cafe" in lower_cats

    def test_normalize_place_price_level_mapping(self):
        price_levels = [
            ("PRICE_LEVEL_FREE", 0),
            ("PRICE_LEVEL_INEXPENSIVE", 1),
            ("PRICE_LEVEL_MODERATE", 2),
            ("PRICE_LEVEL_EXPENSIVE", 3),
            ("PRICE_LEVEL_VERY_EXPENSIVE", 4),
        ]
        client = GooglePlacesClient(api_key="test_key")

        for google_price, expected in price_levels:
            place = {
                "id": "test_id",
                "displayName": {"text": "Test Place"},
                "location": {"latitude": 37.7749, "longitude": -122.4194},
                "priceLevel": google_price,
            }
            venue = client._normalize_place(place)
            assert venue is not None
            assert venue.price_level == expected

    def test_normalize_place_regular_opening_hours_fallback(self):
        place = {
            "id": "test_id",
            "displayName": {"text": "Test Place"},
            "location": {"latitude": 37.7749, "longitude": -122.4194},
            "regularOpeningHours": {
                "weekdayText": ["Monday: 9:00 AM – 6:00 PM"],
                "openNow": False,
            },
        }
        client = GooglePlacesClient(api_key="test_key")
        venue = client._normalize_place(place)

        assert venue is not None
        assert venue.hours is not None
        assert venue.hours["open_now"] is False
        assert "Monday: 9:00 AM – 6:00 PM" in venue.hours["weekday_text"]
