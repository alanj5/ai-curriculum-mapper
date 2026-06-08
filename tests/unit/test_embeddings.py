"""Tests for EmbeddingManager.

Uses a mock to avoid loading the 80 MB SBERT model in CI.
"""

from __future__ import annotations

import hashlib
from pathlib import Path
from unittest.mock import MagicMock, patch

import numpy as np
import pytest


class TestEmbeddingManagerWithMock:
    """Tests that stub the SentenceTransformer to avoid model loading."""

    def _make_em(self, tmp_path: Path):
        """Build an EmbeddingManager whose cache lives in tmp_path."""
        mock_model = MagicMock()
        # Return L2-normalised random embeddings
        def _encode(texts, batch_size, show_progress_bar, normalize_embeddings, convert_to_numpy):
            n = len(texts)
            vecs = np.random.randn(n, 384).astype(np.float32)
            norms = np.linalg.norm(vecs, axis=1, keepdims=True)
            return vecs / norms

        mock_model.encode.side_effect = _encode

        with patch("curriculum_mapper.nlp.embeddings.EMBEDDING_CACHE", tmp_path), \
             patch("sentence_transformers.SentenceTransformer", return_value=mock_model):
            from importlib import reload

            import curriculum_mapper.nlp.embeddings as emb_mod
            reload(emb_mod)
            em = emb_mod.EmbeddingManager.__new__(emb_mod.EmbeddingManager)
            em.model = mock_model
            em._cache_dir = tmp_path
            # Replicate __init__ manually using patched cache
            original_cache = emb_mod.EMBEDDING_CACHE
            emb_mod.EMBEDDING_CACHE = tmp_path
            em2 = emb_mod.EmbeddingManager.__new__(emb_mod.EmbeddingManager)
            em2.model = mock_model
            emb_mod.EMBEDDING_CACHE = original_cache
            return em2, emb_mod, mock_model, tmp_path

    def test_encode_returns_correct_shape(self, tmp_path):
        mock_model = MagicMock()
        n, d = 3, 384
        vecs = np.random.randn(n, d).astype(np.float32)
        norms = np.linalg.norm(vecs, axis=1, keepdims=True)
        mock_model.encode.return_value = vecs / norms

        with patch("sentence_transformers.SentenceTransformer", return_value=mock_model), \
             patch("curriculum_mapper.nlp.embeddings.EMBEDDING_CACHE", tmp_path):
            import importlib

            import curriculum_mapper.nlp.embeddings as emb_mod
            importlib.reload(emb_mod)
            emb_mod.EMBEDDING_CACHE = tmp_path
            em = emb_mod.EmbeddingManager.__new__(emb_mod.EmbeddingManager)
            em.model = mock_model

            texts = ["sorting algorithm", "binary tree", "neural network"]
            result = em.encode(texts)
            assert result.shape == (3, 384)

    def test_encode_caches_to_disk(self, tmp_path):
        mock_model = MagicMock()
        n, d = 2, 384
        vecs = np.random.randn(n, d).astype(np.float32)
        norms = np.linalg.norm(vecs, axis=1, keepdims=True)
        mock_model.encode.return_value = vecs / norms

        with patch("sentence_transformers.SentenceTransformer", return_value=mock_model), \
             patch("curriculum_mapper.nlp.embeddings.EMBEDDING_CACHE", tmp_path):
            import importlib

            import curriculum_mapper.nlp.embeddings as emb_mod
            importlib.reload(emb_mod)
            emb_mod.EMBEDDING_CACHE = tmp_path
            em = emb_mod.EmbeddingManager.__new__(emb_mod.EmbeddingManager)
            em.model = mock_model

            texts = ["heap sort", "quicksort"]
            key = hashlib.sha256("|".join(texts).encode()).hexdigest()
            cache_file = tmp_path / f"{key}.npy"

            assert not cache_file.exists()
            em.encode(texts)
            assert cache_file.exists()

            # Second call should use cache (model not called again)
            call_count_before = mock_model.encode.call_count
            em.encode(texts)
            assert mock_model.encode.call_count == call_count_before

    def test_encode_normalised_embeddings(self, tmp_path):
        mock_model = MagicMock()
        n, d = 4, 384
        vecs = np.random.randn(n, d).astype(np.float32)
        norms = np.linalg.norm(vecs, axis=1, keepdims=True)
        mock_model.encode.return_value = vecs / norms

        with patch("sentence_transformers.SentenceTransformer", return_value=mock_model), \
             patch("curriculum_mapper.nlp.embeddings.EMBEDDING_CACHE", tmp_path):
            import importlib

            import curriculum_mapper.nlp.embeddings as emb_mod
            importlib.reload(emb_mod)
            emb_mod.EMBEDDING_CACHE = tmp_path
            em = emb_mod.EmbeddingManager.__new__(emb_mod.EmbeddingManager)
            em.model = mock_model

            texts = ["a", "b", "c", "d"]
            result = em.encode(texts)
            norms_out = np.linalg.norm(result, axis=1)
            np.testing.assert_allclose(norms_out, np.ones(n), atol=1e-5)

    def test_cosine_similarity(self, tmp_path):

        mock_model = MagicMock()
        n, d = 3, 384
        vecs = np.eye(n, d, dtype=np.float32)
        mock_model.encode.return_value = vecs

        with patch("sentence_transformers.SentenceTransformer", return_value=mock_model), \
             patch("curriculum_mapper.nlp.embeddings.EMBEDDING_CACHE", tmp_path):
            import importlib

            import curriculum_mapper.nlp.embeddings as emb_mod
            importlib.reload(emb_mod)
            emb_mod.EMBEDDING_CACHE = tmp_path
            em = emb_mod.EmbeddingManager.__new__(emb_mod.EmbeddingManager)
            em.model = mock_model

            # Orthogonal unit vectors → cosine = 0; same vector → cosine = 1
            a = np.array([1.0, 0.0, 0.0])
            b = np.array([1.0, 0.0, 0.0])
            assert em.cosine_similarity(a, b) == pytest.approx(1.0, abs=1e-5)

            a = np.array([1.0, 0.0, 0.0])
            c = np.array([0.0, 1.0, 0.0])
            assert em.cosine_similarity(a, c) == pytest.approx(0.0, abs=1e-5)
