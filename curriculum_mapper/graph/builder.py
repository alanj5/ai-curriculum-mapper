"""Graph builder — constructs three NetworkX graphs and caches them.

Graph 1 — Bipartite Module-Concept Graph:
  Nodes: module nodes (type=module) + concept nodes (type=concept)
  Edges: module ─── concept (weight = confidence)

Graph 2 — Module-Module Similarity Graph:
  Nodes: module codes
  Edges:
    - prerequisite (from explicit prerequisites in module data)
    - similarity (Jaccard of shared concept sets, ≥ SHARED_CONCEPT_EDGE_MIN)

Graph 3 — Concept-ACM Hierarchy:
  Nodes: concept terms → KA topic strings → KA codes
  Edges weighted by alignment score

All graphs are persisted as pickle files in data/cache/graphs/ for fast reload.
"""

from __future__ import annotations

import logging
import pickle
from pathlib import Path

import networkx as nx

from curriculum_mapper.config import (
    DB_PATH,
    GRAPH_CACHE,
    SHARED_CONCEPT_EDGE_MIN,
)
from curriculum_mapper.ingestion.schema import (
    AlignmentResult,
    Concept,
    ModuleDescriptor,
)

logger = logging.getLogger(__name__)


def _cache_path(name: str) -> Path:
    # Namespace the cache by the database stem so that running the pipeline on a
    # different database (e.g. the LLM-augmented curriculum_llm.db) does not
    # clobber the canonical graph pickles.
    cache_dir = GRAPH_CACHE / DB_PATH.stem
    cache_dir.mkdir(parents=True, exist_ok=True)
    return cache_dir / f"{name}.pkl"


def _save_graph(G: nx.Graph, name: str) -> None:
    with open(_cache_path(name), "wb") as f:
        pickle.dump(G, f)
    logger.info(f"Cached graph '{name}': {G.number_of_nodes()} nodes, {G.number_of_edges()} edges")


def load_graph(name: str) -> nx.Graph | None:
    p = _cache_path(name)
    if not p.exists():
        return None
    with open(p, "rb") as f:
        return pickle.load(f)


def build_bipartite_graph(
    modules: list[ModuleDescriptor],
    concepts: list[Concept],
) -> nx.Graph:
    """Bipartite module ↔ concept graph."""
    G = nx.Graph()
    for m in modules:
        G.add_node(m.code, bipartite=0, type="module", level=m.level, title=m.title)
    for c in concepts:
        G.add_node(c.id, bipartite=1, type="concept", term=c.term, confidence=c.confidence)
        for mc in c.module_codes:
            if mc in G:
                G.add_edge(mc, c.id, weight=c.confidence)
    _save_graph(G, "bipartite")
    return G


def build_module_module_graph(
    modules: list[ModuleDescriptor],
    concepts: list[Concept],
) -> nx.Graph:
    """Module similarity graph with prerequisite and similarity edges."""
    G = nx.Graph()
    module_set = {m.code for m in modules}

    for m in modules:
        G.add_node(m.code, type="module", level=m.level, title=m.title, credits=m.credits)

    # Prerequisite edges (directed semantics encoded in edge attribute)
    for m in modules:
        for prereq in m.prerequisites:
            if prereq in module_set and prereq != m.code:
                if not G.has_edge(prereq, m.code):
                    G.add_edge(prereq, m.code, type="prerequisite", weight=1.0)

    # Similarity edges via shared concept Jaccard
    concept_sets: dict[str, set[str]] = {
        m.code: set() for m in modules
    }
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
                    # upgrade to similarity if already has prereq edge
                    G[a][b]["similarity"] = round(jaccard, 4)
                    G[a][b]["shared_count"] = len(shared)
                else:
                    G.add_edge(
                        a, b,
                        type="similarity",
                        weight=round(jaccard, 4),
                        shared_count=len(shared),
                    )

    _save_graph(G, "module_module")
    return G


def build_concept_acm_graph(
    concepts: list[Concept],
    alignments: list[AlignmentResult],
    ka_data: dict,
) -> nx.DiGraph:
    """Concept → KA topic → KA code hierarchy graph."""
    G = nx.DiGraph()

    # Add KA nodes
    for ka_code, ka_info in ka_data.items():
        G.add_node(ka_code, type="ka", name=ka_info["name"])

    # Add concept nodes and alignment edges
    for c in concepts:
        G.add_node(c.id, type="concept", term=c.term, confidence=c.confidence)

    for a in alignments:
        if a.rank == 1:  # only best alignment per concept
            topic_node = f"{a.ka_code}::{a.ka_topic}"
            if not G.has_node(topic_node):
                G.add_node(topic_node, type="ka_topic", ka_code=a.ka_code, topic=a.ka_topic)
                G.add_edge(topic_node, a.ka_code, weight=1.0)
            G.add_edge(a.concept_id, topic_node, weight=a.score)

    _save_graph(G, "concept_acm")
    return G


def build_concept_prerequisite_graph(
    edges: list,
    concepts: list[Concept],
    modules: list[ModuleDescriptor],
    save: bool = True,
) -> nx.DiGraph:
    """Directed concept→concept prerequisite graph (DAG).

    ``edges`` is a list of ``ConceptPrerequisite``; only concepts referenced by an
    edge become nodes. Each node carries its term and *introduction level* (lowest
    teaching-module level) so the frontend can lay it out as a progression.
    """
    level_of = {m.code: m.level for m in modules}
    intro: dict[str, int] = {}
    by_id = {c.id: c for c in concepts}
    for c in concepts:
        levels = [level_of[mc] for mc in c.module_codes if mc in level_of]
        if levels:
            intro[c.id] = min(levels)

    G = nx.DiGraph()
    referenced = {e.from_concept_id for e in edges} | {e.to_concept_id for e in edges}
    for cid in referenced:
        node = by_id.get(cid)
        if node is None:
            continue
        G.add_node(
            cid, type="concept", term=node.term, label=node.term,
            confidence=node.confidence, level=intro.get(cid),
        )
    for e in edges:
        if G.has_node(e.from_concept_id) and G.has_node(e.to_concept_id):
            G.add_edge(
                e.from_concept_id, e.to_concept_id,
                type="prerequisite", weight=e.confidence, method=e.method,
            )

    if G.number_of_edges() and not nx.is_directed_acyclic_graph(G):
        logger.warning("Concept-prerequisite graph is unexpectedly cyclic!")
    if save:
        _save_graph(G, "concept_prerequisites")
    return G
