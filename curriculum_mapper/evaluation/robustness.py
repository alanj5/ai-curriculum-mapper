"""Perturbation-robustness analysis for the curriculum graph.

Measures how stable the downstream curriculum diagnostics are when the
lowest-confidence concepts are pruned from the extracted set. For each removal
fraction we drop the lowest-confidence concepts (and their alignments), rebuild
the module-module similarity graph, and recompute KA coverage, community
structure, and redundancies. Large changes under small perturbations would
indicate that the findings rest on noisy, low-confidence concepts; small,
graceful changes indicate the diagnostics are robust.

This was identified as future work in the interim report (Section 4.6, "Threats
to validity"). It has no external dependencies and reuses the production graph
analytics so the f=0 row reproduces the live graph exactly.
"""

from __future__ import annotations

import logging

import networkx as nx

from curriculum_mapper.config import SHARED_CONCEPT_EDGE_MIN
from curriculum_mapper.graph.analytics import (
    compute_ka_coverage_full,
    detect_communities,
)
from curriculum_mapper.graph.gap_detector import generate_coverage_report

logger = logging.getLogger(__name__)


def _module_similarity_graph(modules, concepts) -> nx.Graph:
    """Module-module graph (prerequisite + shared-concept similarity edges).

    Mirrors ``graph.builder.build_module_module_graph`` but does NOT persist the
    pickle, so it is safe to call repeatedly without clobbering the live graph.
    """
    G = nx.Graph()
    module_set = {m.code for m in modules}
    for m in modules:
        G.add_node(m.code)

    for m in modules:
        for prereq in m.prerequisites:
            if prereq in module_set and prereq != m.code and not G.has_edge(prereq, m.code):
                G.add_edge(prereq, m.code, type="prerequisite", weight=1.0)

    concept_sets: dict[str, set[str]] = {m.code: set() for m in modules}
    for c in concepts:
        for mc in c.module_codes:
            if mc in concept_sets:
                concept_sets[mc].add(c.id)

    codes = list(concept_sets.keys())
    for i in range(len(codes)):
        for j in range(i + 1, len(codes)):
            a, b = codes[i], codes[j]
            shared = concept_sets[a] & concept_sets[b]
            if len(shared) >= SHARED_CONCEPT_EDGE_MIN:
                union = concept_sets[a] | concept_sets[b]
                jaccard = len(shared) / len(union) if union else 0.0
                if G.has_edge(a, b):
                    G[a][b]["similarity"] = round(jaccard, 4)
                else:
                    G.add_edge(a, b, type="similarity", weight=round(jaccard, 4))
    return G


def run_perturbation_robustness(
    storage,
    ka_data: dict,
    fractions: list[float] | None = None,
) -> dict[float, dict]:
    """Drop the lowest-confidence ``f`` of concepts and re-measure the graph.

    Returns ``{fraction: {n_concepts, mm_edges, n_communities, covered_kas,
    coverage_fraction, redundancy_count, ...}}``. The ``f=0`` row reproduces the
    full pipeline.
    """
    if fractions is None:
        fractions = [0.0, 0.1, 0.2, 0.3]

    modules = storage.get_all_modules()
    all_concepts = storage.get_all_concepts()
    all_alignments = storage.get_all_alignments()
    if not all_concepts or not modules:
        logger.warning("No concepts/modules — run the pipeline first.")
        return {}

    # Ascending by confidence: index 0 is the lowest-confidence concept.
    ordered = sorted(all_concepts, key=lambda c: c.confidence)
    n = len(ordered)

    results: dict[float, dict] = {}
    for f in fractions:
        n_drop = int(round(f * n))
        retained = ordered[n_drop:]
        retained_ids = {c.id for c in retained}
        alns = [a for a in all_alignments if a.concept_id in retained_ids]

        G = _module_similarity_graph(modules, retained)
        communities = detect_communities(G)
        n_comm = len(set(communities.values())) if communities else 0

        ka_coverage = compute_ka_coverage_full(retained, alns, ka_data, modules)
        report = generate_coverage_report(ka_coverage, ka_data, retained)

        results[f] = {
            "fraction_removed": round(f, 3),
            "n_dropped": n_drop,
            "n_concepts": len(retained),
            "mm_edges": G.number_of_edges(),
            "n_communities": n_comm,
            "covered_kas": report["covered_kas"],
            "total_kas": report["total_kas"],
            "coverage_fraction": report["coverage_fraction"],
            "redundancy_count": report["redundancy_count"],
        }
        logger.info(
            f"  remove {int(f * 100):>2d}%: concepts={len(retained)}, "
            f"mm_edges={G.number_of_edges()}, communities={n_comm}, "
            f"covered_KAs={report['covered_kas']}/{report['total_kas']}, "
            f"redundancies={report['redundancy_count']}"
        )

    return results
