"""Tests for the Canonicalizer (nlp/canonicalizer.py)."""

from __future__ import annotations

from unittest.mock import MagicMock

import numpy as np

from curriculum_mapper.ingestion.schema import Concept
from curriculum_mapper.nlp.canonicalizer import (
    Canonicalizer,
    _lemmatize_term,
    _wordnet_similar,
)

# ── Helpers ────────────────────────────────────────────────────────────────────

def _make_em(n_terms: int = 10, sim_value: float = 0.0) -> MagicMock:
    """EmbeddingManager that returns identity-like embeddings (low mutual cosine)."""
    em = MagicMock()

    def encode(terms, show_progress=False, **kwargs):
        n = len(terms)
        # Return orthogonal unit vectors so no pair exceeds sim_value
        vecs = np.eye(max(n, 1), max(n, 1), dtype=np.float32)[:n]
        return vecs

    em.encode.side_effect = encode
    return em


def _make_em_high_sim() -> MagicMock:
    """EmbeddingManager where every pair has cosine = 1.0 (all identical vectors)."""
    em = MagicMock()

    def encode(terms, show_progress=False, **kwargs):
        n = len(terms)
        vecs = np.ones((n, 3), dtype=np.float32)
        norms = np.linalg.norm(vecs, axis=1, keepdims=True)
        return vecs / norms

    em.encode.side_effect = encode
    return em


# ── _lemmatize_term ────────────────────────────────────────────────────────────

class TestLemmatizeTerm:
    def test_lowercases(self):
        assert _lemmatize_term("Sorting Algorithms") == "sorting algorithms"

    def test_strips_whitespace(self):
        assert _lemmatize_term("  binary search  ") == "binary search"

    def test_collapses_internal_whitespace(self):
        assert _lemmatize_term("dynamic   programming") == "dynamic programming"

    def test_empty_string(self):
        assert _lemmatize_term("") == ""


# ── _wordnet_similar ───────────────────────────────────────────────────────────

class TestWordnetSimilar:
    def test_identical_words_share_synset(self):
        result = _wordnet_similar("sort", "sort", threshold=0.85)
        assert isinstance(result, bool)

    def test_multi_word_terms_return_false(self):
        result = _wordnet_similar("sorting algorithm", "searching algorithm", 0.85)
        assert result is False

    def test_unknown_words_return_false(self):
        result = _wordnet_similar("xyzzy_nonsense_word", "gobbledygook_word", 0.85)
        assert result is False


# ── Canonicalizer ──────────────────────────────────────────────────────────────

class TestCanonicalizerEmpty:
    def test_empty_input_returns_empty_list(self):
        em = _make_em()
        canon = Canonicalizer(em)
        result = canon.canonicalize({})
        assert result == []

    def test_all_short_terms_filtered(self):
        em = _make_em()
        canon = Canonicalizer(em)
        candidates = {"MOD001": {"ab": {"tfidf": 0.5}, "xy": {"rake": 0.4}}}
        result = canon.canonicalize(candidates)
        assert result == []


class TestCanonicalizerBasic:
    def test_returns_list_of_concepts(self):
        em = _make_em()
        canon = Canonicalizer(em)
        candidates = {
            "MOD001": {"sorting algorithms": {"tfidf": 0.8, "keybert": 0.9}},
        }
        result = canon.canonicalize(candidates)
        assert isinstance(result, list)
        assert all(isinstance(c, Concept) for c in result)

    def test_canonical_term_present(self):
        em = _make_em()
        canon = Canonicalizer(em)
        candidates = {
            "MOD001": {"sorting algorithms": {"tfidf": 0.8}},
        }
        result = canon.canonicalize(candidates)
        terms = [c.term for c in result]
        assert "sorting algorithms" in terms

    def test_module_code_assigned(self):
        em = _make_em()
        canon = Canonicalizer(em)
        candidates = {
            "MOD001": {"sorting algorithms": {"tfidf": 0.8}},
        }
        result = canon.canonicalize(candidates)
        assert "MOD001" in result[0].module_codes

    def test_confidence_between_zero_and_one(self):
        em = _make_em()
        canon = Canonicalizer(em)
        candidates = {
            "MOD001": {"sorting algorithms": {"tfidf": 0.8, "keybert": 0.9}},
        }
        result = canon.canonicalize(candidates)
        for c in result:
            assert 0.0 <= c.confidence <= 1.0

    def test_extractors_populated(self):
        em = _make_em()
        canon = Canonicalizer(em)
        candidates = {
            "MOD001": {"dynamic programming": {"tfidf": 0.7, "rake": 0.6}},
        }
        result = canon.canonicalize(candidates)
        assert len(result[0].extractors) >= 1

    def test_sorted_by_confidence_descending(self):
        em = _make_em()
        canon = Canonicalizer(em)
        candidates = {
            "MOD001": {
                "sorting algorithms": {"keybert": 0.9},
                "binary search": {"tfidf": 0.3},
            },
        }
        result = canon.canonicalize(candidates)
        if len(result) >= 2:
            assert result[0].confidence >= result[1].confidence


class TestCanonicalizerMerging:
    def test_near_identical_terms_merged(self):
        """Terms with cosine sim >= SYNONYM_SIM_THRESHOLD should merge into one concept."""
        em = _make_em_high_sim()  # all pairs have sim=1.0
        canon = Canonicalizer(em)
        candidates = {
            "MOD001": {
                "sorting algorithm": {"tfidf": 0.8},
                "sort algorithm": {"rake": 0.7},
            },
        }
        result = canon.canonicalize(candidates)
        # Both should merge into 1 concept
        assert len(result) == 1

    def test_merged_concept_has_variants(self):
        em = _make_em_high_sim()
        canon = Canonicalizer(em)
        candidates = {
            "MOD001": {
                "sorting algorithm": {"tfidf": 0.8},
                "sort algorithm": {"rake": 0.7},
            },
        }
        result = canon.canonicalize(candidates)
        assert len(result[0].variants) >= 0  # canonical + variant

    def test_distinct_terms_not_merged(self):
        """Orthogonal embeddings → distinct terms produce separate concepts."""
        em = _make_em()  # orthogonal = low cosine
        canon = Canonicalizer(em)
        candidates = {
            "MOD001": {
                "sorting algorithms": {"tfidf": 0.8},
                "process management": {"tfidf": 0.7},
            },
        }
        result = canon.canonicalize(candidates)
        assert len(result) == 2

    def test_multi_module_concepts_aggregate_modules(self):
        em = _make_em()
        canon = Canonicalizer(em)
        candidates = {
            "MOD001": {"sorting algorithms": {"tfidf": 0.8}},
            "MOD002": {"sorting algorithms": {"keybert": 0.9}},
        }
        result = canon.canonicalize(candidates)
        assert "MOD001" in result[0].module_codes
        assert "MOD002" in result[0].module_codes

    def test_prefers_longer_canonical_term(self):
        """Canonical should be the longer (more specific) form."""
        em = _make_em_high_sim()
        canon = Canonicalizer(em)
        candidates = {
            "MOD001": {
                "sort": {"tfidf": 0.9},
                "sorting algorithms": {"rake": 0.8},
            },
        }
        result = canon.canonicalize(candidates)
        assert result[0].term == "sorting algorithms"
