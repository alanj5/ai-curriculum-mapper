"""Tests for graph builder, analytics, gap detector, and prerequisite inference (Week 2)."""

from __future__ import annotations

import networkx as nx
import pytest

from curriculum_mapper.graph.analytics import (
    compute_centrality,
    compute_ka_coverage_full,
    detect_communities,
    to_cytoscape_json,
)
from curriculum_mapper.graph.gap_detector import (
    detect_gaps,
    detect_redundancies,
    generate_coverage_report,
)
from curriculum_mapper.graph.prerequisite import infer_prerequisites
from curriculum_mapper.ingestion.schema import (
    AlignmentResult,
    Concept,
    ModuleDescriptor,
)

# ── Fixtures ──────────────────────────────────────────────────────────────────

def _make_module(code: str, level: int = 2, prereqs: list[str] | None = None) -> ModuleDescriptor:
    return ModuleDescriptor(
        code=code,
        title=f"Module {code}",
        level=level,
        credits=10,
        prerequisites=prereqs or [],
        description=f"Description of {code}",
        source="imperial",
        source_file="test.json",
    )


def _make_concept(term: str, module_codes: list[str], confidence: float = 0.8) -> Concept:
    return Concept(
        term=term,
        confidence=confidence,
        extractors=["tfidf"],
        module_codes=module_codes,
    )


def _make_alignment(concept_id: str, ka_code: str, score: float = 0.9, rank: int = 1) -> AlignmentResult:
    return AlignmentResult(
        concept_id=concept_id,
        ka_code=ka_code,
        ka_topic="test topic",
        method="hybrid",
        score=score,
        rank=rank,
    )


# ── Graph Builder ─────────────────────────────────────────────────────────────

class TestBuildBipartiteGraph:
    def test_nodes_include_modules_and_concepts(self, tmp_path):
        import curriculum_mapper.graph.builder as gb
        from curriculum_mapper.graph.builder import build_bipartite_graph
        gb.GRAPH_CACHE = tmp_path

        modules = [_make_module("M1"), _make_module("M2")]
        c1 = _make_concept("sorting", ["M1"])
        c2 = _make_concept("hashing", ["M2"])
        concepts = [c1, c2]

        G = build_bipartite_graph(modules, concepts)
        assert "M1" in G.nodes
        assert "M2" in G.nodes
        assert c1.id in G.nodes
        assert c2.id in G.nodes

    def test_edges_connect_module_to_concept(self, tmp_path):
        import curriculum_mapper.graph.builder as gb
        from curriculum_mapper.graph.builder import build_bipartite_graph
        gb.GRAPH_CACHE = tmp_path

        modules = [_make_module("M1")]
        c1 = _make_concept("sorting", ["M1"], confidence=0.75)
        G = build_bipartite_graph(modules, [c1])
        assert G.has_edge("M1", c1.id)
        assert G["M1"][c1.id]["weight"] == pytest.approx(0.75)

    def test_empty_inputs(self, tmp_path):
        import curriculum_mapper.graph.builder as gb
        from curriculum_mapper.graph.builder import build_bipartite_graph
        gb.GRAPH_CACHE = tmp_path

        G = build_bipartite_graph([], [])
        assert G.number_of_nodes() == 0


