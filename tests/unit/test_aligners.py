"""Tests for lexical, semantic, and hybrid aligners (Week 2)."""

from __future__ import annotations

from unittest.mock import MagicMock

import numpy as np

from curriculum_mapper.alignment.ambiguity import is_ambiguous
from curriculum_mapper.alignment.lexical import LexicalAligner
from curriculum_mapper.ingestion.schema import Concept

# ── Minimal CS2023 KA fixture ──────────────────────────────────────────────────

KA_DATA = {
    "AL": {
        "name": "Algorithms and Complexity",
        "topics": [
            "Sorting algorithms",
            "Binary search",
            "Dynamic programming",
            "Graph algorithms",
            "Greedy algorithms",
        ],
    },
    "OS": {
        "name": "Operating Systems",
        "topics": [
            "Process management",
            "Memory management",
            "Virtual memory",
            "File systems",
            "Scheduling algorithms",
        ],
    },
    "DS": {
        "name": "Data Structures",
        "topics": [
            "Arrays and linked lists",
            "Hash tables",
            "Binary trees",
            "Heaps",
            "Graphs",
        ],
    },
}


# ── Lexical Aligner ───────────────────────────────────────────────────────────

class TestLexicalAligner:
    def setup_method(self):
        self.aligner = LexicalAligner(KA_DATA)

    def test_exact_token_match(self):
        results = self.aligner.align("sorting algorithms")
        assert len(results) > 0
        # "sorting algorithms" ≈ "Sorting algorithms" (Jaccard = 1.0)
        best = max(results, key=lambda r: r["score"])
        assert best["ka_code"] == "AL"
        assert best["score"] > 0.5

    def test_partial_token_overlap(self):
        results = self.aligner.align("graph search")
        [r["ka_code"] for r in results]
        # Should match "Graph algorithms" in AL
        assert len(results) > 0

    def test_below_threshold_returns_empty(self):
        results = self.aligner.align("xyzzy nonsense")
        assert results == []

    def test_edit_distance_match(self):
        # "dinamyc programming" — one-char edit — should still match
        results = self.aligner.align("dinamyc programming")
        assert len(results) > 0

    def test_case_insensitive(self):
        r1 = self.aligner.align("SORTING ALGORITHMS")
        r2 = self.aligner.align("sorting algorithms")
        assert len(r1) == len(r2)

    def test_returns_list_of_dicts(self):
        results = self.aligner.align("binary search")
        assert isinstance(results, list)
        if results:
            r = results[0]
            assert "ka_code" in r
            assert "ka_topic" in r
            assert "score" in r
            assert 0.0 <= r["score"] <= 1.0

    def test_single_word_match(self):
        results = self.aligner.align("scheduling")
        assert len(results) > 0


# ── Ambiguity Detection ───────────────────────────────────────────────────────

class TestIsAmbiguous:
    def test_empty_list(self):
        assert is_ambiguous([]) is False

    def test_single_result(self):
        assert is_ambiguous([{"score": 0.8}]) is False

    def test_large_gap_not_ambiguous(self):
        results = [{"score": 0.9}, {"score": 0.7}]
        # gap = 0.2 > AMBIGUITY_MARGIN (0.08)
        assert is_ambiguous(results) is False

    def test_small_gap_ambiguous(self):
        results = [{"score": 0.85}, {"score": 0.82}]
        # gap = 0.03 < AMBIGUITY_MARGIN (0.08)
        assert is_ambiguous(results) is True

    def test_exact_gap_boundary(self):
        from curriculum_mapper.config import AMBIGUITY_MARGIN
        results = [{"score": 0.8}, {"score": 0.8 - AMBIGUITY_MARGIN + 0.001}]
        assert is_ambiguous(results) is True

    def test_gap_clearly_above_margin(self):
        from curriculum_mapper.config import AMBIGUITY_MARGIN
        # Gap of 2x AMBIGUITY_MARGIN is clearly not ambiguous
        results = [{"score": 0.9}, {"score": 0.9 - 2 * AMBIGUITY_MARGIN}]
        assert is_ambiguous(results) is False


# ── Semantic Aligner (mocked) ─────────────────────────────────────────────────

