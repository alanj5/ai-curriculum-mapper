"""KeyBERT keyphrase extractor with MMR diversity.

KeyBERT embeds both the document and candidate n-grams with SBERT, then selects
candidates whose embeddings are closest to the document embedding. MMR (Maximal
Marginal Relevance) diversifies the output by penalising redundant selections.

Justification: KeyBERT with MMR achieves higher multi-word coverage than TF-IDF
alone and is more focused than RAKE (which ignores document-level context).
The shared EmbeddingManager avoids loading the SBERT model a second time.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from curriculum_mapper.config import KEYBERT_DIVERSITY, KEYBERT_TOP_N

if TYPE_CHECKING:
    from curriculum_mapper.nlp.embeddings import EmbeddingManager

logger = logging.getLogger(__name__)


class KeyBERTExtractor:
    """Document-level keyphrase extractor using KeyBERT + MMR."""

    def __init__(self, embedding_manager: "EmbeddingManager") -> None:
        try:
            from keybert import KeyBERT
            # Reuse the shared SentenceTransformer — never load a second copy
            self._model = KeyBERT(model=embedding_manager.model)
            self._available = True
        except ImportError:
            logger.warning("keybert not installed; KeyBERTExtractor unavailable.")
            self._model = None
            self._available = False

    @property
    def is_available(self) -> bool:
        return self._available

    def extract(
        self,
        text: str,
        top_n: int = KEYBERT_TOP_N,
        diversity: float = KEYBERT_DIVERSITY,
    ) -> list[tuple[str, float]]:
        """Return [(keyphrase, score), ...] sorted by relevance descending.

        Scores are cosine similarities in [0, 1] between the phrase embedding
        and the document embedding.
        """
        if not text.strip() or not self._available:
            return []

        try:
            results = self._model.extract_keywords(
                text,
                keyphrase_ngram_range=(1, 3),
                stop_words="english",
                use_mmr=True,
                diversity=diversity,
                top_n=top_n,
            )
            return [(kw.lower(), float(score)) for kw, score in results if score > 0]
        except Exception as e:
            logger.warning(f"KeyBERT extraction failed: {e}")
            return []
