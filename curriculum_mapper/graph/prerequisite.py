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


def infer_module_prerequisites_from_concept_dag(
    modules: list[ModuleDescriptor],
    concepts: list[Concept],
    cprereq_edges,
    *,
    top_k: int = 3,
    min_votes: int = 5,
) -> list[tuple[str, str, int]]:
    """Derive module prerequisite edges from the directed concept-prerequisite DAG.

    The Department does not publish module prerequisites, so they are inferred:
    module *A* is a prerequisite of module *B* when concepts taught in *A* are
    prerequisites (in the concept DAG) of concepts taught in *B*, and *A* is at a
    strictly lower level than *B* (which keeps the module relation acyclic and
    consistent with the year structure). Each dependent keeps its top-``top_k``
    prerequisite modules by the number of supporting concept-prerequisite links
    (requiring at least ``min_votes`` links to avoid spurious single-concept ties).

    Each ``cprereq_edge`` must expose ``from_concept_id`` (the prerequisite concept)
    and ``to_concept_id`` (the dependent concept).

    Returns ``(prereq_code, module_code, votes)`` — i.e. prereq → dependent.
    """
    import collections

    level = {m.code: (m.level or 1) for m in modules}
    # Cohort = the first token of ``source`` so provenance suffixes (e.g.
    # "imperial (descriptor page unavailable; …)") still group with their cohort.
    def _cohort(m: ModuleDescriptor) -> str | None:
        s = getattr(m, "source", None)
        return s.split()[0] if s else None

    source = {m.code: _cohort(m) for m in modules}
    teach: dict[str, set[str]] = collections.defaultdict(set)
    for c in concepts:
        for mc in c.module_codes:
            teach[c.id].add(mc)

    votes: collections.Counter = collections.Counter()
    for e in cprereq_edges:
        for a in teach.get(e.from_concept_id, ()):
            for b in teach.get(e.to_concept_id, ()):
                # Same cohort only (a prerequisite belongs to the same programme)
                # and strictly lower level (keeps the relation acyclic).
                if (
                    a != b
                    and source.get(a) == source.get(b)
                    and level.get(a, 1) < level.get(b, 1)
                ):
                    votes[(a, b)] += 1

    by_dependent: dict[str, list[tuple[str, int]]] = collections.defaultdict(list)
    for (a, b), n in votes.items():
        if n >= min_votes:
            by_dependent[b].append((a, n))

    edges: list[tuple[str, str, int]] = []
    for b, candidates in by_dependent.items():
        for a, n in sorted(candidates, key=lambda x: -x[1])[:top_k]:
            edges.append((a, b, n))
    return sorted(edges, key=lambda t: -t[2])
