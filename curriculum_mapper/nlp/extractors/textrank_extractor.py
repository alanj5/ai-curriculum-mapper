"""TextRank keyphrase extractor via pytextrank + spaCy.

TextRank builds a graph of phrases where edges represent co-occurrence
in sentences. Phrases are ranked by PageRank-style scoring, identifying
those most central to the document's semantic content.

Justification: TextRank captures contextually important phrases relative
to the document's own structure, not the corpus. Modules with unique
specialised content benefit from this since TF-IDF would deprioritise
terms appearing only once corpus-wide.
"""

from __future__ import annotations

import logging

import spacy

from curriculum_mapper.config import SPACY_MODEL, TEXTRANK_TOP_N

logger = logging.getLogger(__name__)


class TextRankExtractor:
    """Per-document TextRank keyphrase extractor using pytextrank."""

    def __init__(self) -> None:
        try:
            import pytextrank  # noqa: F401 — side-effect: registers pipe factory
            self._nlp = spacy.load(SPACY_MODEL)
            if "textrank" not in self._nlp.pipe_names:
                self._nlp.add_pipe("textrank")
            self._available = True
        except Exception as e:
            logger.warning(f"pytextrank not available: {e}. Using spaCy noun chunks.")
            self._nlp = spacy.load(SPACY_MODEL)
            self._available = False

    def extract(
        self, text: str, top_n: int = TEXTRANK_TOP_N
    ) -> list[tuple[str, float]]:
        """Return [(keyphrase, rank_score), ...] sorted by score descending.

        Rank scores are relative to the document (not normalised globally).
        """
        if not text.strip():
            return []

        doc = self._nlp(text)

        if self._available:
            phrases = [
                (phrase.text.lower(), float(phrase.rank))
                for phrase in doc._.phrases
                if len(phrase.text) > 2 and len(phrase.text.split()) <= 5
            ]
        else:
            # Fallback: use noun chunks ranked by length (longer = more specific)
            seen: set[str] = set()
            phrases = []
            for chunk in doc.noun_chunks:
                t = chunk.text.lower()
                if t not in seen and len(t) > 2:
                    seen.add(t)
                    phrases.append((t, float(len(t.split()))))

        # Deduplicate (same text, keep highest rank)
        deduped: dict[str, float] = {}
        for phrase, rank in phrases:
            if phrase not in deduped or rank > deduped[phrase]:
                deduped[phrase] = rank

        sorted_phrases = sorted(deduped.items(), key=lambda x: -x[1])
        return sorted_phrases[:top_n]

    @property
    def is_available(self) -> bool:
        return self._available
