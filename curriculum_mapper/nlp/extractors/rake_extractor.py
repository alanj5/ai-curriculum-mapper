"""RAKE (Rapid Automatic Keyword Extraction) extractor.

RAKE is an unsupervised, corpus-independent method that scores keyphrases
by the ratio of word co-occurrence degree to word frequency. It requires
no pre-training, making it effective for short per-module texts where
TF-IDF corpus statistics are unreliable.

Library: multi-rake (0.0.2)

Justification: RAKE identifies multi-word key phrases without a fitted model,
complementing TF-IDF. The degree-to-frequency ratio rewards words that
appear together in rare combinations — characteristic of technical terms.
"""

from __future__ import annotations

import logging

from curriculum_mapper.config import (
    DOMAIN_STOP_WORDS,
    RAKE_MAX_WORDS,
)

logger = logging.getLogger(__name__)

try:
    from multi_rake import Rake as MultiRake
    _MULTI_RAKE_AVAILABLE = True
except ImportError:
    _MULTI_RAKE_AVAILABLE = False
    logger.warning("multi-rake not available; RAKEExtractor will fall back to NLTK RAKE")

try:
    from nltk.corpus import stopwords as _sw
    _NLTK_STOP_WORDS = set(_sw.words("english")) | set(DOMAIN_STOP_WORDS)
except Exception:
    _NLTK_STOP_WORDS = set(DOMAIN_STOP_WORDS)


class RAKEExtractor:
    """Per-document RAKE keyphrase extractor."""

    def __init__(self) -> None:
        if _MULTI_RAKE_AVAILABLE:
            self._rake = MultiRake(
                min_chars=3,
                max_words=RAKE_MAX_WORDS,
                min_freq=1,
                stopwords=_NLTK_STOP_WORDS,
            )
        else:
            self._rake = None

    def extract(self, text: str, top_n: int = 20) -> list[tuple[str, float]]:
        """Return [(keyphrase, score), ...] sorted by RAKE score descending.

        Scores are raw RAKE degree-to-frequency ratios; NOT normalised to [0,1].
        The pipeline normalises scores during confidence aggregation.
        """
        if not text.strip():
            return []

        if self._rake is not None:
            try:
                keywords = self._rake.apply(text)
                # multi-rake returns List[Tuple[str, float]]
                filtered = [
                    (kw.lower(), score)
                    for kw, score in keywords
                    if len(kw) > 2 and len(kw.split()) <= RAKE_MAX_WORDS
                ]
                return filtered[:top_n]
            except Exception as e:
                logger.warning(f"multi-rake failed: {e}")

        # Fallback: simple noun-chunk extraction from preprocessor
        return self._fallback_extract(text, top_n)

    def _fallback_extract(self, text: str, top_n: int) -> list[tuple[str, float]]:
        """Fallback when multi-rake is unavailable: return word frequency pairs."""
        words = [
            w.lower()
            for w in text.split()
            if w.lower() not in _NLTK_STOP_WORDS and len(w) > 3
        ]
        freq: dict[str, int] = {}
        for w in words:
            freq[w] = freq.get(w, 0) + 1
        sorted_words = sorted(freq.items(), key=lambda x: -x[1])
        max_score = sorted_words[0][1] if sorted_words else 1
        return [(w, s / max_score) for w, s in sorted_words[:top_n]]