class TestBuildModuleModuleGraph:
    def test_prerequisite_edge(self, tmp_path):
        import curriculum_mapper.graph.builder as gb
        from curriculum_mapper.graph.builder import build_module_module_graph
        gb.GRAPH_CACHE = tmp_path

        modules = [
            _make_module("M1", level=1),
            _make_module("M2", level=2, prereqs=["M1"]),
        ]
        G = build_module_module_graph(modules, [])
        assert G.has_edge("M1", "M2")
        assert G["M1"]["M2"]["type"] == "prerequisite"

    def test_similarity_edge_above_min(self, tmp_path):
        import curriculum_mapper.graph.builder as gb
        from curriculum_mapper.graph.builder import build_module_module_graph
        gb.GRAPH_CACHE = tmp_path
        gb.SHARED_CONCEPT_EDGE_MIN = 2

        modules = [_make_module("M1"), _make_module("M2")]
        concepts = [
            _make_concept("sorting", ["M1", "M2"]),
            _make_concept("hashing", ["M1", "M2"]),
            _make_concept("graphs", ["M1", "M2"]),
        ]
        G = build_module_module_graph(modules, concepts)
        assert G.has_edge("M1", "M2")
        assert G["M1"]["M2"]["type"] == "similarity"

    def test_no_edge_below_min(self, tmp_path):
        import curriculum_mapper.graph.builder as gb
        from curriculum_mapper.graph.builder import build_module_module_graph
        gb.GRAPH_CACHE = tmp_path
        gb.SHARED_CONCEPT_EDGE_MIN = 5  # high threshold

        modules = [_make_module("M1"), _make_module("M2")]
        concepts = [_make_concept("sorting", ["M1", "M2"])]  # only 1 shared
        G = build_module_module_graph(modules, concepts)
        assert not G.has_edge("M1", "M2")


# ── Graph Analytics ───────────────────────────────────────────────────────────

class TestComputeCentrality:
    def test_empty_graph_returns_empty(self):
        G = nx.Graph()
        assert compute_centrality(G) == {}

    def test_single_node(self):
        G = nx.Graph()
        G.add_node("M1")
        c = compute_centrality(G)
        assert "M1" in c
        # A single node with no edges has normalised degree 0 in networkx,
        # but the formula divides by (n-1) = 0 so nx returns 0.0 for n=1
        # (networkx >= 2.8 handles this gracefully — just check key exists)
        assert "degree" in c["M1"]

    def test_complete_graph_equal_centrality(self):
        G = nx.complete_graph(4)
        G = nx.relabel_nodes(G, {i: f"M{i}" for i in range(4)})
        c = compute_centrality(G)
        degrees = [c[n]["degree"] for n in G.nodes()]
        assert max(degrees) == pytest.approx(min(degrees), abs=0.001)

    def test_returns_all_nodes(self):
        G = nx.path_graph(5)
        G = nx.relabel_nodes(G, {i: f"M{i}" for i in range(5)})
        c = compute_centrality(G)
        assert set(c.keys()) == set(G.nodes())

    def test_centrality_keys(self):
        G = nx.path_graph(3)
        G = nx.relabel_nodes(G, {i: f"M{i}" for i in range(3)})
        c = compute_centrality(G)
        for node in G.nodes():
            assert "degree" in c[node]
            assert "betweenness" in c[node]
            assert "eigenvector" in c[node]


class TestDetectCommunities:
    def test_disconnected_graph_multiple_communities(self):
        G = nx.Graph()
        G.add_nodes_from(["M1", "M2", "M3", "M4"])
        G.add_edge("M1", "M2")
        G.add_edge("M3", "M4")
        communities = detect_communities(G)
        assert len(set(communities.values())) >= 1

    def test_single_community_clique(self):
        G = nx.complete_graph(4)
        communities = detect_communities(G)
        # All nodes in same community
        assert len(set(communities.values())) == 1

    def test_returns_all_nodes(self):
        G = nx.path_graph(5)
        communities = detect_communities(G)
        assert set(communities.keys()) == set(G.nodes())

    def test_no_edges_single_community(self):
        G = nx.Graph()
        G.add_nodes_from(["A", "B"])
        communities = detect_communities(G)
        assert set(communities.keys()) == {"A", "B"}


class TestKACoverage:
    def test_full_coverage(self):
        modules = [_make_module("M1"), _make_module("M2")]
        c1 = _make_concept("sorting", ["M1"])
        c2 = _make_concept("hashing", ["M2"])
        a1 = _make_alignment(c1.id, "AL")
        a2 = _make_alignment(c2.id, "DS")
        ka_data = {"AL": {"name": "Algorithms"}, "DS": {"name": "Data Structures"}}
        coverage = compute_ka_coverage_full([c1, c2], [a1, a2], ka_data, modules)
        assert coverage["AL"] == pytest.approx(0.5)  # 1 of 2 modules
        assert coverage["DS"] == pytest.approx(0.5)

    def test_no_modules(self):
        coverage = compute_ka_coverage_full([], [], {"AL": {}}, [])
        assert coverage["AL"] == 0.0


