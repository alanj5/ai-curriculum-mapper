"""Ambiguity detection for alignment results.

A concept is flagged ambiguous when its top-2 hybrid scores differ by less than
AMBIGUITY_MARGIN (default 0.08). These concepts are surfaced in the UI with a
warning icon and prioritised for human validation (Research Question 3).

Small margin → user decides. Large margin → system is confident.
"""

from __future__ import annotations

from curriculum_mapper.config import AMBIGUITY_MARGIN


def is_ambiguous(scored_results: list[dict]) -> bool:
    """True when the gap between rank-1 and rank-2 scores is below AMBIGUITY_MARGIN."""
    if len(scored_results) < 2:
        return False
    return (scored_results[0]["score"] - scored_results[1]["score"]) < AMBIGUITY_MARGIN
