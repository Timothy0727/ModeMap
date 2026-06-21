# ModeMap

ModeMap is a **mode-aware nearby places recommender** that helps users find the *right* place based on intent, not just proximity.

Instead of returning a generic list of nearby venues, ModeMap lets users choose a **mode** (e.g. Work, Date, Quick Bite, Budget) and re-ranks places accordingly. Each venue comes with explanation bullets describing *why* it matches the selected mode.

---

## MVP Scope (Locked)

### Supported Modes
| Mode | Intent | Example query sent to Google |
|------|--------|------------------------------|
| **Work** | Quiet cafes, coworking spots with wifi | `"quiet cafe or coworking space with wifi"` |
| **Date** | Romantic restaurants, bars for a date | `"romantic restaurant or bar for a date"` |
| **Quick Bite** | Fast casual, grab-and-go | `"quick food or fast casual restaurant"` |
| **Budget** | Cheap eats, high-value spots | `"affordable restaurant or cheap eats"` |

### Explicitly Out of Scope (for MVP)
- Machine learning models (Hugging Face classifiers/embeddings — Step 7+)
- Personalization
- Frontend job status dashboard (admin JSON API only for Step 6)

Heuristic review-based attribute inference (keyword rules, no ML) is in scope as of **Step 5**. Background Celery enrichment orchestration is in scope as of **Step 6**. All ranking logic remains deterministic and rule-based in early stages.

---

## Tech Stack

### Backend
- Python 3.11+
- FastAPI
- PostgreSQL (with SQLAlchemy async)
- Redis (cache for /recommend responses; see Step 3)
- Alembic (database migrations)
- Docker + Docker Compose

### Frontend
- Next.js 14 + TypeScript
- Mapbox GL JS (interactive map)
- Tailwind CSS

### External APIs
- Google Places API (New) — **Text Search** endpoint with pagination (up to 60 results)
- Mapbox GL JS (map rendering)

### Tooling
- Ruff (linting + formatting)
- Pytest + pytest-asyncio
- GitHub Actions (CI)

---

## Getting Started

### Prerequisites
- Docker & Docker Compose
- Node.js 18+
- A Google Places API key (with Places API (New) enabled)
- A Mapbox access token

### 1. Clone and configure environment

```bash
git clone <repo-url>
cd ModeMap
cp .env.example .env
```

Edit `.env` and fill in your API keys:

```
GOOGLE_PLACES_API_KEY=your_google_api_key
```

Create `frontend/.env.local`:

```
NEXT_PUBLIC_MAPBOX_TOKEN=your_mapbox_token
NEXT_PUBLIC_API_URL=http://localhost:8000
```

### 2. Start the backend (Docker)

```bash
docker compose up -d --build
```

If you previously ran the optional worker (or upgraded from an older compose file), remove stale containers first:

```bash
docker compose down --remove-orphans
docker compose up -d --build
```

This builds the **api** image from `backend/Dockerfile` and starts:
- **PostgreSQL** on port `5433`
- **Redis** on port `6379`
- **FastAPI** on port `8000` (with hot reload)

The **Celery worker** is optional (Step 6) and is not started by default. To include it:

```bash
docker compose --profile worker up -d --build
```

Verify the backend is running:

```bash
curl http://localhost:8000/health
# → {"status": "ok"}
```

### 3. Start the frontend

```bash
cd frontend
npm install
npm run dev
```