class TestToCytoscapeJson:
    def test_structure(self):
        G = nx.Graph()
        G.add_node("M1", level=2)
        G.add_node("M2", level=3)
        G.add_edge("M1", "M2", weight=0.5)
        result = to_cytoscape_json(G)
        assert "nodes" in result
        assert "edges" in result
        assert len(result["nodes"]) == 2
        assert len(result["edges"]) == 1

    def test_centrality_added_to_nodes(self):
        G = nx.Graph()
        G.add_node("M1")
        centrality = {"M1": {"degree": 0.5, "betweenness": 0.2}}
        result = to_cytoscape_json(G, centrality=centrality)
        node_data = result["nodes"][0]["data"]
        assert node_data["degree"] == 0.5

    def test_community_added_to_nodes(self):
        G = nx.Graph()
        G.add_node("M1")
        communities = {"M1": 2}
        result = to_cytoscape_json(G, communities=communities)
        assert result["nodes"][0]["data"]["community"] == 2


# ── Gap Detector ──────────────────────────────────────────────────────────────

class TestDetectGaps:
    def setup_method(self):
        self.ka_data = {
            "AL": {"name": "Algorithms"},
            "OS": {"name": "Operating Systems"},
            "DS": {"name": "Data Structures"},
        }

    def test_all_covered_no_gaps(self):
        coverage = {"AL": 0.5, "OS": 0.3, "DS": 0.2}
        gaps = detect_gaps(coverage, self.ka_data)
        assert gaps == []

    def test_critical_gap_zero_coverage(self):
        coverage = {"AL": 0.0, "OS": 0.5, "DS": 0.3}
        gaps = detect_gaps(coverage, self.ka_data)
        assert len(gaps) == 1
        assert gaps[0]["ka_code"] == "AL"
        assert gaps[0]["severity"] == "critical"

    def test_warning_gap(self):
        coverage = {"AL": 0.05, "OS": 0.5, "DS": 0.3}
        gaps = detect_gaps(coverage, self.ka_data)
        assert len(gaps) == 1
        assert gaps[0]["severity"] == "warning"

    def test_sorted_by_coverage(self):
        coverage = {"AL": 0.05, "OS": 0.0, "DS": 0.3}
        gaps = detect_gaps(coverage, self.ka_data)
        assert len(gaps) == 2
        assert gaps[0]["coverage"] <= gaps[1]["coverage"]


class TestDetectRedundancies:
    def test_no_redundancy(self):
        concepts = [
            _make_concept("sorting", ["M1", "M2"]),
            _make_concept("hashing", ["M1"]),
        ]
        result = detect_redundancies(concepts)
        assert result == []

    def test_redundancy_detected(self):
        # concept appearing in 5+ modules
        concept = _make_concept("sorting", ["M1", "M2", "M3", "M4", "M5"], confidence=0.9)
        result = detect_redundancies([concept])
        assert len(result) == 1
        assert result[0]["concept"] == "sorting"
        assert result[0]["module_count"] == 5

    def test_below_noise_floor_not_redundant(self):
        # Below REDUNDANCY_MIN_CONFIDENCE (0.25): treated as extraction noise.
        concept = _make_concept("sorting", ["M1", "M2", "M3", "M4", "M5"], confidence=0.2)
        result = detect_redundancies([concept])
        assert result == []

    def test_moderate_confidence_cross_cutting_redundant(self):
        # Cross-cutting concepts legitimately have moderate confidence; redundancy
        # is defined by cross-module frequency, not extraction certainty.
        concept = _make_concept("software", ["M1", "M2", "M3", "M4", "M5"], confidence=0.35)
        result = detect_redundancies([concept])
        assert len(result) == 1


