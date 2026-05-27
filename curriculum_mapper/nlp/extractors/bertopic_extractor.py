"""BERTopic corpus-level topic extractor.

BERTopic discovers latent topic clusters across the module corpus. It is run
once corpus-wide (not per-document). The topic words per cluster become
additional concept candidates for each module assigned to that cluster.

Pipeline:
  SBERT embeddings → UMAP dimensionality reduction → HDBSCAN clustering →
  CountVectorizer c-TF-IDF topic representation

random_state=42 on UMAP and HDBSCAN for full reproducibility (Sect. 3.4 of
interim report). Outlier documents (HDBSCAN topic -1) are silently dropped
from the per-document topic word mapping.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from curriculum_mapper.nlp.embeddings import EmbeddingManager

logger = logging.getLogger(__name__)


class BERTopicExtractor:
    """Corpus-level BERTopic topic model."""

    def __init__(self, embedding_manager: "EmbeddingManager") -> None:
        try:
            from bertopic import BERTopic
            from hdbscan import HDBSCAN
            from sklearn.feature_extraction.text import CountVectorizer
            from umap import UMAP

            umap_model = UMAP(
                n_neighbors=5,
                n_components=5,
                min_dist=0.0,
                metric="cosine",
                random_state=42,  # reproducibility
            )
            hdbscan_model = HDBSCAN(
                min_cluster_size=3,
                metric="euclidean",
                cluster_selection_method="eom",
                prediction_data=True,
            )
            vectorizer_model = CountVectorizer(
                stop_words="english",
                ngram_range=(1, 2),
            )
            self._model = BERTopic(
                embedding_model=embedding_manager.model,
                umap_model=umap_model,
                hdbscan_model=hdbscan_model,
                vectorizer_model=vectorizer_model,
                top_n_words=10,
                verbose=False,
                calculate_probabilities=False,
            )
            self._available = True
        except ImportError as e:
            logger.warning(f"BERTopic dependencies missing: {e}. BERTopicExtractor disabled.")
            self._model = None
            self._available = False

    @property
    def is_available(self) -> bool:
        return self._available

    def fit_transform(self, documents: list[str]) -> dict[int, list[str]]:
        """Fit BERTopic on corpus and return {doc_idx: [topic_words]}.

        Documents that HDBSCAN assigns to the outlier cluster (-1) are excluded.
        """
        if not self._available or len(documents) < 4:
            logger.warning("BERTopic skipped: unavailable or corpus too small.")
            return {}

        try:
            topics, _ = self._model.fit_transform(documents)
            results: dict[int, list[str]] = {}
            for i, topic_id in enumerate(topics):
                if topic_id != -1:
                    topic_info = self._model.get_topic(topic_id)
                    if topic_info:
                        results[i] = [w for w, _ in topic_info]
            n_topics = len(set(t for t in topics if t != -1))
            n_outliers = sum(1 for t in topics if t == -1)
            logger.info(
                f"BERTopic: {n_topics} topics, {n_outliers}/{len(documents)} outlier docs"
            )
            return results
        except Exception as e:
            logger.warning(f"BERTopic fit_transform failed: {e}")
            return {}
