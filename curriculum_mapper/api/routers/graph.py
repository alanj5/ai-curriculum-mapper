"""Graph router — /api/v1/graph"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query

from curriculum_mapper.api.dependencies import (
    get_graph_bipartite,
    get_graph_concept_acm,
    get_graph_module_module,
)
from curriculum_mapper.graph.analytics import (
    compute_centrality,
    detect_communities,
    to_cytoscape_json,
)

router = APIRouter()


def _graph_to_cytoscape(G, centrality=None, communities=None) -> dict:
    """Convert NetworkX graph to Cytoscape.js JSON."""
    if G is None:
        return {"nodes": [], "edges": []}
    return to_cytoscape_json(G, centrality, communities)


@router.get("/module-module")
def get_module_module_graph(
    include_centrality: bool = Query(True),
    include_communities: bool = Query(True),
) -> dict:
    """Module-module similarity and prerequisite graph as Cytoscape.js JSON."""
    G = get_graph_module_module()
    if G is None:
        raise HTTPException(status_code=503, detail="Graph not built — run build_graph.py first")

    centrality = compute_centrality(G) if include_centrality else None
    communities = detect_communities(G) if include_communities else None
    return _graph_to_cytoscape(G, centrality, communities)


@router.get("/module-concept")
def get_bipartite_graph(
    module: str | None = Query(None, description="Filter to subgraph for one module"),
) -> dict:
    """Bipartite module-concept graph (optionally filtered to one module)."""
    G = get_graph_bipartite()
    if G is None:
        raise HTTPException(status_code=503, detail="Graph not built — run build_graph.py first")

    if module:
        module_upper = module.upper()
        if module_upper not in G:
            raise HTTPException(status_code=404, detail=f"Module '{module}' not in graph")
        # Include the module node and all directly connected concept nodes
        neighbors = list(G.neighbors(module_upper))
        subgraph_nodes = [module_upper] + neighbors
        G = G.subgraph(subgraph_nodes)

    return _graph_to_cytoscape(G)


@router.get("/concept-acm")
def get_concept_acm_graph() -> dict:
    """Concept → KA topic → KA code hierarchy graph."""
    G = get_graph_concept_acm()
    if G is None:
        raise HTTPException(status_code=503, detail="Graph not built — run build_graph.py first")
    return _graph_to_cytoscape(G)


@router.get("/communities")
def get_communities() -> dict:
    """Louvain community assignment per module."""
    G = get_graph_module_module()
    if G is None:
        raise HTTPException(status_code=503, detail="Graph not built — run build_graph.py first")
    communities = detect_communities(G)
    return {"communities": communities}


@router.get("/centrality")
def get_centrality() -> dict:
    """Degree, betweenness, and eigenvector centrality per module."""
    G = get_graph_module_module()
    if G is None:
        raise HTTPException(status_code=503, detail="Graph not built — run build_graph.py first")
    centrality = compute_centrality(G)
    return {"centrality": centrality}
