"""Baseline ranking: mode-specific scoring and explanations. See ranking/README.md for design."""

from app.ranking.scoring import score_and_explain

__all__ = ["score_and_explain"]
