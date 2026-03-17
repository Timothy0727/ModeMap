# Ranking Module — How It Works

This module ranks nearby venues per **mode** (Work, Date, Quick Bite, Budget) using rule-based scoring. Every venue gets a **score** (higher = better) and **2–3 explanation bullets** derived from the factors that contributed most to that score.

---

## 1. Inputs

For each venue we use:

- **Venue fields**: `rating` (0–5 or missing), `price_level` (0–4 or missing), `hours` (with `open_now` when known).
- **Request context**: `distance_m` (from user location), `radius` (search radius in meters), `mode`, and whether the user asked for **open now** and/or a specific **price** level.

We do **not** use inferred attributes (quiet, laptop-friendly, etc.) here; those are added in Step 7 after enrichment.

---

## 2. Normalized Components (0–1, higher = better)

All raw inputs are turned into **components** in `[0, 1]` so we can combine them with weights.

| Component        | Formula | Meaning |
|-----------------|--------|--------|
| **distance_score** | `max(0, 1 - distance_m / radius)` | Closer venues score higher. At 0 m → 1; at `radius` m → 0. |
| **rating_norm**    | `(rating or 0) / 5` | 5★ → 1, 0★ → 0. Missing rating treated as 0. |
| **open_score**     | `1` if venue is open now, else `0` | From `hours["open_now"]`. Unknown (no hours) → 0 so we don’t falsely claim “open now”. |
| **price_low_score** | `1 - (price_level or 2) / 4` | Lower price = higher score. $ → 1, $$$$ → 0. Missing → 0.5 (mid). |
| **mid_price_score** | `1 - |(price_level or 2) - 2| / 2` | Mid-range (1–2) best; 2 → 1, 1 or 3 → 0.5, 0 or 4 → 0. Used for Date. |
| **value_score**    | `rating_norm * price_low_score` | Good rating and low price = “good value”. |

---

## 3. Mode-Specific Equation

Each mode uses a **weighted sum** of the components above. Weights are chosen so the mode’s priorities are clear and ordering is stable.

### Quick Bite

- **Goal**: Close, open now, decent rating, slightly prefer cheaper.
- **Formula**:  
  `score = 0.40 * distance_score + 0.30 * open_score + 0.22 * rating_norm + 0.08 * price_low_score`
- **Effect**: Distance and “open now” dominate; rating matters; price has a small effect.

### Work

- **Goal**: Must be open now, then close, then good rating. (Later Step 7 adds quiet / laptop-friendly.)
- **Formula**:  
  `score = 0.50 * open_score + 0.30 * distance_score + 0.20 * rating_norm`
- **Effect**: Open now is the main differentiator; then proximity; then rating.

### Date

- **Goal**: Nice rating, not too far, mid-range price (not cheap, not splurge).
- **Formula**:  
  `score = 0.50 * rating_norm + 0.25 * distance_score + 0.25 * mid_price_score`
- **Effect**: Rating and “not far” and “mid-range” balance.

### Budget

- **Goal**: Low price and good value (rating per dollar).
- **Formula**:  
  `score = 0.50 * price_low_score + 0.35 * value_score + 0.15 * distance_score`
- **Effect**: Cheap and high value dominate; distance still matters a bit.

---

## 4. Explanation Generation

Explanations must **match actual scoring factors** (no generic or made-up reasons).

1. **Per-venue**: We compute the **contribution** of each factor (e.g. `0.40 * distance_score` for Quick Bite distance).
2. We keep a short **label** and optional **numeric detail** per factor (e.g. “distance”, “Within 200 m”).
3. We take the **top 2–3 factors by contribution** and turn them into user-facing bullets, e.g.:
   - “Within 200 m”
   - “Open now”
   - “Highly rated (4.5)”
   - “Budget-friendly”
   - “Mid-range pricing”
   - “Great value”
4. If there are fewer than 2 contributing factors (e.g. missing data), we still emit up to 2–3 bullets from what we have, and avoid repeating the same idea.

---

## 5. Flow in Code

1. **`score_and_explain(venue, distance_m, radius, mode, is_open_now)`**  
   - Computes all normalized components.  
   - Applies the mode’s weights to get **score**.  
   - Computes per-factor contributions and builds **explanations** from the top 2–3.  
   - Returns `(score: float, explanations: list[str])`.

2. **`/recommend`** (in `main.py`):  
   - After filtering by radius and optional open_now, calls `score_and_explain` for each `(venue, distance_m)`.  
   - Sorts by **score** descending.  
   - Builds each `VenueCard` with the returned **explanations** (instead of empty list).

---

## 6. Properties

- **Deterministic**: Same inputs → same score and same explanations.  
- **Testable**: Pure functions; no I/O or randomness.  
- **Explainable**: Every bullet maps to a term in the scoring equation.  
- **Extensible**: Step 7 can add attribute-based terms (e.g. quiet, laptop-friendly) and new explanation templates without changing this structure.