class TestSemanticAligner:
    def _make_aligner(self):
        mock_em = MagicMock()
        n_topics = sum(len(v["topics"]) for v in KA_DATA.values())
        # Deterministic embeddings: topic i = e_i (canonical basis)
        topic_embs = np.zeros((n_topics, 384), dtype=np.float32)
        for i in range(min(n_topics, 384)):
            topic_embs[i, i] = 1.0
        mock_em.encode.return_value = topic_embs

        from curriculum_mapper.alignment.semantic import SemanticAligner
        aligner = SemanticAligner(KA_DATA, mock_em)
        return aligner

    def test_returns_list(self):
        aligner = self._make_aligner()
        query_emb = np.zeros(384, dtype=np.float32)
        query_emb[0] = 1.0
        results = aligner.align(query_emb)
        assert isinstance(results, list)

    def test_top_result_has_highest_score(self):
        aligner = self._make_aligner()
        # Query aligned with topic index 0
        query_emb = np.zeros(384, dtype=np.float32)
        query_emb[0] = 1.0
        results = aligner.align(query_emb)
        if len(results) >= 2:
            assert results[0]["score"] >= results[1]["score"]

    def test_score_in_range(self):
        aligner = self._make_aligner()
        query_emb = np.random.randn(384).astype(np.float32)
        query_emb /= np.linalg.norm(query_emb)
        results = aligner.align(query_emb)
        for r in results:
            assert 0.0 <= r["score"] <= 1.0

    def test_result_dict_keys(self):
        aligner = self._make_aligner()
        query_emb = np.zeros(384, dtype=np.float32)
        query_emb[0] = 1.0
        results = aligner.align(query_emb)
        for r in results:
            assert "ka_code" in r
            assert "ka_topic" in r
            assert "score" in r


# ── Hybrid Aligner (mocked) ───────────────────────────────────────────────────

class TestHybridAligner:
    def _make_aligner_and_concept(self):
        mock_em = MagicMock()
        # Encode returns a matrix of L2-normalised random vectors
        def encode_side_effect(texts):
            n = len(texts)
            vecs = np.zeros((n, 384), dtype=np.float32)
            vecs[:, 0] = 1.0  # all point in dimension 0
            return vecs

        mock_em.encode.side_effect = encode_side_effect

        # Pre-encode topics manually
        n_topics = sum(len(v["topics"]) for v in KA_DATA.values())
        topic_embs = np.zeros((n_topics, 384), dtype=np.float32)
        topic_embs[:, 0] = 1.0  # all topics also point in dim 0 → high cosine

        from curriculum_mapper.alignment.hybrid import HybridAligner
        from curriculum_mapper.alignment.semantic import SemanticAligner

        # Patch SemanticAligner init to avoid re-encoding
        sem = SemanticAligner.__new__(SemanticAligner)
        sem._em = mock_em
        sem._topic_map = []
        for ka_code, ka_info in KA_DATA.items():
            for topic in ka_info["topics"]:
                sem._topic_map.append((ka_code, topic))
        sem._topic_embeddings = topic_embs

        from curriculum_mapper.alignment.lexical import LexicalAligner
        lex = LexicalAligner(KA_DATA)

        hybrid = HybridAligner.__new__(HybridAligner)
        hybrid._lexical = lex
        hybrid._semantic = sem
        hybrid._em = mock_em

        concept = Concept(
            term="sorting algorithms",
            confidence=0.8,
            extractors=["tfidf"],
            module_codes=["IC50001"],
        )
        return hybrid, concept

    def test_returns_alignment_results(self):
        from curriculum_mapper.ingestion.schema import AlignmentResult
        hybrid, concept = self._make_aligner_and_concept()
        results = hybrid.align(concept)
        assert isinstance(results, list)
        for r in results:
            assert isinstance(r, AlignmentResult)

    def test_results_have_correct_concept_id(self):
        hybrid, concept = self._make_aligner_and_concept()
        results = hybrid.align(concept)
        for r in results:
            assert r.concept_id == concept.id

    def test_ranks_are_sequential(self):
        hybrid, concept = self._make_aligner_and_concept()
        results = hybrid.align(concept)
        for i, r in enumerate(results):
            assert r.rank == i + 1

    def test_scores_decrease_with_rank(self):
        hybrid, concept = self._make_aligner_and_concept()
        results = hybrid.align(concept)
        if len(results) >= 2:
            assert results[0].score >= results[1].score

    def test_max_k_results(self):
        from curriculum_mapper.config import TOP_K_ALIGNMENTS
        hybrid, concept = self._make_aligner_and_concept()
        results = hybrid.align(concept)
        assert len(results) <= TOP_K_ALIGNMENTS

    def test_method_is_hybrid(self):
        hybrid, concept = self._make_aligner_and_concept()
        results = hybrid.align(concept)
        for r in results:
            assert r.method == "hybrid"
