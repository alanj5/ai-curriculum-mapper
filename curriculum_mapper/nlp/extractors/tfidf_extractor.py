"""TF-IDF keyphrase extractor.

Fitted on the whole module corpus; scores individual modules by TF-IDF weight.
N-grams (1–3) capture multi-word technical phrases.

Justification: TF-IDF with sublinear_tf downweights ubiquitous terms while
promoting module-specific vocabulary. min_df=2 suppresses hapax legomena
(single-occurrence noise); max_df=0.85 filters near-universal terms.
"""

from __future__ import annotations

import logging

from sklearn.feature_extraction.text import TfidfVectorizer

from curriculum_mapper.config import (
    TFIDF_MAX_DF,
    TFIDF_MIN_DF,
    TFIDF_NGRAM_RANGE,
    TFIDF_TOP_N,
)

logger = logging.getLogger(__name__)


class TFIDFExtractor:
    """Corpus-level TF-IDF keyphrase extractor."""

    def __init__(self) -> None:
        # Combine NLTK English stop words with domain-specific list
        list(
            set(["english"])  # placeholder; vectorizer uses its own list
        )
        self.vectorizer = TfidfVectorizer(
            ngram_range=TFIDF_NGRAM_RANGE,       # (1, 3)
            max_features=5000,
            sublinear_tf=True,                    # log(1 + tf)
            min_df=TFIDF_MIN_DF,                  # 2 — filter noise
            max_df=TFIDF_MAX_DF,                  # 0.85 — filter near-universal
            stop_words="english",
            token_pattern=r"(?u)\b[a-zA-Z][a-zA-Z\-]{2,}\b",
        )
        self._fitted = False
        self._feature_names: list[str] = []

    def fit(self, documents: list[str]) -> "TFIDFExtractor":
        """Fit the vectorizer on the corpus. Must be called before extract()."""
        if len(documents) < 2:
            logger.warning("TF-IDF requires >= 2 documents; skipping fit.")
            return self
        self.vectorizer.fit(documents)
        self._feature_names = list(self.vectorizer.get_feature_names_out())
        self._fitted = True
        logger.info(
            f"TF-IDF fitted on {len(documents)} documents, "
            f"{len(self._feature_names)} features"
        )
        return self

    def extract(
        self, text: str, top_n: int = TFIDF_TOP_N
    ) -> list[tuple[str, float]]:
        """Return top-N (term, tfidf_score) pairs for a single document.

        Scores are in [0, 1] due to sublinear_tf normalisation.
        """
        if not self._fitted:
            logger.warning("TFIDFExtractor not fitted; returning empty list.")
            return []
        if not text.strip():
            return []

        tfidf_matrix = self.vectorizer.transform([text])
        scores = tfidf_matrix.toarray()[0]

        # Pair feature names with scores and filter zero-scores
        pairs = [
            (self._feature_names[i], float(scores[i]))
            for i in range(len(self._feature_names))
            if scores[i] > 0
        ]
        pairs.sort(key=lambda x: -x[1])
        return pairs[:top_n]

    def fit_extract_all(
        self, documents: list[str], top_n: int = TFIDF_TOP_N
    ) -> list[list[tuple[str, float]]]:
        """Fit on corpus and extract for each document in one pass."""
        self.fit(documents)
        return [self.extract(doc, top_n) for doc in documents]

    @property
    def is_fitted(self) -> bool:
        return self._fitted
