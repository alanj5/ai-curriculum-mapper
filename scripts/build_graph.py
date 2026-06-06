#!/usr/bin/env python3
"""Build and cache the three NetworkX curriculum graphs.

Graph 1 — Bipartite module-concept graph
Graph 2 — Module-module similarity + prerequisite graph
Graph 3 — Concept-ACM hierarchy graph

Runs community detection and centrality analysis, then exports
Cytoscape.js JSON for front-end visualisation.

Usage:
    python scripts/build_graph.py [--verbose]

Prerequisites:
    python scripts/run_nlp_pipeline.py --week2
    python scripts/run_alignment.py
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from curriculum_mapper.config import GRAPH_STATS_PATH, PROCESSED_DIR, STANDARDS_DIR
from curriculum_mapper.graph.analytics import (
    compute_centrality,
    compute_ka_coverage_full,
    detect_communities,
    to_cytoscape_json,
)
from curriculum_mapper.graph.builder import (
    build_bipartite_graph,
    build_concept_acm_graph,
    build_concept_prerequisite_graph,
    build_module_module_graph,
)
from curriculum_mapper.graph.concept_prerequisite import infer_concept_prerequisites
from curriculum_mapper.graph.gap_detector import generate_coverage_report
from curriculum_mapper.graph.prerequisite import infer_prerequisites
from curriculum_mapper.ingestion.storage import StorageManager
from curriculum_mapper.nlp.embeddings import EmbeddingManager

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s: %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)


def main() -> None:
    parser = argparse.ArgumentParser(description="Build curriculum knowledge graphs")
    parser.add_argument("--verbose", action="store_true")
    args = parser.parse_args()

    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)

    storage = StorageManager()
    modules = storage.get_all_modules()
    concepts = storage.get_all_concepts()
    alignments = storage.get_all_alignments()

    if not modules:
        logger.error("No modules in DB — run ingest_modules.py first.")
        sys.exit(1)
    if not concepts:
        logger.error("No concepts in DB — run run_nlp_pipeline.py --week2 first.")
        sys.exit(1)

    logger.info(f"Building graphs: {len(modules)} modules, {len(concepts)} concepts, "
                f"{len(alignments)} alignments")

    # Load KA data
    ka_path = STANDARDS_DIR / "cs2023_ka.json"
    with open(ka_path) as f:
        ka_data = json.load(f)

    # ── Graph 1: Bipartite ─────────────────────────────────────────────────────
    logger.info("Building bipartite module-concept graph…")
    G_bip = build_bipartite_graph(modules, concepts)
    logger.info(f"  Bipartite: {G_bip.number_of_nodes()} nodes, {G_bip.number_of_edges()} edges")

    # ── Graph 2: Module-Module ─────────────────────────────────────────────────
    logger.info("Building module-module similarity graph…")
    G_mm = build_module_module_graph(modules, concepts)
    logger.info(f"  Module-module: {G_mm.number_of_nodes()} nodes, {G_mm.number_of_edges()} edges")

    # ── Graph 3: Concept-ACM ───────────────────────────────────────────────────
    logger.info("Building concept-ACM hierarchy graph…")
    G_acm = build_concept_acm_graph(concepts, alignments, ka_data)
    logger.info(f"  Concept-ACM: {G_acm.number_of_nodes()} nodes, {G_acm.number_of_edges()} edges")

    # ── Graph 4: Directed concept-prerequisite graph (DAG) ─────────────────────
    logger.info("Inferring directed concept→concept prerequisites…")
    best_alignments = storage.get_best_alignments_per_concept()
    cprereq_edges = infer_concept_prerequisites(
        concepts, modules, best_alignments, EmbeddingManager()
    )
    storage.clear_concept_prerequisites()
    for edge in cprereq_edges:
        storage.insert_concept_prerequisite(edge)
    G_cp = build_concept_prerequisite_graph(cprereq_edges, concepts, modules)
    import networkx as _nx
    cp_acyclic = _nx.is_directed_acyclic_graph(G_cp) if G_cp.number_of_edges() else True
    cp_depth = len(_nx.dag_longest_path(G_cp)) if (cp_acyclic and G_cp.number_of_edges()) else 0
    logger.info(
        f"  Concept-prerequisites: {G_cp.number_of_nodes()} nodes, "
        f"{G_cp.number_of_edges()} edges, acyclic={cp_acyclic}, longest chain={cp_depth}"
    )

    # ── Analytics on module-module graph ─────────────────────────────────────
    logger.info("Computing centrality measures…")
    centrality = compute_centrality(G_mm)

    logger.info("Detecting communities (Louvain)…")
    communities = detect_communities(G_mm)
    n_communities = len(set(communities.values()))
    logger.info(f"  {n_communities} communities detected.")

    # ── KA Coverage ───────────────────────────────────────────────────────────
    logger.info("Computing KA coverage…")
    ka_coverage = compute_ka_coverage_full(concepts, alignments, ka_data, modules)

    # ── Gap detection ─────────────────────────────────────────────────────────
    logger.info("Detecting curriculum gaps and redundancies…")
    coverage_report = generate_coverage_report(ka_coverage, ka_data, concepts)
    logger.info(
        f"  Coverage: {coverage_report['covered_kas']}/{coverage_report['total_kas']} KAs "
        f"({coverage_report['coverage_fraction']:.1%}), "
        f"{coverage_report['gap_count']} gaps "
        f"({len(coverage_report['critical_gaps'])} critical)"
    )

    # ── Prerequisite inference ────────────────────────────────────────────────
    logger.info("Inferring implicit prerequisites…")
    inferred = infer_prerequisites(modules, concepts)
    logger.info(f"  {len(inferred)} implicit prerequisite edges inferred.")

    # ── Cytoscape export ──────────────────────────────────────────────────────
    logger.info("Exporting Cytoscape.js JSON…")
    cyto = to_cytoscape_json(G_mm, centrality, communities)
    cyto_path = PROCESSED_DIR / "graph_cytoscape.json"
    with open(cyto_path, "w") as f:
        json.dump(cyto, f, indent=2)
    logger.info(f"  Saved to {cyto_path}")

    # ── Full analytics summary ─────────────────────────────────────────────────
    # Top modules by degree centrality
    top_central = sorted(
        centrality.items(), key=lambda x: -x[1].get("degree", 0)
    )[:5]

    graph_stats = {
        "bipartite": {
            "nodes": G_bip.number_of_nodes(),
            "edges": G_bip.number_of_edges(),
        },
        "module_module": {
            "nodes": G_mm.number_of_nodes(),
            "edges": G_mm.number_of_edges(),
            "n_communities": n_communities,
            "top_central_modules": [
                {"module": m, **c} for m, c in top_central
            ],
        },
        "concept_acm": {
            "nodes": G_acm.number_of_nodes(),
            "edges": G_acm.number_of_edges(),
        },
        "concept_prerequisites": {
            "nodes": G_cp.number_of_nodes(),
            "edges": G_cp.number_of_edges(),
            "acyclic": cp_acyclic,
            "longest_chain": cp_depth,
        },
        "coverage": coverage_report,
        "inferred_prerequisites": [
            {"from": a, "to": b, "overlap": s}
            for a, b, s in inferred[:20]
        ],
        "communities": {str(k): v for k, v in communities.items()},
    }

    stats_path = GRAPH_STATS_PATH
    with open(stats_path, "w") as f:
        json.dump(graph_stats, f, indent=2)
    logger.info(f"  Graph stats saved to {stats_path}")

    # ── Console summary ───────────────────────────────────────────────────────
    logger.info("=" * 60)
    logger.info("GRAPH BUILD SUMMARY")
    logger.info("=" * 60)
    logger.info(f"  Bipartite graph:    {G_bip.number_of_nodes()} nodes, {G_bip.number_of_edges()} edges")
    logger.info(f"  Module-module:      {G_mm.number_of_nodes()} nodes, {G_mm.number_of_edges()} edges")
    logger.info(f"  Concept-ACM:        {G_acm.number_of_nodes()} nodes, {G_acm.number_of_edges()} edges")
    logger.info(f"  Communities:        {n_communities}")
    logger.info(f"  KA coverage:        {coverage_report['covered_kas']}/{coverage_report['total_kas']} ({coverage_report['coverage_fraction']:.1%})")
    logger.info(f"  Critical gaps:      {len(coverage_report['critical_gaps'])}")
    logger.info(f"  Inferred prereqs:   {len(inferred)}")
    logger.info("  Top central modules:")
    for m, c in top_central:
        logger.info(f"    {m}: degree={c.get('degree', 0):.4f} betw={c.get('betweenness', 0):.4f}")


if __name__ == "__main__":
    main()
