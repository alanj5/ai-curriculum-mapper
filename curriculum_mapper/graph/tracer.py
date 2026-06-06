"""Prerequisite-chain tracing.

Delivers the interim's §2.7.2 interaction — "select a node then 'find all
prerequisite chains' stemming from that course (following edge predecessors)" —
and the §2.6 scaffolding-depth metric (longest path through the prerequisite
relation), for both modules and concepts.

Module prerequisites are read directly from each module's ``prerequisites`` list
(which carries unambiguous direction prereq→module); concept prerequisites use
the directed concept-prerequisite DAG (``graph/concept_prerequisite.py``).
"""

from __future__ import annotations

import networkx as nx


def _module_prereq_digraph(modules: list) -> nx.DiGraph:
    """Directed graph prereq→module from each module's prerequisite list."""
    codes = {m.code for m in modules}
    DG = nx.DiGraph()
    for m in modules:
        DG.add_node(m.code, title=getattr(m, "title", m.code), level=getattr(m, "level", None))
        for p in m.prerequisites:
            if p in codes and p != m.code:
                DG.add_edge(p, m.code)  # p is a prerequisite of m
    return DG


def _trace(DG: nx.DiGraph, node: str) -> dict:
    """Transitive upstream (ancestors) + downstream (descendants) of ``node``."""
    if node not in DG:
        return {"center": node, "upstream": [], "downstream": [], "chain_depth": 0, "edges": []}
    upstream = nx.ancestors(DG, node)
    downstream = nx.descendants(DG, node)
    sub = DG.subgraph(upstream | downstream | {node})
    # scaffolding depth = longest prerequisite path ending at this node
    up_sub = DG.subgraph(upstream | {node})
    depth = nx.dag_longest_path_length(up_sub) if up_sub.number_of_edges() else 0
    return {
        "center": node,
        "upstream": sorted(upstream),
        "downstream": sorted(downstream),
        "chain_depth": depth,
        "edges": [[u, v] for u, v in sub.edges()],
    }


def trace_module(modules: list, code: str) -> dict:
    """Full prerequisite chain (upstream) and dependents (downstream) for a module."""
    return _trace(_module_prereq_digraph(modules), code)


def trace_concept(G: nx.DiGraph | None, concept_id: str) -> dict:
    """Full prerequisite chain (upstream) and dependents (downstream) for a concept."""
    if G is None:
        return {"center": concept_id, "upstream": [], "downstream": [], "chain_depth": 0, "edges": []}
    return _trace(G, concept_id)
