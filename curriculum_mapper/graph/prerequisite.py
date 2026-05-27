"""Implicit prerequisite inference.

Beyond explicit prerequisites in module data, infers implicit ones:
If module B contains ≥70% of module A's high-confidence concepts AND
B is at a higher or equal level, then A is an implicit prerequisite of B.

This allows the system to suggest prerequisite relationships even when
module descriptors don't list them explicitly — common for Imperial modules.
"""

from __future__ import annotations

from curriculum_mapper.ingestion.schema import Concept, ModuleDescriptor


def infer_prerequisites(
    modules: list[ModuleDescriptor],
    concepts: list[Concept],
    confidence_threshold: float = 0.5,
    overlap_threshold: float = 0.7,
) -> list[tuple[str, str, float]]:
    """Return (from_module, to_module, overlap_score) for inferred edges.

    Parameters
    ----------
    confidence_threshold:
        Only high-confidence concepts are considered for overlap.
    overlap_threshold:
        Minimum fraction of A's concepts that B must contain.
    """
    # Build high-confidence concept sets per module
    concept_sets: dict[str, set[str]] = {m.code: set() for m in modules}
    for c in concepts:
        if c.confidence >= confidence_threshold:
            for mc in c.module_codes:
                if mc in concept_sets:
                    concept_sets[mc].add(c.id)

    levels = {m.code: m.level for m in modules}
    existing_prereqs: set[tuple[str, str]] = set()
    for m in modules:
        for p in m.prerequisites:
            existing_prereqs.add((p, m.code))

    inferred: list[tuple[str, str, float]] = []
    module_codes = list(concept_sets.keys())

    for i, a in enumerate(module_codes):
        set_a = concept_sets[a]
        if not set_a:
            continue
        for b in module_codes:
            if a == b:
                continue
            if (a, b) in existing_prereqs:
                continue
            if levels.get(b, 1) < levels.get(a, 1):
                continue  # B must be same or higher level
            set_b = concept_sets[b]
            overlap = len(set_a & set_b) / len(set_a)
            if overlap >= overlap_threshold and len(set_b) > len(set_a):
                inferred.append((a, b, round(overlap, 3)))

    return sorted(inferred, key=lambda x: -x[2])
