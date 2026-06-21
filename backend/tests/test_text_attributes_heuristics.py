"""Unit tests for heuristic text-attribute inference.

Tests cover:
- Scoring direction for each attribute (positive patterns → high score,
  negative patterns → low score).
- Evidence snippet content and truncation.
- Score range guarantees (0–1).
- Edge cases: empty inputs, conflicting signals, all-negative, no signal.
"""


from app.text_attributes.heuristics import (
    ATTRIBUTE_RULES,
    EVIDENCE_MAX_CHARS,
    infer_attributes_from_text,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def snippets_with(*phrases: str) -> list[str]:
    """Wrap phrases in sentence-like snippets."""
    return [f"This place is really {p} in every way." for p in phrases]


# ---------------------------------------------------------------------------
# Basic shape
# ---------------------------------------------------------------------------


def test_returns_empty_on_no_snippets():
    scores, evidence = infer_attributes_from_text([])
    assert scores == {}
    assert evidence == {}


def test_returns_empty_on_blank_snippets():
    scores, evidence = infer_attributes_from_text(["", "   ", "\n"])
    assert scores == {}
    assert evidence == {}


def test_scores_in_range():
    texts = snippets_with("quiet", "laptop", "romantic", "fast service", "affordable")
    scores, _ = infer_attributes_from_text(texts)
    for attr, score in scores.items():
        assert 0.0 <= score <= 1.0, f"{attr} score {score} out of range"


def test_all_canonical_attributes_covered():
    """ATTRIBUTE_RULES contains all expected attributes."""
    expected = {"quiet", "noisy", "laptop_friendly", "romantic", "fast_service", "value"}
    assert set(ATTRIBUTE_RULES.keys()) == expected


# ---------------------------------------------------------------------------
# noisy
# ---------------------------------------------------------------------------


def test_noisy_raises_on_positive_patterns():
    texts = ["So loud and noisy, very crowded.", "Blasting music and rowdy crowd."]
    scores, _ = infer_attributes_from_text(texts)
    assert "noisy" in scores
    assert scores["noisy"] > 0.4


def test_noisy_lowers_on_quiet_patterns():
    texts = ["Very quiet and peaceful.", "Calm and tranquil atmosphere."]
    scores, _ = infer_attributes_from_text(texts)
    assert "noisy" in scores
    assert scores["noisy"] < 0.4


# ---------------------------------------------------------------------------
# quiet
# ---------------------------------------------------------------------------


def test_quiet_positive_patterns_raise_score():
    texts = ["The place is so quiet and peaceful.", "Very calm and tranquil atmosphere."]
    scores, _ = infer_attributes_from_text(texts)
    assert "quiet" in scores
    assert scores["quiet"] > 0.4


def test_quiet_negative_patterns_lower_score():
    texts = ["So loud and noisy in here.", "Very crowded and rowdy."]
    scores, _ = infer_attributes_from_text(texts)
    assert "quiet" in scores
    assert scores["quiet"] < 0.4


def test_quiet_mixed_signals():
    texts = [
        "Generally peaceful but can get loud on weekends.",
        "Quiet during the week, noisy and crowded on Fridays.",
    ]
    scores, _ = infer_attributes_from_text(texts)
    assert "quiet" in scores
    # Both positive and negative matched — score should be somewhere in the middle
    assert 0.0 <= scores["quiet"] <= 1.0


# ---------------------------------------------------------------------------
# laptop_friendly
# ---------------------------------------------------------------------------


def test_laptop_friendly_raises_on_positive():
    texts = ["Great wifi and power outlets throughout.", "Perfect for studying with your laptop."]
    scores, _ = infer_attributes_from_text(texts)
    assert "laptop_friendly" in scores
    assert scores["laptop_friendly"] > 0.4


def test_laptop_friendly_lowers_on_negative():
    texts = ["No wifi available here.", "No outlets anywhere, very frustrating."]
    scores, _ = infer_attributes_from_text(texts)
    assert "laptop_friendly" in scores
    assert scores["laptop_friendly"] < 0.4


# ---------------------------------------------------------------------------
# romantic
# ---------------------------------------------------------------------------


def test_romantic_raises_on_positive():
    texts = ["Very romantic and intimate setting.", "Perfect for a date night — cozy and charming."]
    scores, _ = infer_attributes_from_text(texts)
    assert "romantic" in scores
    assert scores["romantic"] > 0.4


def test_romantic_lowers_on_negative():
    texts = ["Rowdy sports bar.", "Loud college bar, not a date spot."]
    scores, _ = infer_attributes_from_text(texts)
    assert "romantic" in scores
    assert scores["romantic"] < 0.4


# ---------------------------------------------------------------------------
# fast_service
# ---------------------------------------------------------------------------


def test_fast_service_raises_on_positive():
    texts = ["Incredibly fast service.", "Food came out quickly with no wait."]
    scores, _ = infer_attributes_from_text(texts)
    assert "fast_service" in scores
    assert scores["fast_service"] > 0.4


def test_fast_service_lowers_on_slow():
    texts = ["Slow service — waited 45 minutes.", "Took forever to get our order."]
    scores, _ = infer_attributes_from_text(texts)
    assert "fast_service" in scores
    assert scores["fast_service"] < 0.4


# ---------------------------------------------------------------------------
# value
# ---------------------------------------------------------------------------


def test_value_raises_on_positive():
    texts = ["Great value for money.", "Very affordable and reasonably priced."]
    scores, _ = infer_attributes_from_text(texts)
    assert "value" in scores
    assert scores["value"] > 0.4


def test_value_lowers_on_negative():
    texts = ["Totally overpriced.", "Not worth the price — ripoff."]
    scores, _ = infer_attributes_from_text(texts)
    assert "value" in scores
    assert scores["value"] < 0.4


# ---------------------------------------------------------------------------
# Ordering across multiple mentions
# ---------------------------------------------------------------------------


def test_more_positive_mentions_gives_higher_score():
    """Attribute mentioned in more snippets → higher score."""
    texts_few = ["quiet atmosphere"] * 1 + ["unrelated"] * 5
    texts_many = ["quiet atmosphere"] * 5 + ["unrelated"] * 1

    scores_few, _ = infer_attributes_from_text(texts_few)
    scores_many, _ = infer_attributes_from_text(texts_many)

    assert scores_many.get("quiet", 0) > scores_few.get("quiet", 0)


# ---------------------------------------------------------------------------
# Evidence snippets
# ---------------------------------------------------------------------------


def test_evidence_contains_matching_text():
    texts = ["Great wifi here for working.", "Plenty of power outlets available."]
    _, evidence = infer_attributes_from_text(texts)
    assert "laptop_friendly" in evidence
    assert len(evidence["laptop_friendly"]) >= 1
    # Evidence should contain the snippet text (possibly truncated)
    combined = " ".join(evidence["laptop_friendly"])
    assert "wifi" in combined.lower() or "outlet" in combined.lower()


def test_evidence_capped_at_max():
    """No more than MAX_EVIDENCE_PER_ATTRIBUTE snippets per attribute."""
    texts = [f"quiet and peaceful visit number {i}" for i in range(20)]
    _, evidence = infer_attributes_from_text(texts)
    assert "quiet" in evidence
    assert len(evidence["quiet"]) <= 3


def test_evidence_truncated_to_max_chars():
    long_text = "quiet " + "x" * (EVIDENCE_MAX_CHARS + 50)
    _, evidence = infer_attributes_from_text([long_text])
    for snippets in evidence.values():
        for s in snippets:
            assert len(s) <= EVIDENCE_MAX_CHARS + 1  # +1 for the ellipsis char


def test_evidence_only_for_attributes_with_positive_signal():
    """Evidence dict must not include attributes that had only negative matches."""
    texts = ["So loud and noisy."]  # negative for 'quiet', no positive
    _, evidence = infer_attributes_from_text(texts)
    assert "quiet" not in evidence


# ---------------------------------------------------------------------------
# Attributes with no signal are omitted
# ---------------------------------------------------------------------------


def test_attributes_without_signal_absent_from_scores():
    texts = ["The food was delicious and the service was excellent."]
    scores, _ = infer_attributes_from_text(texts)
    # None of our attribute keywords appear → empty scores
    assert scores == {}


def test_only_matched_attributes_in_scores():
    texts = ["Great wifi here for studying."]
    scores, _ = infer_attributes_from_text(texts)
    # Only laptop_friendly should have a signal
    assert "laptop_friendly" in scores
    # Other attributes should NOT appear (no signal)
    for attr in ["quiet", "romantic", "fast_service", "value"]:
        assert attr not in scores
