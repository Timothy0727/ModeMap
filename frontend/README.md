# ModeMap Frontend

Next.js frontend for ModeMap — a mode-aware nearby places recommender.

## Setup

### Prerequisites
- Node.js 18+
- Backend running on `http://localhost:8000` (see root README)

### Environment variables

Create `.env.local`:

```
NEXT_PUBLIC_MAPBOX_TOKEN=your_mapbox_access_token
NEXT_PUBLIC_API_URL=http://localhost:8000
```

### Install and run

```bash
npm install
npm run dev
```

Open [http://localhost:3000](http://localhost:3000).

## Project Structure

```text
frontend/
├── app/
│   ├── layout.tsx           # Root layout (fonts, metadata)
│   ├── page.tsx             # Home page — mode selector, filters, map, venue list
│   └── globals.css          # Tailwind global styles
├── components/
│   ├── Map.tsx              # Mapbox GL JS map with venue markers and popups
│   ├── ModeSelector.tsx     # Mode chip selector (Work, Date, Quick Bite, Budget)
│   ├── Filters.tsx          # Radius slider, Open Now toggle, Price level chips
│   ├── VenueDetailPanel.tsx # Full venue detail view (replaces list when selected)
│   └── VenueList.tsx        # Venue list shared by desktop column and mobile drawer
├── hooks/
│   └── useRecommend.ts      # Presenter hook: state, recommend() call, handlers
├── lib/
│   └── api.ts               # API client — recommend(), types, healthCheck()
├── public/                  # Static assets
├── package.json
├── tailwind.config.ts
└── tsconfig.json
```

## Components

### `ModeSelector`
Four chip buttons for selecting the recommendation mode. Controlled via `mode` / `onModeChange` props.

### `Filters`
- **Radius**: Range slider, 100 m to 50 km
- **Open Now**: Checkbox toggle
- **Price**: Chip buttons — Any, $, $$, $$$, $$$$

### `Map`
Mapbox GL JS map that renders venue markers using **GeoJSON sources with circle + symbol layers** (GPU-rendered for smooth performance with up to 60 markers). Features:
- **Ranked markers** — each marker displays its rank number via a symbol layer.
- **Data-driven selection** — the selected marker turns red and grows larger, driven by a `selected` GeoJSON property.
- **Hover popups** — hovering a marker shows a popup with rank, name, rating, price, categories, and address.
- **Click → select** — clicking a marker calls `onMarkerClick`, which toggles selection in the parent.
- **flyTo animation** — selecting a venue smoothly pans/zooms the camera to center it.

### `VenueDetailPanel`
Full detail view for a selected venue, shown in the right column in place of the venue list. Displays:
- Rank badge, full name, rating, price level, open/closed status badge
- All category tags
- Full address with a Google Maps directions link
- Weekly hours schedule (parsed from `hours.weekday_text` or `raw_hours` fallback)
- "Why this matches" explanation bullets (placeholder for Step 4 scoring)
- "Back to list" button to deselect and return to the venue list

Props: `venue`, `rank`, `onClose`.

## API Client (`lib/api.ts`)

### `recommend(params)`
Calls `GET /recommend` with mode, location, radius, and filters. Returns up to 60 ranked venues.

### Types
- `Mode` — `"work" | "date" | "quick_bite" | "budget"`
- `RecommendParams` — request parameters
- `RecommendVenue` — venue card with categories, rating, price, hours, explanations
- `RecommendResponse` — `{ meta, venues }`

## State Management (MVP Presenter pattern)

Recommendation state and API logic live in **`hooks/useRecommend.ts`**. The hook owns:
- `mode`, `radius`, `openNow`, `price` (with 300ms debounce on radius)
- `venues`, `loading`, `error`
- `selectedVenueId`, `selectedVenue`, `selectedRank`
- `snap` / `setSnap` for the mobile bottom sheet
- Handlers: `onModeChange`, `onRadiusChange`, `onOpenNowChange`, `onPriceChange`, `onVenueSelect`, `onCloseDetail`

The home page (`app/page.tsx`) is a **thin View**: it calls `useRecommend()`, composes the right-column content (list vs detail panel), and renders layout + children from the returned props. No API calls or business logic in the page. This keeps testability high and sets up Step 10 (feedback) cleanly.
