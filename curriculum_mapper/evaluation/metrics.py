"""Evaluation metrics for concept extraction and alignment.

Concept extraction metrics use SBERT partial credit (cosine ≥ 0.85) rather than
exact string matching. This is essential because surface variants like "sorting
algorithm" vs "sorting algorithms" are semantically identical but string-different.

References:
  - Precision@K, Recall@K, F1@K: standard IR metrics (Manning et al., 2008)
  - MRR: Mean Reciprocal Rank (Voorhees, 1999)
  - SBERT partial credit threshold 0.85: chosen to handle plurals, hyphens, and
    minor paraphrases while rejecting genuinely different concepts.
"""

from __future__ import annotations

import logging

import numpy as np

from curriculum_mapper.config import SBERT_MATCH_THRESHOLD

logger = logging.getLogger(__name__)

PARTIAL_CREDIT_THRESHOLD = SBERT_MATCH_THRESHOLD


def _is_hit(pred_emb: np.ndarray, gold_embs: np.ndarray, threshold: float) -> bool:
    """True if pred embedding is within threshold cosine of any gold embedding."""
    sims = pred_emb @ gold_embs.T
    return float(np.max(sims)) >= threshold


def precision_at_k(
    predicted: list[str],
    gold: list[str],
    k: int,
    em,
    threshold: float = PARTIAL_CREDIT_THRESHOLD,
) -> float:
    """Fraction of top-K predictions that match a gold concept (partial credit)."""
    predicted_k = predicted[:k]
    if not predicted_k or not gold:
        return 0.0
    pred_embs = em.encode(predicted_k)
    gold_embs = em.encode(gold)
    hits = sum(1 for p_emb in pred_embs if _is_hit(p_emb, gold_embs, threshold))
    return round(hits / k, 4)


def recall_at_k(
    predicted: list[str],
    gold: list[str],
    k: int,
    em,
    threshold: float = PARTIAL_CREDIT_THRESHOLD,
) -> float:
    """Fraction of gold concepts covered by top-K predictions."""
    predicted_k = predicted[:k]
    if not gold:
        return 0.0
    if not predicted_k:
        return 0.0
    gold_embs = em.encode(gold)
    pred_embs = em.encode(predicted_k)
    covered = sum(1 for g_emb in gold_embs if _is_hit(g_emb, pred_embs, threshold))
    return round(covered / len(gold), 4)


def f1_at_k(
    predicted: list[str],
    gold: list[str],
    k: int,
    em,
    threshold: float = PARTIAL_CREDIT_THRESHOLD,
) -> float:
    p = precision_at_k(predicted, gold, k, em, threshold)
    r = recall_at_k(predicted, gold, k, em, threshold)
    if p + r == 0:
        return 0.0
    return round(2 * p * r / (p + r), 4)


def top_k_accuracy(
    predicted_ka_lists: list[list[str]],
    gold_kas: list[str],
    k: int,
) -> float:
    """Fraction of alignment predictions where gold KA appears in top-K."""
    if not gold_kas:
        return 0.0
    hits = sum(
        1
        for pred, gold in zip(predicted_ka_lists, gold_kas)
        if gold in pred[:k]
    )
    return round(hits / len(gold_kas), 4)


def mean_reciprocal_rank(
    predicted_ka_lists: list[list[str]],
    gold_kas: list[str],
) -> float:
    """MRR for alignment: average of 1/rank of first correct KA."""
    if not gold_kas:
        return 0.0
    rrs = []
    for pred, gold in zip(predicted_ka_lists, gold_kas):
        if gold in pred:
            rrs.append(1.0 / (pred.index(gold) + 1))
        else:
            rrs.append(0.0)
    return round(sum(rrs) / len(rrs), 4)


def average_precision(
    predicted: list[str],
    gold: list[str],
    em,
    threshold: float = PARTIAL_CREDIT_THRESHOLD,
) -> float:
    """Area under the precision-recall curve (AP) using partial credit."""
    if not gold or not predicted:
        return 0.0
    gold_embs = em.encode(gold)
    pred_embs = em.encode(predicted)

    hits = 0
    precision_sum = 0.0
    for i, p_emb in enumerate(pred_embs):
        if _is_hit(p_emb, gold_embs, threshold):
            hits += 1
            precision_sum += hits / (i + 1)
    return round(precision_sum / len(gold), 4) if gold else 0.0
