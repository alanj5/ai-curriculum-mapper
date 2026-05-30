"""Unit tests for the perturbation-robustness analysis (evaluation.robustness)."""

from __future__ import annotations

from unittest.mock import MagicMock

from curriculum_mapper.evaluation.robustness import run_perturbation_robustness
from curriculum_mapper.ingestion.schema import (
    AlignmentResult,
    Concept,
    ModuleDescriptor,
)


def _module(code: str, prereqs=None) -> ModuleDescriptor:
    return ModuleDescriptor(
        code=code, title=code, level=1, credits=8,
        prerequisites=prereqs or [], description="d", ilos=[], topics=[],
        source="institutional", source_file=f"{code}.json",
    )


def _concept(cid: str, modules: list[str], conf: float) -> Concept:
    return Concept(id=cid, term=cid, variants=[], confidence=conf,
                   extractors=["tfidf"], module_codes=modules)


def _align(cid: str, ka: str) -> AlignmentResult:
    return AlignmentResult(concept_id=cid, ka_code=ka, ka_topic=ka,
                           method="hybrid", score=0.9, rank=1)


KA_DATA = {"AL": {"name": "Algorithms", "topics": []},
           "OS": {"name": "Operating Systems", "topics": []}}


def _storage(modules, concepts, alignments):
    s = MagicMock()
    s.get_all_modules.return_value = modules
    s.get_all_concepts.return_value = concepts
    s.get_all_alignments.return_value = alignments
    return s


class TestPerturbationRobustness:
    def test_empty_when_no_concepts(self):
        s = _storage([_module("M1")], [], [])
        assert run_perturbation_robustness(s, KA_DATA) == {}

    def test_fraction_rows_and_pruning(self):
        modules = [_module("M1"), _module("M2")]
        # 10 concepts; the two shared ones (high confidence) create the M1–M2 edge.
        concepts = [_concept("shared1", ["M1", "M2"], 0.9),
                    _concept("shared2", ["M1", "M2"], 0.8)]
        concepts += [_concept(f"low{i}", ["M1"], 0.1 + i * 0.01) for i in range(8)]
        alignments = [_align(c.id, "AL") for c in concepts]
        s = _storage(modules, concepts, alignments)

        out = run_perturbation_robustness(s, KA_DATA, fractions=[0.0, 0.2, 0.5])
        assert set(out.keys()) == {0.0, 0.2, 0.5}
        # f=0 keeps everything; the two shared concepts give one similarity edge.
        assert out[0.0]["n_concepts"] == 10
        assert out[0.0]["mm_edges"] == 1
        # Removing the lowest 50% drops only low-confidence single-module concepts,
        # so the shared-concept edge (and thus connectivity) survives.
        assert out[0.5]["n_concepts"] == 5
        assert out[0.5]["mm_edges"] == 1

    def test_keys_present(self):
        modules = [_module("M1")]
        concepts = [_concept("c1", ["M1"], 0.5)]
        s = _storage(modules, concepts, [_align("c1", "AL")])
        out = run_perturbation_robustness(s, KA_DATA, fractions=[0.0])
        for key in ("n_concepts", "mm_edges", "n_communities", "covered_kas",
                    "coverage_fraction", "redundancy_count"):
            assert key in out[0.0]
