"""Lexical aligner: Jaccard token overlap + normalised edit distance.

Two metrics are combined (max of both):
  - Jaccard: |A ∩ B| / |A ∪ B| on token sets — rewards full-phrase token overlap
  - Edit distance: 1 - normalised_levenshtein — handles plurals, hyphens, variants

High lexical precision for exact technical term matches ("sorting algorithms" →
"Sorting algorithms"). Lower recall for paraphrase — the semantic aligner covers that.
"""

from __future__ import annotations

import logging
import re

from curriculum_mapper.config import LEXICAL_THRESHOLD, TOP_K_ALIGNMENTS

logger = logging.getLogger(__name__)

try:
    import Levenshtein
    _LEV_AVAILABLE = True
except ImportError:
    _LEV_AVAILABLE = False
    logger.warning("Levenshtein not available; using difflib fallback.")


def _edit_similarity(a: str, b: str) -> float:
    """1 − normalised Levenshtein distance."""
    if _LEV_AVAILABLE:
        dist = Levenshtein.distance(a, b)
    else:
        import difflib
        dist = round((1 - difflib.SequenceMatcher(None, a, b).ratio()) * max(len(a), len(b)))
    max_len = max(len(a), len(b))
    return 1.0 - dist / max_len if max_len > 0 else 1.0


def _jaccard(a: str, b: str) -> float:
    ta = set(re.findall(r"\w+", a.lower()))
    tb = set(re.findall(r"\w+", b.lower()))
    inter = len(ta & tb)
    union = len(ta | tb)
    return inter / union if union > 0 else 0.0


class LexicalAligner:
    """Score concept terms against CS2023 KA topics using lexical measures."""

    def __init__(self, ka_data: dict) -> None:
        self._topics: list[tuple[str, str, str]] = []  # (ka_code, topic, topic_lower)
        for ka_code, ka_info in ka_data.items():
            for topic in ka_info["topics"]:
                self._topics.append((ka_code, topic, topic.lower()))

    def align(self, term: str) -> list[dict]:
        """Return top-K alignment dicts sorted by score descending."""
        term_lower = term.lower()
        results = []
        for ka_code, topic, topic_lower in self._topics:
            jac = _jaccard(term_lower, topic_lower)
            edit = _edit_similarity(term_lower, topic_lower)
            score = max(jac, edit)
            if score >= LEXICAL_THRESHOLD:
                results.append({
                    "ka_code": ka_code,
                    "ka_topic": topic,
                    "score": round(score, 4),
                    "method": "lexical",
                })
        results.sort(key=lambda r: -r["score"])
        return results[:TOP_K_ALIGNMENTS]
