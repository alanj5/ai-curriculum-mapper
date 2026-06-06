"""Tests for DAG-safe concept→concept prerequisite inference."""

from __future__ import annotations

from unittest.mock import MagicMock

import networkx as nx
import numpy as np

from curriculum_mapper.graph.builder import build_concept_prerequisite_graph
from curriculum_mapper.graph.concept_prerequisite import infer_concept_prerequisites
from curriculum_mapper.ingestion.schema import Concept, ModuleDescriptor


def _module(code, level):
    return ModuleDescriptor(
        code=code, title=code, level=level, credits=8, prerequisites=[],
        description="x", ilos=[], topics=[], source="imperial", source_file=f"{code}.json",
    )


def _concept(cid, term, modules, conf=0.9):
    return Concept(id=cid, term=term, confidence=conf, extractors=["tfidf"], module_codes=modules)


def _em_with(groups):
    """Mock EmbeddingManager: terms in the same group get identical unit vectors."""
    term_vec = {}
    for i, group in enumerate(groups):
        v = np.zeros(len(groups), dtype=np.float32)
        v[i] = 1.0
        for t in group:
            term_vec[t] = v
    em = MagicMock()
    em.encode.side_effect = lambda terms, **k: np.stack([term_vec[t] for t in terms])
    return em


def test_edges_follow_strict_level_order_and_are_acyclic():
    modules = [_module("M1", 1), _module("M2", 2), _module("M3", 3), _module("M4", 1)]
    concepts = [
        _concept("low", "low", ["M1"]),
        _concept("mid", "mid", ["M2"]),
        _concept("high", "high", ["M3"]),
        _concept("unrel", "unrel", ["M4"]),
    ]
    # low/mid/high are mutually similar; unrel is orthogonal.
    em = _em_with([["low", "mid", "high"], ["unrel"]])
    edges = infer_concept_prerequisites(concepts, modules, {}, em)

    pairs = {(e.from_concept_id, e.to_concept_id) for e in edges}
    # strictly increasing level, related → expected edges
    assert ("low", "mid") in pairs
    assert ("low", "high") in pairs
    assert ("mid", "high") in pairs
    # no reverse / equal-level / unrelated edges
    assert ("mid", "low") not in pairs
    assert all("unrel" not in (f, t) for f, t in pairs)
    # acyclic
    G = nx.DiGraph(list(pairs))
    assert nx.is_directed_acyclic_graph(G)


def test_low_confidence_concepts_excluded():
    modules = [_module("M1", 1), _module("M2", 2)]
    concepts = [
        _concept("low", "low", ["M1"], conf=0.1),   # below min_confidence
        _concept("mid", "mid", ["M2"], conf=0.9),
    ]
    em = _em_with([["low", "mid"]])
    edges = infer_concept_prerequisites(concepts, modules, {}, em)
    assert edges == []


def test_builder_produces_acyclic_digraph_with_levels():
    modules = [_module("M1", 1), _module("M2", 2)]
    concepts = [_concept("low", "low", ["M1"]), _concept("mid", "mid", ["M2"])]
    em = _em_with([["low", "mid"]])
    edges = infer_concept_prerequisites(concepts, modules, {}, em)
    G = build_concept_prerequisite_graph(edges, concepts, modules, save=False)
    assert isinstance(G, nx.DiGraph)
    assert nx.is_directed_acyclic_graph(G)
    assert G.nodes["low"]["level"] == 1 and G.nodes["mid"]["level"] == 2
