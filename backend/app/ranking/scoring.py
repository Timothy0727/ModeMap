"""
Baseline ranking: mode-specific scoring and "Why this matches" explanations.

See ranking/README.md for the full design (equations, weights, normalization).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from app.models.user_event import Mode
from app.schemas.venue import VenueCreate


# -----------------------------------------------------------------------------
# Normalized components (0-1, higher = better)
# -----------------------------------------------------------------------------


def _distance_score(distance_m: float, radius_m: int) -> float:
    """Closer = higher. 0m -> 1, at radius -> 0."""
    if radius_m <= 0:
        return 1.0
    return max(0.0, 1.0 - distance_m / float(radius_m))


def _rating_norm(rating: float | None) -> float:
    """0-5 -> 0-1. Missing -> 0."""
    if rating is None:
        return 0.0
    return max(0.0, min(1.0, rating / 5.0))


def _open_score(hours: dict[str, Any] | None) -> float:
    """1 if open now, else 0. Unknown (no hours) -> 0."""
    if hours is None:
        return 0.0
    if hours.get("open_now") is True:
        return 1.0
    return 0.0


def _price_low_score(price_level: int | None) -> float:
    """Lower price = higher. $ -> 1, $$$$ -> 0. Missing -> 0.5."""
    if price_level is None:
        return 0.5
    return max(0.0, min(1.0, 1.0 - price_level / 4.0))


def _mid_price_score(price_level: int | None) -> float:
    """Mid-range (1-2) best. 2 -> 1, 1 or 3 -> 0.5, 0 or 4 -> 0."""
    p = price_level if price_level is not None else 2
    return max(0.0, 1.0 - abs(p - 2) / 2.0)


def _value_score(rating: float | None, price_level: int | None) -> float:
    """Good rating and low price = high value."""
    return _rating_norm(rating) * _price_low_score(price_level)


# -----------------------------------------------------------------------------
# Per-factor contribution for explanations
# -----------------------------------------------------------------------------


@dataclass(frozen=True)
class _FactorContrib:
    """A single factor's contribution to the score and its explanation text."""

    contribution: float
    message: str


def _top_explanations(contribs: list[_FactorContrib], max_bullets: int = 3) -> list[str]:
    """Return up to max_bullets explanation strings, ordered by contribution descending."""
    sorted_contribs = sorted(contribs, key=lambda c: c.contribution, reverse=True)
    messages: list[str] = []
    for c in sorted_contribs:
        if c.contribution <= 0 or not c.message.strip():
            continue
        if c.message not in messages:
            messages.append(c.message)
        if len(messages) >= max_bullets:
            break
    return messages


# -----------------------------------------------------------------------------
# Mode-specific scoring and explanation building
# -----------------------------------------------------------------------------


def _score_quick_bite(
    distance_score: float,
    open_s: float,
    rating_n: float,
    price_low: float,
    distance_m: float,
    rating: float | None,
) -> tuple[float, list[_FactorContrib]]:
    """Quick Bite: distance + open_now + rating + slight price preference."""
    w_d, w_o, w_r, w_p = 0.40, 0.30, 0.22, 0.08
    score = w_d * distance_score + w_o * open_s + w_r * rating_n + w_p * price_low
    contribs = [
        _FactorContrib(w_d * distance_score, _fmt_distance(distance_m)),
        _FactorContrib(w_o * open_s, "Open now" if open_s > 0 else ""),
        _FactorContrib(w_r * rating_n, _fmt_rating(rating) if rating is not None else ""),
        _FactorContrib(w_p * price_low, "Budget-friendly" if price_low >= 0.75 else ""),
    ]
    return score, contribs


def _score_work(
    distance_score: float,
    open_s: float,
    rating_n: float,
    distance_m: float,
    rating: float | None,
) -> tuple[float, list[_FactorContrib]]:
    """Work: open_now + distance + rating."""
    w_o, w_d, w_r = 0.50, 0.30, 0.20
    score = w_o * open_s + w_d * distance_score + w_r * rating_n
    contribs = [
        _FactorContrib(w_o * open_s, "Open now" if open_s > 0 else ""),
        _FactorContrib(w_d * distance_score, _fmt_distance(distance_m)),
        _FactorContrib(w_r * rating_n, _fmt_rating(rating) if rating is not None else ""),
    ]
    return score, contribs


