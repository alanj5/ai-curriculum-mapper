"""System Usability Scale (SUS) scoring helpers.

SUS (Brooke, 1996): ten alternating positive/negative items on a 1--5 scale.
Per participant: odd items contribute (response - 1), even items contribute
(5 - response); the sum (0--40) is multiplied by 2.5 to give a 0--100 score.
Interpretive bands follow Bangor et al. (2009).
"""

from __future__ import annotations

import statistics


def sus_score(items: list[int]) -> float:
    """Score one participant's ten 1--5 SUS responses → a 0--100 SUS value."""
    if len(items) != 10:
        raise ValueError(f"SUS needs exactly 10 items, got {len(items)}")
    for v in items:
        if not (1 <= v <= 5):
            raise ValueError(f"SUS responses must be in 1..5, got {v}")
    total = 0
    for i, v in enumerate(items):
        total += (v - 1) if i % 2 == 0 else (5 - v)  # 0-indexed: even idx = odd item
    return round(total * 2.5, 1)


def sus_band(score: float) -> str:
    """Adjective band for a SUS score (Bangor et al., 2009)."""
    if score >= 80.3:
        return "excellent"
    if score >= 68:
        return "good"
    if score >= 51:
        return "OK (marginal)"
    return "poor"


def summarise_sus(participants: list[list[int]]) -> dict:
    """Aggregate SUS across participants. Returns mean/SD/min/max/band + per-participant."""
    if not participants:
        return {"n": 0}
    scores = [sus_score(p) for p in participants]
    mean = round(statistics.mean(scores), 1)
    return {
        "n": len(scores),
        "scores": scores,
        "mean": mean,
        "sd": round(statistics.stdev(scores), 1) if len(scores) > 1 else 0.0,
        "min": min(scores),
        "max": max(scores),
        "band": sus_band(mean),
        "above_average": mean >= 68,  # 68 is the established SUS average
    }


def summarise_likert(items: list[list[float]]) -> list[float]:
    """Per-column means for a set of Likert responses (rows = participants)."""
    if not items:
        return []
    cols = list(zip(*items))
    return [round(statistics.mean(c), 2) for c in cols]
