"""Tests for evaluation metrics.

Uses stub EmbeddingManager so no model loading occurs.
"""

from __future__ import annotations

import numpy as np
import pytest

from curriculum_mapper.evaluation.metrics import (
    _is_hit,
    average_precision,
    f1_at_k,
    mean_reciprocal_rank,
    precision_at_k,
    recall_at_k,
    top_k_accuracy,
)

# ── Stub EmbeddingManager ──────────────────────────────────────────────────────

class _IdentityEM:
    """Encodes each string as a one-hot vector over a fixed vocabulary."""

    VOCAB = [
        "sorting",
        "binary search",
        "dynamic programming",
        "graph algorithms",
        "greedy algorithms",
        "memory management",
        "scheduling",
        "file systems",
    ]

    def encode(self, texts):
        result = []
        for t in texts:
            t_low = t.lower().strip()
            if t_low in self.VOCAB:
                idx = self.VOCAB.index(t_low)
            else:
                idx = -1
            vec = np.zeros(len(self.VOCAB) + 1, dtype=np.float32)
            if idx >= 0:
                vec[idx] = 1.0
            else:
                vec[-1] = 0.5
            norm = np.linalg.norm(vec)
            result.append(vec / norm if norm > 0 else vec)
        return np.array(result, dtype=np.float32)


EM = _IdentityEM()


# ── _is_hit ────────────────────────────────────────────────────────────────────

class TestIsHit:
    def test_exact_match_is_hit(self):
        em = EM
        pred_emb = em.encode(["sorting"])[0]
        gold_embs = em.encode(["sorting"])
        assert _is_hit(pred_emb, gold_embs, 0.99)

    def test_orthogonal_not_hit(self):
        em = EM
        pred_emb = em.encode(["sorting"])[0]
        gold_embs = em.encode(["scheduling"])
        # One-hot vectors are orthogonal → cosine = 0 < threshold
        assert not _is_hit(pred_emb, gold_embs, 0.85)

    def test_threshold_zero_always_hits(self):
        em = EM
        pred_emb = em.encode(["sorting"])[0]
        gold_embs = em.encode(["scheduling"])
        assert _is_hit(pred_emb, gold_embs, 0.0)


# ── Precision@K ────────────────────────────────────────────────────────────────

class TestPrecisionAtK:
    def test_all_hits(self):
        predicted = ["sorting", "binary search", "graph algorithms"]
        gold = ["sorting", "binary search", "graph algorithms"]
        p = precision_at_k(predicted, gold, k=3, em=EM, threshold=0.99)
        assert p == pytest.approx(1.0)

    def test_no_hits(self):
        predicted = ["sorting", "binary search"]
        gold = ["scheduling", "file systems"]
        p = precision_at_k(predicted, gold, k=2, em=EM, threshold=0.99)
        assert p == pytest.approx(0.0)

    def test_partial_hits(self):
        predicted = ["sorting", "scheduling", "file systems"]
        gold = ["sorting"]
        p = precision_at_k(predicted, gold, k=3, em=EM, threshold=0.99)
        assert p == pytest.approx(1 / 3, abs=0.001)

    def test_empty_predicted(self):
        assert precision_at_k([], ["sorting"], k=5, em=EM) == 0.0

    def test_empty_gold(self):
        assert precision_at_k(["sorting"], [], k=5, em=EM) == 0.0

    def test_k_larger_than_predicted(self):
        predicted = ["sorting"]
        gold = ["sorting"]
        p = precision_at_k(predicted, gold, k=10, em=EM, threshold=0.99)
        assert p == pytest.approx(1 / 10)

    def test_only_top_k_considered(self):
        predicted = ["scheduling", "file systems", "sorting"]  # sorting at pos 3
        gold = ["sorting"]
        p = precision_at_k(predicted, gold, k=2, em=EM, threshold=0.99)
        assert p == pytest.approx(0.0)  # sorting not in top 2


# ── Recall@K ──────────────────────────────────────────────────────────────────

class TestRecallAtK:
    def test_full_recall(self):
        predicted = ["sorting", "binary search"]
        gold = ["sorting", "binary search"]
        r = recall_at_k(predicted, gold, k=2, em=EM, threshold=0.99)
        assert r == pytest.approx(1.0)

    def test_zero_recall(self):
        predicted = ["scheduling", "file systems"]
        gold = ["sorting", "binary search"]
        r = recall_at_k(predicted, gold, k=2, em=EM, threshold=0.99)
        assert r == pytest.approx(0.0)

    def test_partial_recall(self):
        predicted = ["sorting", "scheduling"]
        gold = ["sorting", "binary search"]
        r = recall_at_k(predicted, gold, k=2, em=EM, threshold=0.99)
        assert r == pytest.approx(0.5)

    def test_empty_gold(self):
        assert recall_at_k(["sorting"], [], k=5, em=EM) == 0.0

    def test_empty_predicted(self):
        assert recall_at_k([], ["sorting"], k=5, em=EM) == 0.0


