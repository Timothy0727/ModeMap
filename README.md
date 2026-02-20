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
- Machine learning models
- Review text inference
- Personalization
- Async enrichment pipelines

All ranking logic is deterministic and rule-based in early stages.

---

## Tech Stack

### Backend
- Python 3.11+
- FastAPI
- PostgreSQL (with SQLAlchemy async)
- Redis (configured, caching to be implemented)
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
docker-compose up -d
```

This starts:
- **PostgreSQL** on port `5433`
- **Redis** on port `6379`
- **FastAPI** on port `8000` (with hot reload)

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

**Example:**

```
GET /recommend?mode=work&lat=37.7749&lng=-122.4194&radius=2000&open_now=true
```

**Response shape:**

```json
{
  "meta": {
    "mode": "work",
    "radius": 2000,
    "total_results": 60,
    "returned_results": 60,
    "cache_hit": null,
    "time_taken_ms": null
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
      "rating": 4.5,
      "price_level": 2,
      "hours": { "weekday_text": [...], "open_now": true },
      "raw_hours": "Monday: 7:00 AM – 6:00 PM\n...",
      "explanations": []
    }
  ]
}
```

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
│   │   ├── main.py               # FastAPI app, /recommend endpoint, mode-to-query mapping
│   │   ├── config.py             # Pydantic settings
│   │   ├── db/                   # Database setup
│   │   │   ├── base.py           # SQLAlchemy Base
│   │   │   └── session.py        # Async session factory
│   │   ├── models/               # SQLAlchemy models
│   │   │   ├── venue.py          # Venue + VenueProfile
│   │   │   └── user_event.py     # UserEvent + Mode/EventType enums
│   │   ├── schemas/              # Pydantic schemas
│   │   │   ├── venue.py          # VenueCreate / VenueRead
│   │   │   └── recommend.py      # RecommendRequest, RecommendResponse, VenueCard, RecommendMeta
│   │   └── providers/            # External API providers
│   │       └── google.py         # Google Places Text Search client (paginated, with fallback)
│   ├── alembic/                  # Database migrations
│   │   └── versions/
│   ├── tests/
│   │   ├── test_google_places.py # Provider + pagination + fallback tests
│   │   ├── test_schemas.py       # Schema validation tests
│   │   └── test_smoke.py         # Health endpoint smoke test
│   ├── pyproject.toml
│   ├── requirements.txt
│   └── Dockerfile
├── frontend/
│   ├── app/
│   │   ├── layout.tsx            # Root layout
│   │   ├── page.tsx              # Home page (mode, filters, map, list)
│   │   └── globals.css           # Global styles
│   ├── components/
│   │   ├── Map.tsx               # Mapbox GL map with venue markers
│   │   ├── ModeSelector.tsx      # Mode chip selector (Work, Date, Quick Bite, Budget)
│   │   └── Filters.tsx           # Radius slider, Open Now toggle, Price chips
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

Current ranking is a simple sort by rating (descending, nulls last) then distance (ascending). Mode-specific scoring functions are planned for Step 4.

### GPU-rendered map markers (GeoJSON layers)

The map originally used DOM-based Mapbox markers (one HTML element per venue). This caused visible lag during pan/zoom with 60 markers. The implementation now uses **GeoJSON sources with circle + symbol layers**, which are rendered entirely on the GPU. Marker selection state, rank labels, and hover popups are all driven through GeoJSON feature properties and data-driven styling expressions.

### Map initialization stability

`Map.tsx` stores `initialCenter` and `initialZoom` in `useRef` to prevent the map initialization `useEffect` from re-firing when the parent re-renders. The map is created exactly once on mount (empty dependency array) and data updates flow through a separate `useEffect` that watches `venues`, `selectedVenueId`, and `mapReady`.

---

## Implementation Progress

### Step 0 — Project setup + scope lock
- [x] MVP modes defined (Work, Date, Quick Bite, Budget)
- [x] Places + map APIs selected (Google Places, Mapbox)
- [x] Monorepo initialized
- [x] Docker Compose (API, Postgres, Redis)
- [x] Backend health + hello endpoints
- [x] Linting, testing, and CI configured

### Step 1 — Core data model + backend skeleton
- [x] Database models (Venue, VenueProfile, UserEvent)
- [x] Alembic migrations configured and initial migration created
- [x] Pydantic schemas for API request/response
- [x] Google Places API (New) client implemented
- [x] Test endpoint for provider integration (`/test/google-places`)
- [x] Unit tests for schemas and provider client
- [x] SQLAlchemy async session setup
- [ ] Redis caching (deferred to later steps)
- [ ] Geohash utilities (deferred to caching implementation)

### Step 2 — MVP UI: Map + list + mode selector (in progress)
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
- [ ] Detail panel for selected venue (planned for Step 7)

### Step 3 — Real nearby retrieval + caching

### Step 4 — Baseline ranking per mode

### Step 5 — Reviews ingestion + text inference

### Step 6 — Async jobs + enrichment orchestration

### Step 7 — Mode-fit ranking + sliders

### Step 8 — Free-text intent + vector search

### Step 9 — Photo-based ambience (optional)

### Step 10 — Feedback + personalization

### Step 11 — Observability + evaluation

### Step 12 — Demo + portfolio polish
