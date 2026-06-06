"""Directed concept→concept prerequisite inference (DAG-safe).

Beyond module-level prerequisites (``graph/prerequisite.py``), this realises the
interim's promised *directed concept graph* whose edges are prerequisites
("culled from course metadata or automatically with heuristics", §3.2.3;
"concept–concept edges enable prerequisite reasoning", §2.5.1).

Heuristic (acyclic by construction): concept *A* is a prerequisite of concept
*B* when the two are **related** and *A* is introduced at a **strictly lower**
curriculum level than *B*. A concept's *introduction level* is the lowest level
among the modules that teach it (the same notion the UI's "introduced here"
uses). Relatedness is any of:

  * they share at least one module (co-taught), or
  * they share their rank-1 CS2023 Knowledge Area, or
  * their SBERT cosine ≥ a threshold.

Strict low→high level ordering guarantees a DAG (no cycles), satisfying §2.5.3
("avoid prerequisites that would create cycles") and enabling the topological /
path metrics of §2.6. Edges are pruned to the top-k strongest prerequisites per
dependent concept to keep the graph legible.
"""

from __future__ import annotations

import logging

import numpy as np

from curriculum_mapper.config import (
    CONCEPT_PREREQ_MIN_CONFIDENCE,
    CONCEPT_PREREQ_RELATEDNESS_FLOOR,
    CONCEPT_PREREQ_SBERT_THRESHOLD,
    CONCEPT_PREREQ_TOP_K,
)
from curriculum_mapper.ingestion.schema import ConceptPrerequisite

logger = logging.getLogger(__name__)


def infer_concept_prerequisites(
    concepts: list,
    modules: list,
    best_alignments: dict,
    em,
    *,
    min_confidence: float = CONCEPT_PREREQ_MIN_CONFIDENCE,
    sbert_threshold: float = CONCEPT_PREREQ_SBERT_THRESHOLD,
    relatedness_floor: float = CONCEPT_PREREQ_RELATEDNESS_FLOOR,
    top_k: int = CONCEPT_PREREQ_TOP_K,
) -> list[ConceptPrerequisite]:
    """Return directed concept→concept prerequisite edges (DAG-safe).

    ``best_alignments`` maps concept_id → its rank-1 ``AlignmentResult`` (for the
    same-KA relatedness signal); ``em`` is an ``EmbeddingManager``.
    """
    level_of = {m.code: m.level for m in modules}

    cand = [c for c in concepts if c.confidence >= min_confidence]
    intro: dict[str, int] = {}
    for c in cand:
        levels = [level_of[mc] for mc in c.module_codes if mc in level_of]
        if levels:
            intro[c.id] = min(levels)
    cand = [c for c in cand if c.id in intro]
    if len(cand) < 2:
        return []

    mods_of = {c.id: set(c.module_codes) for c in cand}
    ka_of = {
        c.id: (best_alignments[c.id].ka_code if c.id in best_alignments else None)
        for c in cand
    }

    # SBERT cosine matrix over candidate terms (L2-normalised dot product).
    embs = np.asarray(em.encode([c.term for c in cand]), dtype=np.float32)
    embs /= np.linalg.norm(embs, axis=1, keepdims=True) + 1e-9
    cos = embs @ embs.T
    pos = {c.id: i for i, c in enumerate(cand)}

    edges: list[ConceptPrerequisite] = []
    for b in cand:
        lb, bi = intro[b.id], pos[b.id]
        candidates: list[tuple[str, float, str]] = []
        for a in cand:
            if a.id == b.id or intro[a.id] >= lb:
                continue  # strict lower-level prerequisite only (DAG safety)
            score, method = 0.0, ""
            shared = mods_of[a.id] & mods_of[b.id]
            if shared:
                jac = len(shared) / len(mods_of[a.id] | mods_of[b.id])
                score, method = 0.5 + 0.5 * jac, "shared_module"
            if ka_of[a.id] and ka_of[a.id] == ka_of[b.id] and score < 0.5:
                score, method = 0.5, "same_ka"
            c_cos = float(cos[pos[a.id], bi])
            if c_cos >= sbert_threshold and c_cos > score:
                score, method = c_cos, "sbert"
            if score >= relatedness_floor:
                candidates.append((a.id, score, method))
        candidates.sort(key=lambda x: -x[1])
        for a_id, score, method in candidates[:top_k]:
            edges.append(
                ConceptPrerequisite(
                    from_concept_id=a_id,
                    to_concept_id=b.id,
                    confidence=round(score, 4),
                    method=method,
                    inferred=True,
                )
            )

    logger.info(
        "Inferred %d concept-prerequisite edges over %d candidate concepts.",
        len(edges), len(cand),
    )
    return edges
