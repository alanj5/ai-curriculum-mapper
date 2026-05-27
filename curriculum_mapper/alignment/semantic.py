"""Semantic aligner: SBERT cosine similarity vs pre-encoded CS2023 topics.

Pre-encodes all 974 CS2023 topic strings at init (one-time cost, cached on disk).
Alignment for a concept = dot product of its L2-normalised embedding against all
topic embeddings. Retrieves top-K results above SIMILARITY_THRESHOLD.

Justification for 65% weight in hybrid:
  SBERT generalises across paraphrase (e.g. "sequencing" ≈ "sorting algorithms")
  whereas lexical matching anchors exact technical terminology. The 65/35 split is
  motivated by Reimers & Gurevych (2019) and validated in our evaluation.
"""

from __future__ import annotations

import logging

import numpy as np

from curriculum_mapper.config import SIMILARITY_THRESHOLD, TOP_K_ALIGNMENTS
from curriculum_mapper.nlp.embeddings import EmbeddingManager

logger = logging.getLogger(__name__)


class SemanticAligner:
    """SBERT-based concept-to-KA aligner with pre-encoded topic embeddings."""

    def __init__(self, ka_data: dict, embedding_manager: EmbeddingManager) -> None:
        self._em = embedding_manager
        self._topic_map: list[tuple[str, str]] = []  # [(ka_code, topic), ...]
        topic_strings: list[str] = []

        for ka_code, ka_info in ka_data.items():
            for topic in ka_info["topics"]:
                self._topic_map.append((ka_code, topic))
                topic_strings.append(topic)

        logger.info(f"Pre-encoding {len(topic_strings)} CS2023 topic strings…")
        self._topic_embeddings = self._em.encode(topic_strings)  # (N, 384)
        logger.info("Topic embeddings ready.")

    def align(self, concept_embedding: np.ndarray) -> list[dict]:
        """Return top-K alignment dicts sorted by semantic score descending."""
        scores = concept_embedding @ self._topic_embeddings.T  # (N,)
        # Take more than TOP_K to allow dedup by KA
        top_idx = np.argsort(scores)[::-1][: TOP_K_ALIGNMENTS * 4]
        results = []
        for idx in top_idx:
            score = float(scores[idx])
            if score < SIMILARITY_THRESHOLD:
                break
            ka_code, topic = self._topic_map[idx]
            results.append({
                "ka_code": ka_code,
                "ka_topic": topic,
                "score": round(score, 4),
                "method": "semantic",
            })
        return results[: TOP_K_ALIGNMENTS * 2]  # pass more to hybrid for dedup