# ── F1@K ──────────────────────────────────────────────────────────────────────

class TestF1AtK:
    def test_perfect_f1(self):
        predicted = ["sorting", "binary search"]
        gold = ["sorting", "binary search"]
        f1 = f1_at_k(predicted, gold, k=2, em=EM, threshold=0.99)
        assert f1 == pytest.approx(1.0)

    def test_zero_f1(self):
        predicted = ["scheduling"]
        gold = ["sorting"]
        f1 = f1_at_k(predicted, gold, k=1, em=EM, threshold=0.99)
        assert f1 == pytest.approx(0.0)

    def test_f1_harmonic_mean(self):
        # P@2 = 0.5, R@2 = 1.0 → F1 = 2*0.5*1.0/1.5 ≈ 0.667
        predicted = ["sorting", "scheduling"]
        gold = ["sorting"]
        f1 = f1_at_k(predicted, gold, k=2, em=EM, threshold=0.99)
        assert f1 == pytest.approx(2 * 0.5 * 1.0 / (0.5 + 1.0), abs=0.001)


# ── Top-K Accuracy ────────────────────────────────────────────────────────────

class TestTopKAccuracy:
    def test_top_1_accuracy(self):
        predicted = [["AL", "OS"], ["DS"]]
        gold = ["AL", "DS"]
        acc = top_k_accuracy(predicted, gold, k=1)
        assert acc == pytest.approx(1.0)

    def test_top_1_miss(self):
        predicted = [["OS", "AL"]]
        gold = ["AL"]
        acc = top_k_accuracy(predicted, gold, k=1)
        assert acc == pytest.approx(0.0)

    def test_top_3_hit(self):
        predicted = [["OS", "DS", "AL"]]
        gold = ["AL"]
        assert top_k_accuracy(predicted, gold, k=3) == pytest.approx(1.0)

    def test_empty_gold(self):
        assert top_k_accuracy([["AL"]], [], k=3) == 0.0

    def test_partial_accuracy(self):
        predicted = [["AL"], ["OS"], ["DS"]]
        gold = ["AL", "DS", "AL"]
        acc = top_k_accuracy(predicted, gold, k=1)
        assert acc == pytest.approx(1 / 3, abs=0.001)


# ── MRR ───────────────────────────────────────────────────────────────────────

class TestMRR:
    def test_rank_1(self):
        predicted = [["AL", "OS"]]
        gold = ["AL"]
        mrr = mean_reciprocal_rank(predicted, gold)
        assert mrr == pytest.approx(1.0)

    def test_rank_2(self):
        predicted = [["OS", "AL"]]
        gold = ["AL"]
        mrr = mean_reciprocal_rank(predicted, gold)
        assert mrr == pytest.approx(0.5)

    def test_not_found(self):
        predicted = [["OS", "DS"]]
        gold = ["AL"]
        mrr = mean_reciprocal_rank(predicted, gold)
        assert mrr == pytest.approx(0.0)

    def test_multiple_queries(self):
        predicted = [["AL", "OS"], ["OS", "AL"]]
        gold = ["AL", "AL"]
        mrr = mean_reciprocal_rank(predicted, gold)
        assert mrr == pytest.approx((1.0 + 0.5) / 2)

    def test_empty_gold(self):
        assert mean_reciprocal_rank([["AL"]], []) == 0.0


# ── Average Precision ─────────────────────────────────────────────────────────

class TestAveragePrecision:
    def test_all_correct(self):
        predicted = ["sorting", "binary search"]
        gold = ["sorting", "binary search"]
        ap = average_precision(predicted, gold, EM, threshold=0.99)
        assert ap == pytest.approx(1.0)

    def test_none_correct(self):
        predicted = ["scheduling"]
        gold = ["sorting"]
        ap = average_precision(predicted, gold, EM, threshold=0.99)
        assert ap == pytest.approx(0.0)

    def test_empty_inputs(self):
        assert average_precision([], ["sorting"], EM) == 0.0
        assert average_precision(["sorting"], [], EM) == 0.0

    def test_partial_credit_order(self):
        # Correct item at rank 2: AP = (1/2 * 1) / 1 = 0.5
        predicted = ["scheduling", "sorting"]
        gold = ["sorting"]
        ap = average_precision(predicted, gold, EM, threshold=0.99)
        assert ap == pytest.approx(0.5, abs=0.01)