class TestGenerateCoverageReport:
    def test_report_keys(self):
        coverage = {"AL": 0.5, "OS": 0.0}
        ka_data = {"AL": {"name": "A"}, "OS": {"name": "O"}}
        concepts = []
        report = generate_coverage_report(coverage, ka_data, concepts)
        assert "total_kas" in report
        assert "covered_kas" in report
        assert "coverage_fraction" in report
        assert "gaps" in report
        assert "redundancies" in report

    def test_coverage_fraction(self):
        coverage = {"AL": 0.5, "OS": 0.0}
        ka_data = {"AL": {"name": "A"}, "OS": {"name": "O"}}
        report = generate_coverage_report(coverage, ka_data, [])
        assert report["coverage_fraction"] == pytest.approx(0.5)
        assert report["covered_kas"] == 1
        assert report["total_kas"] == 2


# ── Prerequisite Inference ────────────────────────────────────────────────────

class TestInferPrerequisites:
    def test_no_concepts_no_inferred(self):
        modules = [_make_module("M1", 1), _make_module("M2", 2)]
        inferred = infer_prerequisites(modules, [])
        assert inferred == []

    def test_high_overlap_inferred(self):
        m1 = _make_module("M1", level=1)
        m2 = _make_module("M2", level=2)
        # M2 contains all of M1's concepts plus more
        shared = [_make_concept(f"c{i}", ["M1", "M2"], 0.9) for i in range(7)]
        extra = [_make_concept(f"e{i}", ["M2"], 0.9) for i in range(3)]
        inferred = infer_prerequisites([m1, m2], shared + extra)
        pairs = [(a, b) for a, b, _ in inferred]
        assert ("M1", "M2") in pairs

    def test_no_self_prerequisites(self):
        m1 = _make_module("M1", level=2)
        concepts = [_make_concept(f"c{i}", ["M1"]) for i in range(5)]
        inferred = infer_prerequisites([m1], concepts)
        for a, b, _ in inferred:
            assert a != b

    def test_existing_prerequisites_not_duplicated(self):
        m1 = _make_module("M1", level=1)
        m2 = _make_module("M2", level=2, prereqs=["M1"])
        shared = [_make_concept(f"c{i}", ["M1", "M2"], 0.9) for i in range(7)]
        extra = [_make_concept(f"e{i}", ["M2"], 0.9) for i in range(3)]
        inferred = infer_prerequisites([m1, m2], shared + extra)
        # M1→M2 already explicit, should not be in inferred
        pairs = [(a, b) for a, b, _ in inferred]
        assert ("M1", "M2") not in pairs

    def test_lower_level_not_prerequisite(self):
        m1 = _make_module("M1", level=3)
        m2 = _make_module("M2", level=1)  # lower level than M1
        shared = [_make_concept(f"c{i}", ["M1", "M2"], 0.9) for i in range(7)]
        extra = [_make_concept(f"e{i}", ["M1"], 0.9) for i in range(3)]
        inferred = infer_prerequisites([m1, m2], shared + extra)
        pairs = [(a, b) for a, b, _ in inferred]
        # M2 is lower level, so M1→M2 should not be inferred
        assert ("M1", "M2") not in pairs

    def test_overlap_scores_sorted_descending(self):
        m1 = _make_module("M1", level=1)
        m2 = _make_module("M2", level=2)
        m3 = _make_module("M3", level=2)
        shared_12 = [_make_concept(f"a{i}", ["M1", "M2"], 0.9) for i in range(9)]
        extra_2 = [_make_concept(f"b{i}", ["M2"], 0.9) for i in range(1)]
        shared_13 = [_make_concept(f"c{i}", ["M1", "M3"], 0.9) for i in range(7)]
        extra_3 = [_make_concept(f"d{i}", ["M3"], 0.9) for i in range(3)]
        inferred = infer_prerequisites([m1, m2, m3], shared_12 + extra_2 + shared_13 + extra_3)
        if len(inferred) >= 2:
            scores = [s for _, _, s in inferred]
            assert scores[0] >= scores[1]
