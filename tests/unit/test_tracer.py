"""Tests for prerequisite-chain tracing."""
from __future__ import annotations

import networkx as nx

from curriculum_mapper.graph.tracer import trace_concept, trace_module
from curriculum_mapper.ingestion.schema import ModuleDescriptor


def _m(code, prereqs, level=1):
    return ModuleDescriptor(code=code, title=code, level=level, credits=8,
                            prerequisites=prereqs, description="x", ilos=[], topics=[],
                            source="imperial", source_file=f"{code}.json")


def test_module_chain_upstream_downstream_and_depth():
    mods = [_m("M1", []), _m("M2", ["M1"]), _m("M3", ["M2"])]
    t3 = trace_module(mods, "M3")
    assert set(t3["upstream"]) == {"M1", "M2"} and t3["downstream"] == []
    assert t3["chain_depth"] == 2
    t1 = trace_module(mods, "M1")
    assert set(t1["downstream"]) == {"M2", "M3"} and t1["upstream"] == []


def test_module_missing_returns_empty():
    assert trace_module([_m("M1", [])], "NOPE")["upstream"] == []


def test_concept_trace_over_digraph():
    G = nx.DiGraph([("a", "b"), ("b", "c")])
    t = trace_concept(G, "c")
    assert set(t["upstream"]) == {"a", "b"} and t["chain_depth"] == 2
    assert trace_concept(None, "c")["upstream"] == []
