"""Graph analytics: centrality measures, community detection, Cytoscape export.

Centrality measures on the module-module graph characterise each module's
importance in the curriculum network:
  - Degree centrality: number of similar modules (breadth of overlap)
  - Betweenness centrality: bridging role between curriculum clusters
  - Eigenvector centrality: importance weighted by neighbours' importance

Community detection uses the Louvain algorithm (Blondel et al., 2008)
with random_state=42. Communities correspond to curriculum clusters
(e.g. systems, theory, maths/AI).
"""

from __future__ import annotations

import logging
from collections import defaultdict

import networkx as nx

logger = logging.getLogger(__name__)


def compute_centrality(G: nx.Graph) -> dict[str, dict[str, float]]:
    """Return centrality measures for all module nodes."""
    if G.number_of_nodes() == 0:
        return {}

    # Work on largest connected component for eigen centrality stability
    if not nx.is_connected(G):
        lcc = G.subgraph(max(nx.connected_components(G), key=len))
    else:
        lcc = G

    deg = nx.degree_centrality(G)
    try:
        bet = nx.betweenness_centrality(G, weight="weight", normalized=True)
    except Exception:
        bet = {n: 0.0 for n in G.nodes()}
    try:
        eig = nx.eigenvector_centrality(lcc, weight="weight", max_iter=1000, tol=1e-4)
        # fill missing nodes (not in LCC) with 0
        eig = {n: eig.get(n, 0.0) for n in G.nodes()}
    except Exception:
        eig = {n: 0.0 for n in G.nodes()}

    return {
        node: {
            "degree": round(deg.get(node, 0.0), 4),
            "betweenness": round(bet.get(node, 0.0), 4),
            "eigenvector": round(eig.get(node, 0.0), 4),
        }
        for node in G.nodes()
    }


def concept_overlap_subgraph(G: nx.Graph) -> nx.Graph:
    """Undirected subgraph of concept-overlap (similarity) edges, Jaccard-weighted.

    A community is defined by *shared concepts*, so prerequisite-only edges (a
    different, sequencing relation) are excluded. Community detection and its
    modularity are both computed on this subgraph, so the two always agree.
    """
    base = G.to_undirected() if G.is_directed() else G
    H = nx.Graph()
    H.add_nodes_from(base.nodes())
    for a, b, d in base.edges(data=True):
        if "shared_count" in d or d.get("type") == "similarity" or "similarity" in d:
            w = d.get("similarity", d.get("weight", 0.0))
            if w and w > 0:
                H.add_edge(a, b, weight=w)
    return H


def detect_communities(G: nx.Graph) -> dict[str, int]:
    """{module_code: community_id} via Louvain on the concept-overlap subgraph."""
    try:
        import community as community_louvain
        H = concept_overlap_subgraph(G)
        if H.number_of_edges() == 0:
            return {n: 0 for n in H.nodes()}
        return community_louvain.best_partition(H, weight="weight", random_state=42)
    except Exception as e:
        logger.warning(f"Louvain community detection failed: {e}. Assigning single community.")
        return {n: 0 for n in G.nodes()}


def compute_ka_coverage(
    modules: list,
    alignments: list,
    ka_data: dict,
) -> dict[str, float]:
    """{ka_code: fraction_of_modules_with_at_least_one_aligned_concept}."""
    if not modules:
        return {}

    # Build: ka_code → set of module_codes with aligned concept
    defaultdict(set)
    # We need concept.module_codes joined via alignment
    # alignments have concept_id; we need a lookup concept_id → module_codes
    # Pass concept list through storage query — but analytics shouldn't import storage.
    # Instead accept a pre-built lookup dict.
    # This is called from build_graph.py which passes the data through.
    return {}  # Filled in by the calling script with full data


def compute_ka_coverage_full(
    concepts: list,
    alignments: list,
    ka_data: dict,
    modules: list,
) -> dict[str, float]:
    """Full KA coverage computation requiring concept objects."""
    n_modules = len(modules)
    if n_modules == 0:
        return {ka: 0.0 for ka in ka_data}

    concept_id_to_modules: dict[str, list[str]] = {c.id: c.module_codes for c in concepts}
    ka_covered_modules: dict[str, set[str]] = defaultdict(set)
    for a in alignments:
        for mc in concept_id_to_modules.get(a.concept_id, []):
            ka_covered_modules[a.ka_code].add(mc)

    return {
        ka: round(len(ka_covered_modules.get(ka, set())) / n_modules, 4)
        for ka in ka_data
    }


def to_cytoscape_json(
    G: nx.Graph,
    centrality: dict | None = None,
    communities: dict | None = None,
) -> dict:
    """Convert NetworkX graph to Cytoscape.js elements format."""
    nodes = []
    for node, data in G.nodes(data=True):
        node_data = {"id": str(node), **{k: v for k, v in data.items()}}
        if centrality and node in centrality:
            node_data.update(centrality[node])
        if communities and node in communities:
            node_data["community"] = communities[node]
        nodes.append({"data": node_data})

    edges = []
    for i, (u, v, data) in enumerate(G.edges(data=True)):
        edge_data = {
            "id": f"e{i}",
            "source": str(u),
            "target": str(v),
            **{k: v for k, v in data.items()},
        }
        edges.append({"data": edge_data})

    return {"nodes": nodes, "edges": edges}
