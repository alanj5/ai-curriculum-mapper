"""Graph router — /api/v1/graph"""

from __future__ import annotations

import networkx as nx
from fastapi import APIRouter, Depends, HTTPException, Query

from curriculum_mapper.api.dependencies import (
    get_graph_bipartite,
    get_graph_concept_acm,
    get_graph_concept_prerequisite,
    get_graph_module_module,
    get_storage,
)
from curriculum_mapper.graph.analytics import (
    compute_centrality,
    detect_communities,
    to_cytoscape_json,
)
from curriculum_mapper.graph.tracer import trace_concept, trace_module
from curriculum_mapper.ingestion.storage import StorageManager

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


@router.get("/concept-prerequisites")
def get_concept_prerequisite_graph() -> dict:
    """Directed concept→concept prerequisite graph (DAG) as Cytoscape.js JSON."""
    G = get_graph_concept_prerequisite()
    if G is None:
        raise HTTPException(status_code=503, detail="Graph not built — run build_graph.py first")
    return _graph_to_cytoscape(G)


@router.get("/concept-neighbourhood")
def get_concept_neighbourhood(
    concept_id: str = Query(..., description="Centre concept id"),
    depth: int = Query(2, ge=1, le=5),
) -> dict:
    """A concept's local neighbourhood of prerequisite (upstream) and subsequent
    (downstream) concepts, up to ``depth`` hops — the §3.2.4 click-to-explore view.
    Each node is tagged ``direction`` = self | prerequisite | subsequent."""
    G = get_graph_concept_prerequisite()
    if G is None:
        raise HTTPException(status_code=503, detail="Graph not built — run build_graph.py first")
    if concept_id not in G:
        # Valid concept with no inferred prerequisite edges → empty neighbourhood.
        return {"nodes": [], "edges": [], "center": concept_id}

    upstream = nx.single_source_shortest_path_length(G.reverse(copy=False), concept_id, cutoff=depth)
    downstream = nx.single_source_shortest_path_length(G, concept_id, cutoff=depth)
    H = G.subgraph(set(upstream) | set(downstream)).copy()
    for n in H.nodes():
        if n == concept_id:
            direction, dist = "self", 0
        elif n in upstream:
            direction, dist = "prerequisite", upstream[n]
        else:
            direction, dist = "subsequent", downstream[n]
        H.nodes[n]["direction"] = direction
        H.nodes[n]["dist"] = dist
    cyto = _graph_to_cytoscape(H)
    cyto["center"] = concept_id
    return cyto


@router.get("/trace/module/{code}")
def trace_module_chain(
    code: str,
    storage: StorageManager = Depends(get_storage),
) -> dict:
    """All transitive prerequisites (upstream) and dependents (downstream) of a
    module, plus the scaffolding depth — the §2.7.2 'find all prerequisite chains'."""
    return trace_module(storage.get_all_modules(), code.upper())


@router.get("/trace/concept/{concept_id}")
def trace_concept_chain(
    concept_id: str,
    storage: StorageManager = Depends(get_storage),
) -> dict:
    """All transitive prerequisite/subsequent concepts of a concept, with terms."""
    result = trace_concept(get_graph_concept_prerequisite(), concept_id)
    term = {c.id: c.term for c in storage.get_all_concepts()}
    result["terms"] = {
        cid: term.get(cid, cid)
        for cid in [result["center"], *result["upstream"], *result["downstream"]]
    }
    return result


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
