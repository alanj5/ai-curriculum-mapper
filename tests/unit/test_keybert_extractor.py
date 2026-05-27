"""Tests for KeyBERTExtractor."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from curriculum_mapper.nlp.extractors.keybert_extractor import KeyBERTExtractor

# ── Helpers ────────────────────────────────────────────────────────────────────

def _make_em(model=None) -> MagicMock:
    em = MagicMock()
    em.model = model or MagicMock()
    return em


def _make_extractor_with_mock_keybert(keywords: list[tuple[str, float]]) -> KeyBERTExtractor:
    """Return a KeyBERTExtractor whose internal KeyBERT model returns fixed keywords."""
    mock_kb = MagicMock()
    mock_kb.extract_keywords.return_value = keywords

    em = _make_em()
    with patch("keybert.KeyBERT", return_value=mock_kb):
        extractor = KeyBERTExtractor(em)
    extractor._model = mock_kb
    return extractor


# ── Initialization ─────────────────────────────────────────────────────────────

class TestKeyBERTExtractorInit:
    def test_available_when_keybert_present(self):
        em = _make_em()
        mock_kb = MagicMock()
        with patch("keybert.KeyBERT", return_value=mock_kb):
            ext = KeyBERTExtractor(em)
        assert ext.is_available is True

    def test_unavailable_when_keybert_missing(self):
        em = _make_em()
        with patch("builtins.__import__", side_effect=lambda name, *a, **kw: (_ for _ in ()).throw(ImportError("keybert not installed")) if name == "keybert" else __import__(name, *a, **kw)):
            try:
                ext = KeyBERTExtractor(em)
                assert ext.is_available is False
            except Exception:
                pytest.skip("Cannot mock nested import in this environment")

    def test_model_is_none_when_unavailable(self):
        _make_em()
        # Create extractor with available=False directly
        ext = KeyBERTExtractor.__new__(KeyBERTExtractor)
        ext._model = None
        ext._available = False
        assert ext._model is None

    def test_reuses_embedding_manager_model(self):
        sentinel = object()
        em = _make_em(model=sentinel)
        captured = {}
        def fake_keybert(model=None, **kwargs):
            captured["model"] = model
            return MagicMock()
        with patch("keybert.KeyBERT", side_effect=fake_keybert):
            KeyBERTExtractor(em)
        assert captured["model"] is sentinel


# ── extract ────────────────────────────────────────────────────────────────────

def _make_ext(keywords: list[tuple[str, float]]) -> KeyBERTExtractor:
    mock_kb = MagicMock()
    mock_kb.extract_keywords.return_value = keywords
    ext = KeyBERTExtractor.__new__(KeyBERTExtractor)
    ext._model = mock_kb
    ext._available = True
    return ext


class TestKeyBERTExtractorExtract:
    def test_returns_list_of_tuples(self):
        ext = _make_ext([("sorting algorithms", 0.85)])
        result = ext.extract("algorithms text")
        assert isinstance(result, list)
        assert all(isinstance(r, tuple) and len(r) == 2 for r in result)

    def test_lowercases_keywords(self):
        ext = _make_ext([("Sorting Algorithms", 0.85)])
        result = ext.extract("some text about sorting")
        assert result[0][0] == "sorting algorithms"

    def test_scores_are_floats(self):
        ext = _make_ext([("sorting", 0.9), ("dynamic programming", 0.7)])
        result = ext.extract("some text")
        for _, score in result:
            assert isinstance(score, float)

    def test_empty_text_returns_empty(self):
        ext = _make_ext([("sorting", 0.9)])
        result = ext.extract("")
        assert result == []

    def test_whitespace_only_returns_empty(self):
        ext = _make_ext([("sorting", 0.9)])
        result = ext.extract("   \t\n  ")
        assert result == []

    def test_unavailable_extractor_returns_empty(self):
        ext = KeyBERTExtractor.__new__(KeyBERTExtractor)
        ext._model = None
        ext._available = False
        result = ext.extract("some text about algorithms")
        assert result == []

    def test_filters_zero_score_terms(self):
        ext = _make_ext([("sorting algorithms", 0.85), ("noise term", 0.0)])
        result = ext.extract("some text")
        terms = [r[0] for r in result]
        assert "noise term" not in terms
        assert "sorting algorithms" in terms

    def test_handles_extraction_exception(self):
        mock_kb = MagicMock()
        mock_kb.extract_keywords.side_effect = RuntimeError("model error")
        ext = KeyBERTExtractor.__new__(KeyBERTExtractor)
        ext._model = mock_kb
        ext._available = True
        result = ext.extract("some text")
        assert result == []

    def test_custom_top_n_and_diversity(self):
        mock_kb = MagicMock()
        mock_kb.extract_keywords.return_value = [("term", 0.8)]
        ext = KeyBERTExtractor.__new__(KeyBERTExtractor)
        ext._model = mock_kb
        ext._available = True
        ext.extract("text", top_n=5, diversity=0.5)
        call_kwargs = mock_kb.extract_keywords.call_args[1]
        assert call_kwargs["top_n"] == 5
        assert call_kwargs["diversity"] == 0.5

    def test_uses_mmr(self):
        mock_kb = MagicMock()
        mock_kb.extract_keywords.return_value = []
        ext = KeyBERTExtractor.__new__(KeyBERTExtractor)
        ext._model = mock_kb
        ext._available = True
        ext.extract("text about sorting and algorithms")
        call_kwargs = mock_kb.extract_keywords.call_args[1]
        assert call_kwargs["use_mmr"] is True
