# ModeMap

ModeMap is a **mode-aware nearby places recommender** that helps users find the *right* place based on intent, not just proximity.

Instead of returning a generic list of nearby venues, ModeMap lets users choose a **mode** (e.g. Work, Date, Quick Bite, Budget) and re-ranks places accordingly.

This repository currently contains **Step 0: Project setup + scope lock**.

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

## Tech Stack (Step 0)

### Backend
- Python 3.11
- FastAPI
- PostgreSQL
- Redis
- Docker + Docker Compose

### Frontend (planned)
- Next.js
- Mapbox GL JS

### External APIs (chosen, not yet integrated)
- Google Places API
- Mapbox

### Tooling
- Ruff (linting + formatting)
- Pytest
- GitHub Actions (CI)

---

## Repository Structure (current)

```text
.
├── backend/
│   ├── app/
│   │   └── main.py
│   ├── tests/
│   ├── pyproject.toml
│   ├── requirements.txt
│   └── Dockerfile
├── frontend/
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

### ⏳ Step 1 — Core data model + backend skeleton
- [ ] In progress

### 🔜 Step 2 — MVP UI: Map + list + mode selector

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
