# ModeMap

ModeMap is a **mode-aware nearby places recommender** that helps users find the *right* place based on intent, not just proximity.

Instead of returning a generic list of nearby venues, ModeMap lets users choose a **mode** (e.g. Work, Date, Quick Bite, Budget) and re-ranks places accordingly.

This repository currently contains **Step 1: Core data model + backend skeleton** (completed).

---

## MVP Scope (Locked)

### Supported Modes (MVP)
- **Work** — prioritize open-now, distance, and suitability for working
- **Date** — prioritize ratings, ambience proxy, and price
- **Quick Bite** — prioritize distance, open-now, and speed
- **Budget** — prioritize low price and value

### Explicitly Out of Scope (for MVP)
- Machine learning models
- Review text inference
- Personalization
- Async enrichment pipelines

All ranking logic is deterministic and rule-based in early stages.

---

## Tech Stack

### Backend
- Python 3.11
- FastAPI
- PostgreSQL (with SQLAlchemy async)
- Redis (configured, caching to be implemented)
- Alembic (database migrations)
- Docker + Docker Compose

### Frontend (Step 2 - in progress)
- Next.js
- Mapbox GL JS

### External APIs
- ✅ Google Places API (New) - integrated
- Mapbox (to be integrated in Step 2)

### Tooling
- Ruff (linting + formatting)
- Pytest
- GitHub Actions (CI)

---

## Repository Structure

```text
.
├── backend/
│   ├── app/
│   │   ├── main.py               # FastAPI app with test endpoints
│   │   ├── config.py             # Pydantic settings
│   │   ├── db/                   # Database setup
│   │   │   ├── base.py           # SQLAlchemy Base
│   │   │   └── session.py        # Async session factory
│   │   ├── models/               # SQLAlchemy models
│   │   │   ├── venue.py          # Venue + VenueProfile
│   │   │   └── user_event.py     # UserEvent
│   │   ├── schemas/              # Pydantic schemas
│   │   │   └── venue.py          # Request/response schemas
│   │   └── providers/            # External API providers
│   │       └── google.py         # Google Places API client
│   ├── alembic/                  # Database migrations
│   │   └── versions/             # Migration files
│   ├── tests/                    # Unit tests
│   │   ├── test_schemas.py       # Schema validation tests
│   │   └── test_google_places.py # Provider integration tests
│   ├── pyproject.toml
│   ├── requirements.txt
│   └── Dockerfile
frontend/                       # Step 2: Work in progress
│   ├── app/                    # Next.js App Router directory
│   │   ├── layout.tsx          # Root layout
│   │   ├── page.tsx            # Home page
│   │   └── globals.css         # Global styles
│   ├── lib/                    # Next.js App Router directory
│   │   ├── api.ts              # API client
│   ├── public/                 # Static assets
│   ├── .eslintrc.json          # ESLint config
│   ├── .gitignore              # Git ignore rules
│   ├── next.config.js          # Next.js config
│   ├── package.json            # Dependencies
│   ├── postcss.config.js       # PostCSS config (for Tailwind)
│   ├── tailwind.config.ts      # Tailwind config
│   └── tsconfig.json           # TypeScript config
├── .github/
│   └── workflows/
│       └── backend-ci.yml
├── docker-compose.yml
├── .env.example
├── .gitignore
└── README.md
```

## Implementation Progress

### ✅ Step 0 — Project setup + scope lock
- [x] MVP modes defined (Work, Date, Quick Bite, Budget)
- [x] Places + map APIs selected (Google Places, Mapbox)
- [x] Monorepo initialized
- [x] Docker Compose (API, Postgres, Redis)
- [x] Backend health + hello endpoints
- [x] Linting, testing, and CI configured

### ✅ Step 1 — Core data model + backend skeleton
- [x] Database models (Venue, VenueProfile, UserEvent)
- [x] Alembic migrations configured and initial migration created
- [x] Pydantic schemas for API request/response
- [x] Google Places API (New) client implemented
- [x] Test endpoint for provider integration (`/test/google-places`)
- [x] Unit tests for schemas and provider client
- [x] SQLAlchemy async session setup
- [ ] Redis caching (deferred to later steps)
- [ ] Geohash utilities (deferred to caching implementation)

### ⏳ Step 2 — MVP UI: Map + list + mode selector (in progress)
- [x] Initialize Next.js with TypeScript, Tailwind, App Router
- [x] Integrate Mapbox GL JS
- [x] Map component with navigation controls
- [x] API client for backend integration
- [x] Venue markers with popups on map
- [x] Basic venue list display
- [ ] Mode selector (Work, Date, Quick Bite, Budget)
- [ ] Basic filters (radius, open now, price)
- [ ] Detail panel for selected venue
- [ ] Map/list synchronization (click list → highlight marker)
- [ ] Responsive layout (desktop + mobile)

### 🔜 Step 3 — Real nearby retrieval + caching

### 🔜 Step 4 — Baseline ranking per mode

### 🔜 Step 5 — Reviews ingestion + text inference

### 🔜 Step 6 — Async jobs + enrichment orchestration

### 🔜 Step 7 — Mode-fit ranking + sliders

### 🔜 Step 8 — Free-text intent + vector search

### 🔜 Step 9 — Photo-based ambience (optional)

### 🔜 Step 10 — Feedback + personalization

### 🔜 Step 11 — Observability + evaluation

### 🔜 Step 12 — Demo + portfolio polish
