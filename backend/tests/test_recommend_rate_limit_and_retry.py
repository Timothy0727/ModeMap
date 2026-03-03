import httpx
from fastapi.testclient import TestClient

from app.main import app
from app.schemas.recommend import RecommendResponse


def _make_recommend_url(**overrides: str) -> str:
    """Build a /recommend URL with sane defaults, allowing overrides."""
    params = {
        "mode": "work",
        "lat": "37.7749",
        "lng": "-122.4194",
        "radius": "1000",
        "open_now": "false",
        "max_results": "1",
        "cache": "0",  # bypass Redis for tests
    }
    params.update(overrides)
    query = "&".join(f"{k}={v}" for k, v in params.items())
    return f"/recommend?{query}"


def test_recommend_rate_limit_per_ip(monkeypatch):
    """Rate limiting: more than 60/minute per IP should return 429."""

    # Ensure limiter is enabled for this test.
    app.state.limiter.enabled = True

    class DummyClient:
        def __init__(self, *args, **kwargs) -> None:  # pragma: no cover - trivial
            pass

        async def text_search(self, *args, **kwargs):
            # Always return an empty list quickly; we only care about rate limiting.
            return []

    monkeypatch.setattr("app.providers.GooglePlacesClient", DummyClient)

    client = TestClient(app)
    url = _make_recommend_url()

    # First 60 requests should be allowed.
    for _ in range(60):
        resp = client.get(url)
        assert resp.status_code == 200

    # 61st request within the same window should hit the rate limit.
    resp = client.get(url)
    assert resp.status_code == 429


def test_recommend_retries_on_server_error(monkeypatch):
    """Retry/backoff: 5xx errors should be retried with backoff and eventually succeed."""

    # Disable limiter so rate limiting does not interfere with retry behavior.
    app.state.limiter.enabled = False

    class FlakyClient:
        calls = 0

        def __init__(self, *args, **kwargs) -> None:  # pragma: no cover - trivial
            pass

        async def text_search(self, *args, **kwargs):
            FlakyClient.calls += 1
            if FlakyClient.calls < 3:
                # Simulate a 500 from the provider.
                response = httpx.Response(
                    status_code=500,
                    request=httpx.Request("POST", "https://example.com"),
                )
                raise httpx.HTTPStatusError(
                    "server error", request=response.request, response=response
                )
            # Third attempt succeeds.
            return []

    monkeypatch.setattr("app.providers.GooglePlacesClient", FlakyClient)
    FlakyClient.calls = 0

    client = TestClient(app)
    resp = client.get(_make_recommend_url())

    assert resp.status_code == 200
    assert FlakyClient.calls == 3


def test_recommend_does_not_retry_on_400(monkeypatch):
    """Retry/backoff: 400 errors should not be retried (single attempt)."""

    # Disable limiter so rate limiting does not interfere with retry behavior.
    app.state.limiter.enabled = False

    class BadRequestClient:
        calls = 0

        def __init__(self, *args, **kwargs) -> None:  # pragma: no cover - trivial
            pass

        async def text_search(self, *args, **kwargs):
            BadRequestClient.calls += 1
            response = httpx.Response(
                status_code=400,
                request=httpx.Request("POST", "https://example.com"),
            )
            raise httpx.HTTPStatusError("bad request", request=response.request, response=response)

    monkeypatch.setattr("app.providers.GooglePlacesClient", BadRequestClient)
    BadRequestClient.calls = 0

    client = TestClient(app)
    resp = client.get(_make_recommend_url())

    # The handler converts provider HTTPStatusError to a 502 for the client.
    assert resp.status_code == 502
    # Only one provider call should have been made; no retries on 400.
    assert BadRequestClient.calls == 1


def test_recommend_cache_hit_second_request(monkeypatch):
    """Integration: first /recommend call misses cache; second call (same params) returns cache_hit=True."""

    app.state.limiter.enabled = False

    from app.schemas.venue import VenueCreate

    # In-memory cache for this test so we don't need Redis.
    cache_store = {}

    async def mock_get(cache_key: str):
        data = cache_store.get(cache_key)
        if data is None:
            return None
        return RecommendResponse.model_validate_json(data)

    async def mock_set(cache_key: str, response: RecommendResponse, ttl_seconds: int):
        cache_store[cache_key] = response.model_dump_json()

    monkeypatch.setattr("app.main.get_cached_recommend", mock_get)
    monkeypatch.setattr("app.main.set_cached_recommend", mock_set)

    # Mock provider: return one venue so first request has something to cache.
    one_venue = VenueCreate(
        provider_id="place_1",
        provider_name="google",
        name="Test Cafe",
        categories=["cafe"],
        lat=37.7749,
        lng=-122.4194,
        address="123 Test St",
        rating=4.5,
        price_level=2,
        hours=None,
        raw_hours=None,
    )

    class OneVenueClient:
        def __init__(self, *args, **kwargs):
            pass

        async def text_search(self, *args, **kwargs):
            return [one_venue]

    monkeypatch.setattr("app.providers.GooglePlacesClient", OneVenueClient)

    client = TestClient(app)
    url = _make_recommend_url(cache="1")  # use cache

    # First request: cache miss → provider called → response stored → cache_hit=False.
    resp1 = client.get(url)
    assert resp1.status_code == 200
    data1 = resp1.json()
    assert data1["meta"]["cache_hit"] is False
    assert len(data1["venues"]) == 1

    # Second request: same params → cache hit → cache_hit=True, no extra provider call.
    resp2 = client.get(url)
    assert resp2.status_code == 200
    data2 = resp2.json()
    assert data2["meta"]["cache_hit"] is True
    assert len(data2["venues"]) == 1
    assert data2["venues"][0]["name"] == "Test Cafe"
