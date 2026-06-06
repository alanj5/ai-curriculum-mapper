"""Unit tests for graph-structure validation (synthetic — no models needed)."""

from __future__ import annotations

from types import SimpleNamespace

import networkx as nx

from curriculum_mapper.evaluation.graph_validation import (
    _build_mm_graph,
    check_prerequisite_dag,
    edge_threshold_sweep,
    validate_communities_vs_level,
)


def _mod(code, level, prereqs=None):
    return SimpleNamespace(code=code, level=level, prerequisites=prereqs or [], title=code, credits=8)


def _concept(cid, modules):
    return SimpleNamespace(id=cid, module_codes=list(modules), confidence=1.0)


class TestPrerequisiteDag:
    def test_acyclic_prerequisites(self):
        G = nx.Graph()
        G.add_edge("A", "B", type="prerequisite")
        G.add_edge("B", "C", type="prerequisite")
        G.add_edge("A", "C", type="similarity")  # ignored
        out = check_prerequisite_dag(G)
        assert out["is_acyclic"] is True
        assert out["n_prerequisite_edges"] == 2
        assert out["cycles"] == []

    def test_cycle_detected(self):
        DG = nx.DiGraph()  # build a graph object that yields a directed cycle
        G = nx.MultiDiGraph()
        for u, v in [("A", "B"), ("B", "C"), ("C", "A")]:
            G.add_edge(u, v, type="prerequisite")
        out = check_prerequisite_dag(G)
        assert out["is_acyclic"] is False
        assert out["cycles"]
        assert DG.number_of_edges() == 0  # sanity


class TestCommunityLevelValidation:
    def test_perfect_level_alignment(self):
        # communities exactly equal levels → NMI = ARI = 1
        modules = [_mod("A", 1), _mod("B", 1), _mod("C", 2), _mod("D", 2)]
        communities = {"A": 0, "B": 0, "C": 1, "D": 1}
        out = validate_communities_vs_level(modules, communities)
        assert out["nmi_community_vs_level"] == 1.0
        assert out["ari_community_vs_level"] == 1.0
        assert out["n_communities"] == 2

    def test_per_community_distribution(self):
        modules = [_mod("A", 1), _mod("B", 2), _mod("C", 3)]
        communities = {"A": 0, "B": 0, "C": 0}
        out = validate_communities_vs_level(modules, communities)
        assert out["per_community_level_distribution"][0] == {1: 1, 2: 1, 3: 1}


class TestEdgeThresholdSweep:
    def test_higher_threshold_means_fewer_edges(self):
        modules = [_mod("A", 1), _mod("B", 1), _mod("C", 2)]
        # A&B share 3 concepts; A&C share 1
        concepts = [
            _concept("c1", ["A", "B"]),
            _concept("c2", ["A", "B"]),
            _concept("c3", ["A", "B"]),
            _concept("c4", ["A", "C"]),
        ]
        sweep = edge_threshold_sweep(modules, concepts, thresholds=[1, 2, 3])
        assert sweep[1]["n_edges"] >= sweep[2]["n_edges"] >= sweep[3]["n_edges"]
        # at threshold 3 only the A–B edge (3 shared) survives
        assert sweep[3]["n_similarity_edges"] == 1

    def test_build_reproduces_prerequisite_edges(self):
        modules = [_mod("A", 1), _mod("B", 2, prereqs=["A"])]
        G = _build_mm_graph(modules, [], min_shared=2)
        assert G.has_edge("A", "B")
        assert G["A"]["B"]["type"] == "prerequisite"


class TestCompareProgrammes:
    def test_splits_cohorts_by_source(self):
        from unittest.mock import MagicMock

        from curriculum_mapper.evaluation.graph_validation import compare_programmes

        mods = [_mod("IC1", 1), _mod("MIT1", 2)]
        mods[0].source, mods[1].source = "imperial", "mit_ocw"
        concepts = [_concept("c1", ["IC1"]), _concept("c2", ["MIT1"])]
        aligns = [
            SimpleNamespace(concept_id="c1", rank=1, ka_code="AL"),
            SimpleNamespace(concept_id="c2", rank=1, ka_code="OS"),
        ]
        s = MagicMock()
        s.get_all_modules.return_value = mods
        s.get_all_concepts.return_value = concepts
        s.get_all_alignments.return_value = aligns
        out = compare_programmes(s)
        assert set(out) == {"imperial", "mit_ocw"}
        assert out["imperial"]["n_modules"] == 1 and out["imperial"]["n_concepts"] == 1
        assert out["imperial"]["kas_covered"] == 1
        assert out["mit_ocw"]["kas_covered"] == 1
