"""SBERT embedding manager with SHA-256 disk cache.

Justification for model choice:
  all-MiniLM-L6-v2 — 80 MB, 384-dim, 6× faster than all-mpnet-base-v2 (~5% quality
  gap on STS benchmarks). Follows Green AI principle (Strubell et al., 2019).
  L2-normalised at encode time so cosine similarity reduces to a dot product.

Single instance pattern: EmbeddingManager is expensive to init (~1.5 s, 250 MB RAM).
All downstream components (KeyBERT, SemanticAligner, Canonicalizer) receive a shared
reference via dependency injection — never load the model twice.
"""

from __future__ import annotations

import hashlib
import logging

import numpy as np

from curriculum_mapper.config import EMBEDDING_CACHE, SBERT_MODEL

logger = logging.getLogger(__name__)


class EmbeddingManager:
    """Load SBERT once; encode with SHA-256 disk cache."""

    def __init__(self, model_name: str = SBERT_MODEL) -> None:
        logger.info(f"Loading SBERT model: {model_name}")
        from sentence_transformers import SentenceTransformer
        self.model = SentenceTransformer(model_name)
        self.model_name = model_name
        EMBEDDING_CACHE.mkdir(parents=True, exist_ok=True)
        logger.info("SBERT model loaded.")

    def encode(
        self,
        texts: list[str],
        batch_size: int = 32,
        show_progress: bool = False,
    ) -> np.ndarray:
        """Return L2-normalised embeddings, loading from cache when available.

        Cache key: SHA-256 of pipe-joined sorted texts.
        Shape: (len(texts), 384).
        """
        if not texts:
            return np.empty((0, 384), dtype=np.float32)

        cache_key = hashlib.sha256("|".join(texts).encode()).hexdigest()
        cache_path = EMBEDDING_CACHE / f"{cache_key}.npy"

        if cache_path.exists():
            logger.debug(f"Embedding cache hit: {cache_key[:8]}…")
            return np.load(cache_path)

        logger.info(f"Encoding {len(texts)} texts with SBERT…")
        embeddings = self.model.encode(
            texts,
            batch_size=batch_size,
            show_progress_bar=show_progress,
            normalize_embeddings=True,  # L2 norm → cosine = dot product
            convert_to_numpy=True,
        )
        np.save(cache_path, embeddings)
        logger.debug(f"Cached embeddings: {cache_key[:8]}…")
        return embeddings

    def cosine_similarity(self, a: np.ndarray, b: np.ndarray) -> float:
        """Cosine similarity between two L2-normalised vectors."""
        return float(np.dot(a, b))

    def pairwise_similarity(self, embeddings: np.ndarray) -> np.ndarray:
        """Return (N, N) cosine similarity matrix for L2-normalised embeddings."""
        return embeddings @ embeddings.T
