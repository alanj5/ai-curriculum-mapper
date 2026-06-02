"""Hybrid aligner: combines lexical (35%) and semantic (65%) scores.

Deduplicates by KA (keeps best topic per knowledge area), then applies
ambiguity detection and produces AlignmentResult objects.

Weight justification (§3.4 of final report):
  Lexical anchors exact technical terms at high precision.
  Semantic generalises across paraphrase at high recall.
  65/35 empirically validated in evaluation (Sect. 5) and motivated by
  Reimers & Gurevych (2019) on short technical text.
"""

from __future__ import annotations

import logging

from curriculum_mapper.alignment.ambiguity import is_ambiguous
from curriculum_mapper.alignment.lexical import LexicalAligner
from curriculum_mapper.alignment.semantic import SemanticAligner
from curriculum_mapper.config import (
    LEXICAL_WEIGHT,
    SEMANTIC_WEIGHT,
    SIMILARITY_THRESHOLD,
    TOP_K_ALIGNMENTS,
)
from curriculum_mapper.ingestion.schema import AlignmentResult, Concept
from curriculum_mapper.nlp.embeddings import EmbeddingManager

logger = logging.getLogger(__name__)


class HybridAligner:
    """Combine lexical + semantic scores into AlignmentResult objects."""

    def __init__(self, ka_data: dict, embedding_manager: EmbeddingManager) -> None:
        self._lexical = LexicalAligner(ka_data)
        self._semantic = SemanticAligner(ka_data, embedding_manager)
        self._em = embedding_manager

    def align(self, concept: Concept) -> list[AlignmentResult]:
        """Align one concept and return up to TOP_K_ALIGNMENTS results."""
        # Encode concept term
        emb = self._em.encode([concept.term])[0]  # (384,)

        lex_results = {
            (r["ka_code"], r["ka_topic"]): r["score"]
            for r in self._lexical.align(concept.term)
        }
        sem_results = {
            (r["ka_code"], r["ka_topic"]): r["score"]
            for r in self._semantic.align(emb)
        }

        all_keys = set(lex_results) | set(sem_results)
        hybrid: list[dict] = []
        for key in all_keys:
            l_score = lex_results.get(key, 0.0)
            s_score = sem_results.get(key, 0.0)
            h_score = LEXICAL_WEIGHT * l_score + SEMANTIC_WEIGHT * s_score
            if h_score >= SIMILARITY_THRESHOLD:
                hybrid.append({"ka_code": key[0], "ka_topic": key[1], "score": h_score})

        # Deterministic ordering: by score desc, then KA code and topic asc, so
        # score ties are broken reproducibly (not by hash-randomised set order).
        hybrid.sort(key=lambda r: (-r["score"], r["ka_code"], r["ka_topic"]))

        # Dedup: keep best topic per KA
        seen_ka: set[str] = set()
        deduped: list[dict] = []
        for r in hybrid:
            if r["ka_code"] not in seen_ka:
                seen_ka.add(r["ka_code"])
                deduped.append(r)
        deduped = deduped[:TOP_K_ALIGNMENTS]

        ambiguous = is_ambiguous(deduped)

        return [
            AlignmentResult(
                concept_id=concept.id,
                ka_code=r["ka_code"],
                ka_topic=r["ka_topic"],
                method="hybrid",
                score=round(r["score"], 4),
                rank=rank + 1,
                is_ambiguous=ambiguous and rank < 2,
            )
            for rank, r in enumerate(deduped)
        ]