def _score_date(
    distance_score: float,
    rating_n: float,
    mid_price: float,
    distance_m: float,
    rating: float | None,
) -> tuple[float, list[_FactorContrib]]:
    """Date: rating + distance + mid-range price."""
    w_r, w_d, w_p = 0.50, 0.25, 0.25
    score = w_r * rating_n + w_d * distance_score + w_p * mid_price
    contribs = [
        _FactorContrib(w_r * rating_n, _fmt_rating(rating) if rating is not None else ""),
        _FactorContrib(w_d * distance_score, _fmt_distance(distance_m)),
        _FactorContrib(w_p * mid_price, "Mid-range pricing" if mid_price >= 0.5 else ""),
    ]
    return score, contribs


def _score_budget(
    distance_score: float,
    price_low: float,
    value_s: float,
    distance_m: float,
) -> tuple[float, list[_FactorContrib]]:
    """Budget: low price + value + a bit of distance."""
    w_p, w_v, w_d = 0.50, 0.35, 0.15
    score = w_p * price_low + w_v * value_s + w_d * distance_score
    contribs = [
        _FactorContrib(w_p * price_low, "Budget-friendly" if price_low >= 0.5 else ""),
        _FactorContrib(w_v * value_s, "Great value" if value_s >= 0.3 else ""),
        _FactorContrib(w_d * distance_score, _fmt_distance(distance_m)),
    ]
    return score, contribs


def _fmt_distance(distance_m: float) -> str:
    """Human-readable distance for explanations."""
    if distance_m < 1000:
        return f"Within {int(round(distance_m))} m"
    km = distance_m / 1000.0
    if km < 10:
        return f"Within {km:.1f} km"
    return f"Within {int(round(km))} km"


def _fmt_rating(rating: float) -> str:
    """Human-readable rating for explanations."""
    if rating >= 4.0:
        return f"Highly rated ({rating:.1f})"
    if rating >= 3.0:
        return f"Rated {rating:.1f}"
    return f"Rated {rating:.1f}"


# -----------------------------------------------------------------------------
# Public API
# -----------------------------------------------------------------------------


def score_and_explain(
    venue: VenueCreate,
    distance_m: float,
    radius_m: int,
    mode: Mode,
    max_explanations: int = 3,
) -> tuple[float, list[str]]:
    """
    Compute mode-specific score and 2-3 explanation bullets for a venue.

    Args:
        venue: Normalized venue from provider.
        distance_m: Distance from request center in meters.
        radius_m: Request search radius in meters (used to normalize distance).
        mode: Recommendation mode (work, date, quick_bite, budget).
        max_explanations: Max number of explanation bullets (default 3).

    Returns:
        (score, explanations): score is higher = better; explanations are user-facing bullets.
    """
    dist_s = _distance_score(distance_m, radius_m)
    open_s = _open_score(venue.hours)
    rating_n = _rating_norm(venue.rating)
    price_low = _price_low_score(venue.price_level)
    mid_price = _mid_price_score(venue.price_level)
    value_s = _value_score(venue.rating, venue.price_level)

    if mode == Mode.QUICK_BITE:
        score, contribs = _score_quick_bite(
            dist_s, open_s, rating_n, price_low, distance_m, venue.rating
        )
    elif mode == Mode.WORK:
        score, contribs = _score_work(dist_s, open_s, rating_n, distance_m, venue.rating)
    elif mode == Mode.DATE:
        score, contribs = _score_date(
            dist_s, rating_n, mid_price, distance_m, venue.rating
        )
    elif mode == Mode.BUDGET:
        score, contribs = _score_budget(dist_s, price_low, value_s, distance_m)
    else:
        # Fallback: rating then distance
        score = rating_n * 0.6 + dist_s * 0.4
        contribs = [
            _FactorContrib(rating_n * 0.6, _fmt_rating(venue.rating) if venue.rating is not None else ""),
            _FactorContrib(dist_s * 0.4, _fmt_distance(distance_m)),
        ]

    explanations = _top_explanations(contribs, max_bullets=max_explanations)
    return score, explanations