Open [http://localhost:3000](http://localhost:3000) in your browser.

### 4. Run backend tests

```bash
cd backend
pip install -r requirements.txt
pytest -v
```

You can also run subsets of tests using markers (configured in `backend/pyproject.toml`):

```bash
cd backend
pytest -m provider -v
pytest -m schemas -v
pytest -m smoke -v
pytest -m cache -v
pytest -m recommend_cache -v
pytest -m rate_limit -v
pytest -m retry -v
pytest -m enrichment -v
```

To measure cache, retry, and rate-limit impact (no Google API key required):

```bash
cd backend
python scripts/measure_improvements.py
```

---

## API Reference

### `GET /health`
Health check.

**Response:** `{"status": "ok"}`

### `GET /recommend`

Returns ranked nearby venues for the given mode and filters.

**Query parameters:**

| Param | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| `mode` | string | yes | — | One of: `work`, `date`, `quick_bite`, `budget` |
| `lat` | float | yes | — | Latitude (-90 to 90) |
| `lng` | float | yes | — | Longitude (-180 to 180) |
| `radius` | int | no | `1000` | Search radius in meters (100–50000) |
| `open_now` | bool | no | `false` | Only return venues currently open |
| `price` | int | no | — | Price level filter (0–4). Omit for any price. |
| `max_results` | int | no | `60` | Maximum venues to return (1–60) |
| `cache` | int | no | `1` | `1` = use Redis cache; `0` = bypass (for benchmarking) |

**Example:**

```
GET /recommend?mode=work&lat=37.7749&lng=-122.4194&radius=2000&open_now=true
```

**Response shape:**

- `meta.cache_hit`: `true` if the response was served from Redis cache, `false` on cache miss.
- `meta.time_taken_ms`: Server-side latency in milliseconds.
- Each venue includes `distance_m`: distance from the query location in meters (Haversine).

```json
{
  "meta": {
    "mode": "work",
    "radius": 2000,
    "total_results": 60,
    "returned_results": 60,
    "cache_hit": false,
    "time_taken_ms": 450
  },
  "venues": [
    {
      "id": "ChIJ...",
      "provider_id": "ChIJ...",
      "provider_name": "google",
      "name": "Blue Bottle Coffee",
      "categories": ["Coffee Shop", "Cafe"],
      "lat": 37.7749,
      "lng": -122.4194,
      "address": "66 Mint St, San Francisco, CA",
      "distance_m": 850.3,
      "rating": 4.5,
      "price_level": 2,
      "hours": { "weekday_text": [...], "open_now": true },
      "raw_hours": "Monday: 7:00 AM – 6:00 PM\n...",
      "explanations": ["Within 450 m", "Open now", "Highly rated (4.5)"]
    }
  ]
}
```

### `GET /venues/{provider_id}/profile`

Return (and if needed, compute) heuristic attribute scores for a venue.

**Path parameter:** `provider_id` — Google Places place ID (same as `venues[].provider_id` from `/recommend`).

**Behavior:**
- On cache miss from `/recommend`, venues are upserted into Postgres in the background.
- This endpoint fetches review snippets from Google Places, runs keyword heuristics, and upserts a `VenueProfile`.
- If a profile exists and is younger than the TTL (7 days), returns it without re-fetching reviews.

**Response shape:**

```json
{
  "id": "uuid",
  "venue_id": "uuid",
  "attribute_scores": {
    "quiet": 0.67,
    "laptop_friendly": 0.5,
    "romantic": 0.33
  },
  "evidence_snippets": {
    "quiet": ["Great spot for studying, very peaceful atmosphere."],
    "laptop_friendly": ["Reliable wifi and plenty of outlets."]
  },
  "embedding_ref": null,
  "profiled_at": "2026-06-19T12:00:00Z",
  "expires_at": "2026-06-26T12:00:00Z"
}
```

**Canonical attributes:** `quiet`, `noisy`, `laptop_friendly`, `romantic`, `fast_service`, `value` (scores 0–1; omitted when no signal).

### `GET /test/google-places`

Debug endpoint for raw Google Places integration.

| Param | Type | Default |
|-------|------|---------|
| `lat` | float | `37.7749` |
| `lng` | float | `-122.4194` |
| `radius` | int | `1000` |

---

## Repository Structure

```text
.
├── backend/
│   ├── app/
│   │   ├── main.py               # FastAPI app, /recommend (cache, rate limit, retry), mode-to-query mapping
│   │   ├── config.py             # Pydantic settings (DB, Redis, cache TTL, Google API key)
│   │   ├── cache.py              # Redis cache: cache key, get_cached_recommend, set_cached_recommend
│   │   ├── db/                   # Database setup
│   │   │   ├── base.py           # SQLAlchemy Base
│   │   │   └── session.py        # Async session factory
│   │   ├── models/               # SQLAlchemy models
│   │   │   ├── venue.py          # Venue + VenueProfile
│   │   │   └── user_event.py     # UserEvent + Mode/EventType enums
│   │   ├── ranking/              # Mode-specific scoring + explanations (Step 4)
│   │   ├── text_attributes/      # Keyword heuristics for review inference (Step 5)
│   │   ├── services/             # Enrichment + venue persistence (Step 5)
│   │   ├── schemas/              # Pydantic schemas
│   │   │   ├── venue.py          # VenueCreate / VenueRead
│   │   │   └── recommend.py      # RecommendRequest, RecommendResponse, VenueCard (incl. distance_m), RecommendMeta
│   │   └── providers/            # External API providers
│   │       └── google.py         # Google Places Text Search + review/details fetch
│   ├── alembic/                  # Database migrations
│   │   └── versions/
│   ├── scripts/
│   │   └── measure_improvements.py  # Measures cache, retry, and rate-limit impact (no real API key needed)
│   ├── tests/
│   │   ├── test_cache.py         # Cache key + Redis get/set (marker: cache)
│   │   ├── test_recommend_rate_limit_and_retry.py  # Rate limit, retry, cache hit (markers: rate_limit, retry, recommend_cache)
│   │   ├── test_google_places.py # Provider + pagination + fallback (marker: provider)
│   │   ├── test_ranking.py       # Mode-specific ranking + explanations (Step 4)
│   │   ├── test_text_attributes_heuristics.py  # Review heuristic inference (Step 5)
│   │   ├── test_enrichment.py    # Profile enrichment + venue upsert (Step 5, marker: enrichment)
│   │   ├── test_schemas.py       # Schema validation (marker: schemas)
│   │   └── test_smoke.py         # Health endpoint (marker: smoke)
│   ├── pyproject.toml           # Pytest markers for test subsets
│   ├── requirements.txt
│   └── Dockerfile
├── frontend/
│   ├── app/
│   │   ├── layout.tsx            # Root layout
│   │   ├── page.tsx              # Home page (mode, filters, map, list)
│   │   └── globals.css           # Global styles
│   ├── components/
│   │   ├── Map.tsx               # Mapbox GL map with venue markers (GeoJSON layers)
│   │   ├── ModeSelector.tsx      # Mode chip selector (Work, Date, Quick Bite, Budget)
│   │   ├── Filters.tsx           # Radius slider, Open Now toggle, Price chips
│   │   ├── VenueList.tsx         # Ranked list with distance, open/closed badge
│   │   └── VenueDetailPanel.tsx  # Detail panel for selected venue (rating, price, distance, open status)
│   ├── lib/
│   │   └── api.ts                # API client (recommend, searchVenues, healthCheck)
│   ├── package.json
│   ├── tailwind.config.ts
│   └── tsconfig.json
├── .github/
│   └── workflows/
│       ├── backend-ci.yml        # CI: ruff lint + pytest
│       └── frontend-ci.yml       # CI: lint + type-check + build
├── docker-compose.yml            # Postgres, Redis, FastAPI, Celery worker
├── .env.example
├── .gitignore
└── README.md
```

---

## Architecture Decisions

### Google Places Text Search (New) over Nearby Search

The backend uses the **Text Search (New)** endpoint (`places:searchText`) rather than Nearby Search. This was chosen because:

1. **`openNow` filter is supported** — Nearby Search silently ignores `openNow`, making "open now" filtering impossible server-side.
2. **Natural-language queries** — Text Search accepts descriptive queries like `"quiet cafe with wifi"`, which improves relevance for mode-based recommendations.
3. **Pagination** — Text Search supports `nextPageToken` for up to 3 pages (60 results), giving the ranking engine more candidates to work with.

### Dual-query strategy

Each mode has two query strings:
- A **descriptive query** (e.g. `"romantic restaurant or bar for a date"`) used when no strict filters are set.
- A **simple query** (e.g. `"restaurant"`) used when `price` or `open_now` filters are active, to avoid conflicts between natural-language queries and Google's structured filters.

### Fallback on filter conflicts

If Google returns HTTP 400 (e.g. due to `includedType` + `priceLevels` conflict), the provider **retries once** without `includedType` and `priceLevels`, allowing the `textQuery` alone to drive results. Non-400 errors (403, 500) are not retried.

### Dummy ranking (Step 2)

Step 2 started with a simple sort by rating (descending) then distance (ascending). As of **Step 4**, ranking is **mode-specific** (Work/Date/Quick Bite/Budget) and each venue includes 2–3 explanation bullets derived from the scoring factors.

### GPU-rendered map markers (GeoJSON layers)

The map originally used DOM-based Mapbox markers (one HTML element per venue). This caused visible lag during pan/zoom with 60 markers. The implementation now uses **GeoJSON sources with circle + symbol layers**, which are rendered entirely on the GPU. Marker selection state, rank labels, and hover popups are all driven through GeoJSON feature properties and data-driven styling expressions.

### Map initialization stability

`Map.tsx` stores `initialCenter` and `initialZoom` in `useRef` to prevent the map initialization `useEffect` from re-firing when the parent re-renders. The map is created exactly once on mount (empty dependency array) and data updates flow through a separate `useEffect` that watches `venues`, `selectedVenueId`, and `mapReady`.

### Caching (Step 3)

- **Cache key:** Geohash (precision 6) + radius bucket (500–50000 m) + 15‑minute time bucket + mode + `open_now` + price. Same key → same cached response; radius bucket avoids fragmenting cache for similar radii.
- **TTL:** 15 minutes (`recommend_cache_ttl_seconds`). Optional bypass with `cache=0` for benchmarking.
- **Storage:** Full `RecommendResponse` JSON in Redis; get/set on cache hit/miss; errors log and degrade (miss).

### Rate limiting and retry (Step 3)

- **Rate limit:** `slowapi` with `60/minute` per client IP on `/recommend`; responses over limit return 429.
- **Retry:** Inline loop in the handler: up to 3 attempts on provider 5xx or 429; backoff 1s, 2s, 4s. Client errors (e.g. 400) are not retried. On final failure the handler returns 502.

---

## Implementation Progress

### Step 0 — Project setup + scope lock
**Delivered:** Monorepo with backend (FastAPI) and frontend (Next.js); Docker Compose for Postgres, Redis, and API; health and hello endpoints; linting (Ruff), formatting, and CI (GitHub Actions).

- [x] MVP modes defined (Work, Date, Quick Bite, Budget)
- [x] Places + map APIs selected (Google Places, Mapbox)
- [x] Monorepo initialized
- [x] Docker Compose (API, Postgres, Redis)
- [x] Backend health + hello endpoints
- [x] Linting, testing, and CI configured

### Step 1 — Core data model + backend skeleton
**Delivered:** SQLAlchemy models (Venue, VenueProfile, UserEvent) and Alembic migrations; Pydantic request/response schemas; Google Places API (New) client with pagination and fallback; test endpoint and unit tests. Redis and geohash are used for caching in Step 3.

- [x] Database models (Venue, VenueProfile, UserEvent)
- [x] Alembic migrations configured and initial migration created
- [x] Pydantic schemas for API request/response
- [x] Google Places API (New) client implemented
- [x] Test endpoint for provider integration (`/test/google-places`)
- [x] Unit tests for schemas and provider client
- [x] SQLAlchemy async session setup
- [x] Redis and geohash used for caching (implemented in Step 3)

### Step 2 — MVP UI: Map + list + mode selector
**Delivered:** Next.js app with Mapbox map, ranked venue list, mode chips, and filters (radius, open now, price). Map and list stay in sync; GPU-rendered GeoJSON markers; detail panel for selected venue. Wired to `/recommend` with dummy ranking (rating, then distance).

- [x] Initialize Next.js with TypeScript, Tailwind, App Router
- [x] Integrate Mapbox GL JS with venue markers and popups
- [x] `/recommend` endpoint with request/response schemas
- [x] Frontend API client (`recommend()`) with TypeScript types
- [x] Mode selector component (Work, Date, Quick Bite, Budget chips)
- [x] Filters: radius slider (100 m–50 km), Open Now toggle, Price chips (Any, $–$$$$)
- [x] Switched provider from Nearby Search to **Text Search (New)** with `openNow` support
- [x] Pagination via `nextPageToken` — up to 60 results per request
- [x] Dual-query strategy (descriptive vs simple) to avoid filter conflicts
- [x] Fallback retry on Google 400 errors (drops `includedType`/`priceLevels`)
- [x] Dummy ranking (rating desc, distance asc)
- [x] Venue list with rank numbers and price indicators
- [x] Map/list synchronization (click list → highlight marker, click marker → scroll + highlight list)
- [x] Selected venue flyTo camera animation
- [x] GPU-rendered markers via GeoJSON layers (circle + symbol) for smooth performance
- [x] Hover popups with venue details (rank, name, rating, price, categories, address)
- [x] Responsive side-by-side layout (map + list on desktop, stacked on mobile)
- [x] Detail panel for selected venue (name, rating, price, address, distance, open/closed)

### Step 3 — Real nearby retrieval + caching + “Open now”
**Delivered:** Redis-backed response cache keyed by location (geohash), radius bucket, time bucket, mode, and filters; real distance (Haversine) and radius/open-now filtering; rate limiting (60/min) and retry/backoff for provider errors; tests and a measurement script for cache, retry, and rate-limit behavior.

- [x] **Cache key strategy** — Key includes geohash tile (precision 6), radius bucket (500–50000 m), 15‑minute time bucket, mode, `open_now`, and price. Implemented in `app/cache.py` (`build_recommend_cache_key`).
- [x] **Redis layer** — `get_cached_recommend` / `set_cached_recommend` with configurable TTL (`recommend_cache_ttl_seconds`, default 15 min). Cache bypass via `cache=0` query param for benchmarking.
- [x] **Wiring into `/recommend`** — On cache hit return stored response with `meta.cache_hit=true` and `meta.time_taken_ms`; on miss call provider, build response, then store and return with `meta.cache_hit=false`.
- [x] **Real distance** — Haversine distance from query (lat, lng) to each venue; stored as `distance_m` on each venue card. Venues filtered to `distance_m <= radius`.
- [x] **“Open now”** — Backend filters to venues where `hours.open_now` is true (or hours missing). Radius phrase in text query (“within X km/m”) and post-filter by distance and open status.
- [x] **Rate limiting** — `slowapi` with `60/minute` per IP on `/recommend`; 429 when exceeded.
- [x] **Retry/backoff** — Inline loop: up to 3 attempts for provider 5xx/429; delays 1s, 2s, 4s; 400 not retried. Provider errors surfaced as 502.
- [x] **Tests** — `tests/test_cache.py` (cache key, Redis get/set roundtrip); `tests/test_recommend_rate_limit_and_retry.py` (rate limit, retry, cache hit on second request). Markers: `cache`, `recommend_cache`, `rate_limit`, `retry`.
- [x] **Measurement script** — `backend/scripts/measure_improvements.py` measures cache latency (uncached vs cached), retry success rate vs single attempt, and rate-limit 200 vs 429 counts.

### Step 4 — Baseline ranking per mode

**Delivered:** Deterministic, rule-based mode scoring (Work/Date/Quick Bite/Budget) with **2–3 “Why this matches”** explanation bullets per venue.

- [x] **Ranking module** — `backend/app/ranking/scoring.py` exports `score_and_explain(venue, distance_m, radius_m, mode) -> (score, explanations)`.
- [x] **Mode-specific scoring (baseline)** — Uses a weighted sum of normalized factors:
  - **Quick Bite:** prioritize distance + open_now, then rating, slight price preference
  - **Work:** prioritize open_now, then distance, then rating (attribute signals come later in Step 7)
  - **Date:** prioritize rating + distance + mid-range price preference
  - **Budget:** prioritize low price + “value” (rating × cheapness), then distance
- [x] **Explanations tied to the score** — Bullets are selected from the top contributing scoring factors (e.g. “Within 450 m”, “Open now”, “Highly rated (4.6)”, “Budget-friendly”, “Great value”, “Mid-range pricing”).
- [x] **Wired into `/recommend`** — `backend/app/main.py` scores each candidate venue, sorts by score, and includes `explanations` on each `VenueCard`.
- [x] **Unit tests** — `backend/tests/test_ranking.py` covers deterministic output, mode-specific ordering properties, explanation behavior, and edge cases (missing rating/price/hours).

**Scoring details:** See `backend/app/ranking/README.md` for the exact normalization and per-mode equations.

### Step 5 — Reviews ingestion + text inference

**Delivered:** Deterministic heuristic enrichment from Google review snippets — no ML. Venues from `/recommend` are persisted to Postgres; profiles are built on demand via the profile endpoint and shown in the detail panel.

- [x] **VenueProfile storage** — Reuses `attribute_scores`, `evidence_snippets`, `profiled_at`, `expires_at` on `venue_profiles` (initial migration).
- [x] **Review ingestion** — `GooglePlacesClient.fetch_place_reviews()` and `fetch_place_details()` return bounded `ReviewSnippet` texts (reviews + editorial summary, max 10, truncated to 300 chars).
- [x] **Heuristic pipeline** — `infer_attributes_from_text()` in `backend/app/text_attributes/heuristics.py` scores `quiet`, `noisy`, `laptop_friendly`, `romantic`, `fast_service`, `value` using positive/negative keyword rules.
- [x] **Enrichment service** — `enrich_venue_profile(provider_id, session)` upserts profiles with 7-day TTL; skips re-inference when fresh.
- [x] **Venue persistence from `/recommend`** — Background upsert on cache miss via `upsert_venues_from_provider()` so enrichment can find venues without an extra Details call.
- [x] **Read API** — `GET /venues/{provider_id}/profile` returns `VenueProfileResponse`.
- [x] **UI** — `VenueDetailPanel` fetches profile and shows “Vibe” tags (score ≥ 40%) with evidence tooltips on hover.
- [x] **Tests** — `test_text_attributes_heuristics.py` (unit) and `test_enrichment.py` (service-level with mocked provider + Postgres).

**Scoring formula:** `score = pos_count / (pos_count + neg_count + 1)` per attribute. See attribute rules in `backend/app/text_attributes/heuristics.py`.

**Manual test (local):**

```bash
# 1. Start stack
docker compose up -d --build

# 2. Run Step 5 tests (requires Postgres on :5433)
cd backend && python3 -m pytest tests/test_text_attributes_heuristics.py tests/test_enrichment.py -v

# 3. Get a provider_id from /recommend, then fetch profile
curl -s "http://localhost:8000/recommend?mode=work&lat=37.7749&lng=-122.4194&radius=1000&cache=0" | python3 -c "import sys,json; v=json.load(sys.stdin)['venues'][0]; print(v['provider_id'])"
curl -s "http://localhost:8000/venues/<provider_id>/profile" | python3 -m json.tool
```

### Step 6 — Async jobs + enrichment orchestration

**Delivered:** Celery + Redis background jobs wrap the existing enrichment service. `/recommend` schedules enrichment non-blockingly; job lifecycle is tracked in Postgres with admin visibility.

- [x] **Job model + migration** — `jobs` table with `job_type`, `status`, `attempts`, `idempotency_key`, timestamps; partial unique index on active jobs.
- [x] **Celery app** — `app/worker/celery_app.py` + `app/worker/tasks.py` with `enrich_venue`, `batch_enrich_area`, `refresh_stale_profiles` tasks.
- [x] **Job service** — `schedule_enrich_venue()` with Redis enqueue locks, idempotency dedup, fresh-profile skip.
- [x] **`/recommend` orchestration** — Background scheduling after venue fetch; response unchanged (no profiles on hot path).
- [x] **Profile endpoint** — Sync enrichment preserved for detail panel UX; also enqueues background job when stale.
- [x] **Admin API** — `GET /admin/jobs`, `GET /admin/jobs/{id}`, `GET /admin/jobs/summary` (gated by `ADMIN_API_ENABLED`).
- [x] **Docker worker profile** — `docker compose --profile worker up` starts Celery worker + Beat.
- [x] **Tests** — `test_jobs.py`, `test_admin_jobs.py`, `test_recommend_enrichment_schedule.py`.

**Manual test (local):**

```bash
# 1. Start stack with worker
docker compose --profile worker up -d --build

# 2. Apply migration (if not auto-applied)
cd backend && alembic upgrade head

# 3. Trigger recommend (schedules jobs)
curl -s "http://localhost:8000/recommend?mode=work&lat=37.7749&lng=-122.4194&radius=1000&cache=0" > /dev/null

# 4. Check admin
curl -s "http://localhost:8000/admin/jobs/summary" | python3 -m json.tool
curl -s "http://localhost:8000/admin/jobs?status=COMPLETED" | python3 -m json.tool

# 5. Profile should be warm on fetch
curl -s "http://localhost:8000/recommend?mode=work&lat=37.7749&lng=-122.4194&radius=1000&cache=0" | python3 -c "import sys,json; v=json.load(sys.stdin)['venues'][0]; print(v['provider_id'])"
curl -s "http://localhost:8000/venues/<provider_id>/profile" | python3 -m json.tool
```

### Step 7 — Mode-fit ranking + sliders

### Step 8 — Free-text intent + vector search

### Step 9 — Photo-based ambience (optional)

### Step 10 — Feedback + personalization

### Step 11 — Observability + evaluation

### Step 12 — Demo + portfolio polish
