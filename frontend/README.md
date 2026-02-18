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
│   └── Filters.tsx          # Radius slider, Open Now toggle, Price level chips
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
Mapbox GL JS map that renders venue markers from the `venues` prop. Each marker shows a popup with the venue name and rating on hover/click.

## API Client (`lib/api.ts`)

### `recommend(params)`
Calls `GET /recommend` with mode, location, radius, and filters. Returns up to 60 ranked venues.

### Types
- `Mode` — `"work" | "date" | "quick_bite" | "budget"`
- `RecommendParams` — request parameters
- `RecommendVenue` — venue card with categories, rating, price, hours, explanations
- `RecommendResponse` — `{ meta, venues }`

## State Management

State lives in the home page component (`app/page.tsx`):
- `mode` — selected recommendation mode
- `radius` / `debouncedRadius` — search radius with 300ms debounce
- `openNow` — open-now filter
- `price` — price level filter (`undefined` = any)
- `venues` — current recommendation results
- `loading` / `error` — request status

Changing any filter triggers a new `recommend()` call via `useEffect` + `useCallback`.
