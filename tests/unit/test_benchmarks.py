"""Tests for BenchmarkRunner and load_gold."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock

import numpy as np
import pytest

from curriculum_mapper.evaluation.benchmarks import BenchmarkRunner, load_gold
from curriculum_mapper.ingestion.schema import Concept

# ── Fixtures ───────────────────────────────────────────────────────────────────

GOLD_DATA = {
    "_metadata": {"annotator": "test"},
    "MOD001": {
        "module_title": "Algorithms",
        "concepts": ["sorting algorithms", "binary search", "dynamic programming"],
    },
    "MOD002": {
        "module_title": "Operating Systems",
        "concepts": ["process management", "virtual memory", "file systems"],
    },
}


@pytest.fixture
def gold_file(tmp_path: Path) -> Path:
    p = tmp_path / "gold_concepts.json"
    p.write_text(json.dumps(GOLD_DATA))
    return p


def _make_concept(term: str, module_codes: list[str], confidence: float = 0.8) -> Concept:
    return Concept(
        term=term,
        variants=[],
        confidence=confidence,
        extractors=["tfidf"],
        module_codes=module_codes,
    )


def _make_em(sim_value: float = 0.9) -> MagicMock:
    """Mock EmbeddingManager that returns deterministic embeddings."""
    em = MagicMock()
    # encode returns L2-normalised unit vectors; dot product = sim_value
    vec = np.array([1.0, 0.0, 0.0], dtype=np.float32)
    em.encode.return_value = np.stack([vec])
    return em


def _make_storage(concepts=None, alignments=None):
    storage = MagicMock()
    storage.get_all_concepts.return_value = concepts or []
    storage.get_all_alignments.return_value = alignments or []
    return storage


# ── load_gold ──────────────────────────────────────────────────────────────────

class TestLoadGold:
    def test_loads_two_modules(self, gold_file):
        gold = load_gold(gold_file)
        assert set(gold.keys()) == {"MOD001", "MOD002"}

    def test_strips_metadata_key(self, gold_file):
        gold = load_gold(gold_file)
        assert "_metadata" not in gold

    def test_returns_concept_lists(self, gold_file):
        gold = load_gold(gold_file)
        assert gold["MOD001"] == ["sorting algorithms", "binary search", "dynamic programming"]

    def test_missing_file_raises(self, tmp_path):
        with pytest.raises(FileNotFoundError):
            load_gold(tmp_path / "nonexistent.json")


# ── BenchmarkRunner constructor ────────────────────────────────────────────────

class TestBenchmarkRunnerInit:
    def test_loads_gold(self, gold_file):
        storage = _make_storage()
        em = _make_em()
        runner = BenchmarkRunner(storage, em, gold_path=gold_file)
        assert len(runner.gold) == 2

    def test_stores_storage_and_em(self, gold_file):
        storage = _make_storage()
        em = _make_em()
        runner = BenchmarkRunner(storage, em, gold_path=gold_file)
        assert runner.storage is storage
        assert runner.em is em


# ── run_extraction_benchmark ───────────────────────────────────────────────────

class TestRunExtractionBenchmark:
    def test_returns_empty_when_no_concepts(self, gold_file):
        storage = _make_storage(concepts=[])
        em = _make_em()
        runner = BenchmarkRunner(storage, em, gold_path=gold_file)
        result = runner.run_extraction_benchmark()
        assert result == {}

    def test_macro_keys_present(self, gold_file):
        concepts = [
            _make_concept("sorting algorithms", ["MOD001"], 0.9),
            _make_concept("binary search", ["MOD001"], 0.8),
            _make_concept("process management", ["MOD002"], 0.85),
        ]
        em = MagicMock()
        # Return high-similarity embeddings so predictions count as hits
        vec = np.array([1.0, 0.0], dtype=np.float32)
        em.encode.return_value = np.stack([vec, vec, vec])
        storage = _make_storage(concepts=concepts)
        runner = BenchmarkRunner(storage, em, gold_path=gold_file)
        result = runner.run_extraction_benchmark(ks=[5, 10])
        assert "macro" in result
        assert "per_module" in result
        assert "P@5" in result["macro"]
        assert "MAP" in result["macro"]

    def test_custom_ks(self, gold_file):
        concepts = [_make_concept("sorting algorithms", ["MOD001"])]
        em = MagicMock()
        vec = np.array([1.0, 0.0], dtype=np.float32)
        em.encode.return_value = np.stack([vec])
        storage = _make_storage(concepts=concepts)
        runner = BenchmarkRunner(storage, em, gold_path=gold_file)
        result = runner.run_extraction_benchmark(ks=[3])
        assert "P@3" in result["macro"]
        assert "P@5" not in result["macro"]

    def test_per_module_has_n_gold(self, gold_file):
        concepts = [_make_concept("sorting algorithms", ["MOD001"])]
        em = MagicMock()
        vec = np.array([1.0, 0.0], dtype=np.float32)
        em.encode.return_value = np.stack([vec])
        storage = _make_storage(concepts=concepts)
        runner = BenchmarkRunner(storage, em, gold_path=gold_file)
        result = runner.run_extraction_benchmark(ks=[5])
        assert result["per_module"]["MOD001"]["n_gold"] == 3

    def test_module_not_in_concepts_gets_zero_predicted(self, gold_file):
        # Only concepts for MOD002
        concepts = [_make_concept("file systems", ["MOD002"])]
        em = MagicMock()
        vec = np.array([1.0, 0.0], dtype=np.float32)
        em.encode.return_value = np.stack([vec])
        storage = _make_storage(concepts=concepts)
        runner = BenchmarkRunner(storage, em, gold_path=gold_file)
        result = runner.run_extraction_benchmark(ks=[5])
        assert result["per_module"]["MOD001"]["n_predicted"] == 0


# ── run_alignment_benchmark ────────────────────────────────────────────────────

class TestRunAlignmentBenchmark:
    def test_returns_empty_when_no_alignments(self, gold_file):
        storage = _make_storage(concepts=[], alignments=[])
        em = _make_em()
        runner = BenchmarkRunner(storage, em, gold_path=gold_file)
        result = runner.run_alignment_benchmark()
        assert result == {}

    def test_macro_keys_present_with_data(self, gold_file):
        from curriculum_mapper.ingestion.schema import AlignmentResult
        concept = _make_concept("sorting algorithms", ["MOD001"])
        alignment = AlignmentResult(
            concept_id=concept.id,
            ka_code="AL",
            ka_topic="Sorting algorithms",
            method="hybrid",
            score=0.9,
            rank=1,
        )
        em = MagicMock()
        def encode_variable(terms, **kw):
            n = len(terms)
            vecs = np.eye(max(n, 1), 3, dtype=np.float32)[:n]
            return vecs
        em.encode.side_effect = encode_variable
        storage = _make_storage(concepts=[concept], alignments=[alignment])
        runner = BenchmarkRunner(storage, em, gold_path=gold_file)
        result = runner.run_alignment_benchmark(ks=[1, 3])
        assert "macro" in result
        assert "alignment_coverage@1" in result["macro"]

    def test_module_with_no_concepts_gets_zero_coverage(self, gold_file):
        from curriculum_mapper.ingestion.schema import AlignmentResult
        concept = _make_concept("sorting algorithms", ["MOD001"])
        alignment = AlignmentResult(
            concept_id=concept.id,
            ka_code="AL",
            ka_topic="Sorting algorithms",
            method="hybrid",
            score=0.9,
            rank=1,
        )
        em = MagicMock()
        def encode_variable(terms, **kw):
            n = len(terms)
            vecs = np.eye(max(n, 1), 3, dtype=np.float32)[:n]
            return vecs
        em.encode.side_effect = encode_variable
        # only MOD001 has concepts; MOD002 has none
        storage = _make_storage(concepts=[concept], alignments=[alignment])
        runner = BenchmarkRunner(storage, em, gold_path=gold_file)
        result = runner.run_alignment_benchmark(ks=[1])
        assert result["per_module"]["MOD002"]["alignment_coverage@1"] == 0.0


# ── run_all ────────────────────────────────────────────────────────────────────

class TestRunAll:
    def test_run_all_returns_both_keys(self, gold_file):
        storage = _make_storage(concepts=[], alignments=[])
        em = _make_em()
        runner = BenchmarkRunner(storage, em, gold_path=gold_file)
        result = runner.run_all()
        assert "extraction" in result
        assert "alignment" in result
