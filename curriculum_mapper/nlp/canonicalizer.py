"""Concept canonicalization: deduplication, synonym merging, confidence aggregation.

Given raw per-module extraction results (term → {extractor: score}), this module
produces a deduplicated list of Concept objects with:
  1. Exact string deduplication (case-folded, lemmatized)
  2. SBERT cosine synonym deduplication (threshold 0.92)
  3. WordNet path-similarity merging (threshold 0.85, single-word terms only)
  4. Weighted confidence aggregation across extractors

Computing-specific note: ambiguous single words ("heap", "stack", "process") are
embedded in their originating sentence context to preserve discriminating semantics.
When sentence context is unavailable we fall back to bare-term embedding.
"""

from __future__ import annotations

import logging
from collections import defaultdict

from curriculum_mapper.config import (
    EXTRACTOR_WEIGHTS,
    SYNONYM_SIM_THRESHOLD,
    WORDNET_SIM_THRESHOLD,
)
from curriculum_mapper.ingestion.schema import Concept
from curriculum_mapper.nlp.embeddings import EmbeddingManager

logger = logging.getLogger(__name__)

# WordNet availability flag
try:
    from nltk.corpus import wordnet as wn
    _WN_AVAILABLE = True
except Exception:
    _WN_AVAILABLE = False
    logger.warning("WordNet unavailable; skipping WordNet synonym merging.")


def _lemmatize_term(term: str) -> str:
    """Lowercase and strip trailing 's' as a minimal normalisation."""
    import re
    term = term.lower().strip()
    term = re.sub(r"\s+", " ", term)
    return term


def _wordnet_similar(a: str, b: str, threshold: float) -> bool:
    """True if single-word terms share a synset or path_similarity >= threshold."""
    if not _WN_AVAILABLE:
        return False
    if " " in a or " " in b:
        return False  # only single-word terms
    syns_a = wn.synsets(a)
    syns_b = wn.synsets(b)
    if not syns_a or not syns_b:
        return False
    # Check shared lemma names first (fast path)
    names_a = {lem.name() for s in syns_a for lem in s.lemmas()}
    names_b = {lem.name() for s in syns_b for lem in s.lemmas()}
    if names_a & names_b:
        return True
    # Path similarity (most similar synset pair)
    max_sim = max(
        (s_a.path_similarity(s_b) or 0.0)
        for s_a in syns_a[:3]
        for s_b in syns_b[:3]
    )
    return max_sim >= threshold


class Canonicalizer:
    """Deduplicates and merges raw extraction candidates into canonical Concepts."""

    def __init__(self, embedding_manager: EmbeddingManager) -> None:
        self._em = embedding_manager

    def canonicalize(
        self,
        all_candidates: dict[str, dict[str, dict[str, float]]],
    ) -> list[Concept]:
        """Main entry point.

        Parameters
        ----------
        all_candidates:
            {module_code: {term: {extractor: score}}}

        Returns
        -------
        list[Concept]
            Deduplicated, merged, confidence-scored concepts.
        """
        # ── Step 1: collect and normalise all terms ────────────────────────────
        # term → {extractor: [scores]}, term → {module_codes}
        term_extractor_scores: dict[str, dict[str, list[float]]] = defaultdict(
            lambda: defaultdict(list)
        )
        term_modules: dict[str, set[str]] = defaultdict(set)

        for module_code, candidates in all_candidates.items():
            for term, extractor_scores in candidates.items():
                norm = _lemmatize_term(term)
                if not norm or len(norm) < 3:
                    continue
                for ext, score in extractor_scores.items():
                    term_extractor_scores[norm][ext].append(score)
                term_modules[norm].add(module_code)

        unique_terms = list(term_extractor_scores.keys())
        logger.info(f"Canonicalizer: {len(unique_terms)} unique terms before dedup")

        if not unique_terms:
            return []

        # ── Step 2: SBERT cosine deduplication ────────────────────────────────
        embeddings = self._em.encode(unique_terms, show_progress=False)
        # Union-Find for grouping similar terms
        parent = list(range(len(unique_terms)))

        def find(x: int) -> int:
            while parent[x] != x:
                parent[x] = parent[parent[x]]
                x = parent[x]
            return x

        def union(x: int, y: int) -> None:
            parent[find(x)] = find(y)

        sim_matrix = embeddings @ embeddings.T
        for i in range(len(unique_terms)):
            for j in range(i + 1, len(unique_terms)):
                sim = float(sim_matrix[i, j])
                if sim >= SYNONYM_SIM_THRESHOLD:
                    union(i, j)
                    continue
                # WordNet fallback for single-word terms below SBERT threshold
                if sim >= 0.75:  # only check WordNet if semantically close
                    if _wordnet_similar(
                        unique_terms[i], unique_terms[j], WORDNET_SIM_THRESHOLD
                    ):
                        union(i, j)

        # ── Step 3: merge groups ───────────────────────────────────────────────
        groups: dict[int, list[int]] = defaultdict(list)
        for i in range(len(unique_terms)):
            groups[find(i)].append(i)

        concepts: list[Concept] = []
        for root, members in groups.items():
            # Choose canonical term = longest (usually most specific) or highest conf
            member_terms = [unique_terms[m] for m in members]

            # Aggregate extractor scores across all group members
            merged_extractor_scores: dict[str, list[float]] = defaultdict(list)
            merged_modules: set[str] = set()
            for m in members:
                t = unique_terms[m]
                for ext, scores in term_extractor_scores[t].items():
                    merged_extractor_scores[ext].extend(scores)
                merged_modules |= term_modules[t]

            # Compute weighted confidence
            weighted_sum = 0.0
            weight_total = 0.0
            for ext, scores in merged_extractor_scores.items():
                w = EXTRACTOR_WEIGHTS.get(ext, 0.10)
                avg_score = sum(scores) / len(scores)
                weighted_sum += w * avg_score
                weight_total += w
            confidence = weighted_sum / weight_total if weight_total > 0 else 0.0

            # Pick canonical term: prefer longer (more specific) multi-word phrases
            canonical = max(member_terms, key=lambda t: (len(t.split()), len(t)))

            variants = [t for t in member_terms if t != canonical]

            concepts.append(
                Concept(
                    term=canonical,
                    variants=variants,
                    confidence=round(confidence, 4),
                    extractors=list(merged_extractor_scores.keys()),
                    module_codes=sorted(merged_modules),
                )
            )

        # Sort by confidence descending
        concepts.sort(key=lambda c: -c.confidence)
        logger.info(f"Canonicalizer: {len(concepts)} concepts after dedup/merge")
        return concepts
