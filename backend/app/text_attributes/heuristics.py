"""
Heuristic text-attribute inference for venues.

Infers per-venue attribute scores (0–1) and evidence snippets from a list of
short text snippets (reviews, editorial summaries, etc.) using deterministic
keyword/substring rules — no ML or external dependencies required.

## Scoring formula

For each attribute:
    score = pos_count / (pos_count + neg_count + 1)

Where:
  - pos_count: number of snippets matching at least one positive pattern
  - neg_count: number of snippets matching at least one negative pattern
  - The +1 denominator prevents 1.0 with a single weak signal

Score ranges:
  - 0.0           : no signal (attribute is omitted from the output dict)
  - 0.0 – ~0.33   : negative signal dominates
  - ~0.33 – ~0.67 : mixed / weak signal
  - ~0.67 – 1.0   : positive signal dominates

## Upgrade path

To replace or augment with ML, swap out this module while keeping the same
public interface:  infer_attributes_from_text(snippets) -> (scores, evidence)
"""

from __future__ import annotations

# ---------------------------------------------------------------------------
# Canonical attribute set and their keyword rules
# ---------------------------------------------------------------------------

# Each entry: attribute_name -> (positive_patterns, negative_patterns)
# Patterns are matched case-insensitively as substrings.
# Order within each list does not affect scoring.
ATTRIBUTE_RULES: dict[str, tuple[list[str], list[str]]] = {
    "quiet": (
        [
            "quiet",
            "peaceful",
            "calm",
            "tranquil",
            "not too loud",
            "serene",
            "relaxing atmosphere",
            "mellow vibe",
            "low-key",
        ],
        [
            "loud",
            "noisy",
            "crowded",
            "packed",
            "blasting music",
            "rowdy",
            "bustling",
            "chaotic",
            "deafening",
        ],
    ),
    "noisy": (
        [
            "loud",
            "noisy",
            "crowded",
            "packed",
            "blasting music",
            "rowdy",
            "bustling",
            "chaotic",
            "deafening",
        ],
        [
            "quiet",
            "peaceful",
            "calm",
            "tranquil",
            "serene",
            "not too loud",
            "mellow vibe",
            "low-key",
        ],
    ),
    "laptop_friendly": (
        [
            "wifi",
            "wi-fi",
            "wi fi",
            "power outlet",
            "power outlets",
            "outlets",
            "sockets",
            "plugs",
            "good for work",
            "study",
            "laptop",
            "working",
            "coworking",
            "remote work",
            "great for studying",
        ],
        [
            "no wifi",
            "no outlets",
            "no laptops",
            "time limit",
            "no working",
        ],
    ),
    "romantic": (
        [
            "romantic",
            "date night",
            "candlelit",
            "candle",
            "cozy",
            "intimate",
            "ambience",
            "atmosphere",
            "anniversary",
            "special occasion",
            "date spot",
            "lovely setting",
            "charming",
        ],
        [
            "rowdy",
            "sports bar",
            "family with kids",
            "boisterous",
            "frat",
            "college bar",
        ],
    ),
    "fast_service": (
        [
            "fast service",
            "quick service",
            "came out quickly",
            "prompt",
            "no wait",
            "short wait",
            "speedy service",
            "quick turnaround",
            "served quickly",
            "fast food",
        ],
        [
            "slow service",
            "took forever",
            "long wait",
            "waited",
            "slow",
            "sluggish",
            "understaffed",
        ],
    ),
    "value": (
        [
            "good value",
            "worth the price",
            "affordable",
            "cheap",
            "great deal",
            "value for money",
            "reasonably priced",
            "budget friendly",
            "inexpensive",
        ],
        [
            "overpriced",
            "not worth",
            "ripoff",
            "rip off",
            "too expensive",
        ],
    ),
}

# Maximum number of evidence snippets to keep per attribute
MAX_EVIDENCE_PER_ATTRIBUTE = 3

# Maximum characters per evidence snippet shown to users
EVIDENCE_MAX_CHARS = 160


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def infer_attributes_from_text(
    snippets: list[str],
) -> tuple[dict[str, float], dict[str, list[str]]]:
    """Infer venue attributes from a list of text snippets.

    Applies keyword/rule heuristics for each attribute in ATTRIBUTE_RULES.
    Attributes with no signal are omitted from the returned dicts.

    Args:
        snippets: List of short text strings (reviews, editorial summaries,
            etc.). Empty strings are ignored.

    Returns:
        A tuple of:
          - attribute_scores: dict mapping attribute name -> score in [0, 1].
            Omitted if no positive or negative patterns matched.
          - evidence_snippets: dict mapping attribute name -> list of
            truncated snippets that contained a positive pattern match.
    """
    if not snippets:
        return {}, {}

    pos_counts: dict[str, int] = {attr: 0 for attr in ATTRIBUTE_RULES}
    neg_counts: dict[str, int] = {attr: 0 for attr in ATTRIBUTE_RULES}
    evidence: dict[str, list[str]] = {attr: [] for attr in ATTRIBUTE_RULES}

    for snippet in snippets:
        if not snippet or not snippet.strip():
            continue
        lowered = snippet.lower()
        for attr, (pos_patterns, neg_patterns) in ATTRIBUTE_RULES.items():
            matched_neg = any(p in lowered for p in neg_patterns)
            # Only count as positive when the snippet isn't also a negation
            # (e.g. "no wifi" contains "wifi" but should not be a positive hit)
            matched_pos = (not matched_neg) and any(p in lowered for p in pos_patterns)

            if matched_pos:
                pos_counts[attr] += 1
                if len(evidence[attr]) < MAX_EVIDENCE_PER_ATTRIBUTE:
                    evidence[attr].append(_truncate(snippet))
            if matched_neg:
                neg_counts[attr] += 1

    scores: dict[str, float] = {}
    for attr in ATTRIBUTE_RULES:
        pos = pos_counts[attr]
        neg = neg_counts[attr]
        if pos + neg == 0:
            continue  # No signal; attribute is not included in output
        scores[attr] = pos / (pos + neg + 1)

    # Only return evidence for attributes that had positive signal
    clean_evidence = {attr: evs for attr, evs in evidence.items() if evs}

    return scores, clean_evidence


def _truncate(text: str, max_chars: int = EVIDENCE_MAX_CHARS) -> str:
    """Truncate text to max_chars, appending '…' if needed."""
    text = text.strip()
    if len(text) <= max_chars:
        return text
    return text[:max_chars].rstrip() + "…"
