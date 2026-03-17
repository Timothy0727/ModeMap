"""Unit tests for mode-specific scoring and explanation generation."""

import pytest

from app.models.user_event import Mode
from app.schemas.venue import VenueCreate
from app.ranking import score_and_explain


def _venue(
    rating: float | None = 4.0,
    price_level: int | None = 2,
    open_now: bool | None = None,
) -> VenueCreate:
    return VenueCreate(
        provider_id="test-id",
        provider_name="google",
        name="Test Venue",
        categories=["cafe"],
        lat=37.77,
        lng=-122.42,
        address="123 Test St",
        rating=rating,
        price_level=price_level,
        hours={"open_now": open_now} if open_now is not None else None,
        raw_hours=None,
    )


# -----------------------------------------------------------------------------
# Determinism and shape
# -----------------------------------------------------------------------------


def test_score_and_explain_returns_float_and_list():
    """score_and_explain returns (float, list[str])."""
    v = _venue()
    score, explanations = score_and_explain(v, 500.0, 1000, Mode.QUICK_BITE)
    assert isinstance(score, float)
    assert isinstance(explanations, list)
    assert all(isinstance(s, str) for s in explanations)


def test_same_inputs_same_output():
    """Scoring is deterministic."""
    v = _venue(rating=4.2, price_level=1)
    a = score_and_explain(v, 300.0, 1000, Mode.DATE)
    b = score_and_explain(v, 300.0, 1000, Mode.DATE)
    assert a[0] == b[0]
    assert a[1] == b[1]


def test_explanations_bounded():
    """At most max_explanations bullets (default 3)."""
    v = _venue(rating=4.8, price_level=0)
    _, explanations = score_and_explain(v, 100.0, 1000, Mode.QUICK_BITE, max_explanations=3)
    assert len(explanations) <= 3
    _, explanations2 = score_and_explain(v, 100.0, 1000, Mode.BUDGET, max_explanations=2)
    assert len(explanations2) <= 2


# -----------------------------------------------------------------------------
# Mode-specific ordering
# -----------------------------------------------------------------------------


def test_quick_bite_prefers_closer():
    """Quick Bite: same venue closer scores higher."""
    v = _venue(rating=4.0, price_level=2)
    score_near, _ = score_and_explain(v, 200.0, 1000, Mode.QUICK_BITE)
    score_far, _ = score_and_explain(v, 800.0, 1000, Mode.QUICK_BITE)
    assert score_near > score_far


def test_quick_bite_prefers_open_now():
    """Quick Bite: open_now boosts score."""
    v_open = _venue(rating=4.0, open_now=True)
    v_closed = _venue(rating=4.0, open_now=False)
    score_open, _ = score_and_explain(v_open, 500.0, 1000, Mode.QUICK_BITE)
    score_closed, _ = score_and_explain(v_closed, 500.0, 1000, Mode.QUICK_BITE)
    assert score_open > score_closed


def test_work_prefers_open_now():
    """Work: open now is dominant factor."""
    v_open = _venue(rating=3.5, open_now=True)
    v_closed = _venue(rating=4.8, open_now=False)
    score_open, _ = score_and_explain(v_open, 500.0, 1000, Mode.WORK)
    score_closed, _ = score_and_explain(v_closed, 500.0, 1000, Mode.WORK)
    assert score_open > score_closed


def test_date_prefers_higher_rating():
    """Date: higher rating scores higher (same distance/price)."""
    v_high = _venue(rating=4.8, price_level=2)
    v_low = _venue(rating=3.2, price_level=2)
    score_high, _ = score_and_explain(v_high, 400.0, 1000, Mode.DATE)
    score_low, _ = score_and_explain(v_low, 400.0, 1000, Mode.DATE)
    assert score_high > score_low


def test_budget_prefers_lower_price():
    """Budget: lower price level scores higher (same rating)."""
    v_cheap = _venue(rating=4.0, price_level=0)
    v_expensive = _venue(rating=4.0, price_level=3)
    score_cheap, _ = score_and_explain(v_cheap, 500.0, 1000, Mode.BUDGET)
    score_expensive, _ = score_and_explain(v_expensive, 500.0, 1000, Mode.BUDGET)
    assert score_cheap > score_expensive


# -----------------------------------------------------------------------------
# Explanations match factors
# -----------------------------------------------------------------------------


def test_explanations_mention_distance_when_relevant():
    """When distance is a top factor, we get a distance-like explanation."""
    v = _venue(rating=3.0)
    _, explanations = score_and_explain(v, 150.0, 1000, Mode.QUICK_BITE)
    distance_style = [e for e in explanations if "m" in e or "km" in e or "Within" in e]
    assert len(distance_style) >= 1


def test_explanations_mention_open_now_when_open():
    """When venue is open and mode cares, we get 'Open now'."""
    v = _venue(open_now=True)
    _, explanations = score_and_explain(v, 500.0, 1000, Mode.WORK)
    assert "Open now" in explanations


def test_explanations_mention_rating_when_high():
    """When rating is strong, we get a rating explanation."""
    v = _venue(rating=4.7)
    _, explanations = score_and_explain(v, 500.0, 1000, Mode.DATE)
    rating_style = [e for e in explanations if "rated" in e.lower() or "Rating" in e]
    assert len(rating_style) >= 1


def test_budget_explanations_can_include_value_or_price():
    """Budget mode can produce Budget-friendly or Great value."""
    v = _venue(rating=4.5, price_level=0)
    _, explanations = score_and_explain(v, 300.0, 1000, Mode.BUDGET)
    assert len(explanations) >= 1
    combined = " ".join(explanations).lower()
    assert "budget" in combined or "value" in combined


# -----------------------------------------------------------------------------
# Edge cases
# -----------------------------------------------------------------------------


def test_missing_rating_does_not_crash():
    """Venue with no rating still gets a score and explanations."""
    v = _venue(rating=None, price_level=1)
    score, explanations = score_and_explain(v, 200.0, 1000, Mode.QUICK_BITE)
    assert isinstance(score, float)
    assert isinstance(explanations, list)


def test_missing_price_level_does_not_crash():
    """Venue with no price_level still gets a score."""
    v = _venue(rating=4.0, price_level=None)
    score, explanations = score_and_explain(v, 500.0, 1000, Mode.BUDGET)
    assert isinstance(score, float)


def test_distance_at_radius_scores_zero_distance_component():
    """At radius, distance_score is 0 so distance doesn't add to score."""
    v = _venue()
    score_at_radius, _ = score_and_explain(v, 1000.0, 1000, Mode.QUICK_BITE)
    score_inside, _ = score_and_explain(v, 500.0, 1000, Mode.QUICK_BITE)
    assert score_inside > score_at_radius
