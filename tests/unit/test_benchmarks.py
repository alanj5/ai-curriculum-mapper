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


def _make_flexible_em(dim: int = 4) -> MagicMock:
    """Mock EmbeddingManager whose encode() returns one unit vector per input."""
    em = MagicMock()

    def _encode(texts, **kwargs):
        rng = np.random.default_rng(abs(hash(tuple(texts))) % (2**32))
        mat = rng.standard_normal((len(texts), dim)).astype(np.float32)
        mat /= np.linalg.norm(mat, axis=1, keepdims=True) + 1e-9
        return mat

    em.encode.side_effect = _encode
    return em


# ── run_canonicalisation_ablation ──────────────────────────────────────────────

class TestCanonicalisationAblation:
    def test_returns_empty_when_no_concepts(self, gold_file):
        runner = BenchmarkRunner(_make_storage(concepts=[]), _make_flexible_em(), gold_path=gold_file)
        assert runner.run_canonicalisation_ablation() == {}

    def test_raw_has_more_surface_forms_than_canonical(self, gold_file):
        c1 = Concept(term="sorting algorithms", variants=["sort algorithm", "sorting"],
                     confidence=0.9, extractors=["tfidf"], module_codes=["MOD001"])
        c2 = Concept(term="virtual memory", variants=["vm"],
                     confidence=0.8, extractors=["rake"], module_codes=["MOD002"])
        runner = BenchmarkRunner(_make_storage(concepts=[c1, c2]),
                                 _make_flexible_em(), gold_path=gold_file)
        out = runner.run_canonicalisation_ablation(ks=[5, 10])
        assert "with_canonicalisation" in out and "without_canonicalisation" in out
        assert out["with_canonicalisation"]["n_concepts"] == 2
        # 2 canonical terms + 3 variants = 5 surface forms
        assert out["without_canonicalisation"]["n_concepts"] == 5
        assert "macro" in out["with_canonicalisation"]


GOLD_WITH_KA = {
    "_metadata": {"annotator": "test"},
    "MOD001": {"module_title": "Algorithms",
               "concepts": [{"term": "dynamic programming", "ka": "AL"},
                            {"term": "binary search", "ka": "AL"}]},
}


@pytest.fixture
def gold_ka_file(tmp_path: Path) -> Path:
    p = tmp_path / "gold_ka.json"
    p.write_text(json.dumps(GOLD_WITH_KA))
    return p


# ── run_aligner_weight_sweep ───────────────────────────────────────────────────

class TestAlignerWeightSweep:
    def test_empty_without_ka_labels(self, gold_file):
        runner = BenchmarkRunner(_make_storage(), _make_flexible_em(), gold_path=gold_file)
        assert runner.run_aligner_weight_sweep() == {}

    def test_sweep_structure_and_determinism(self, gold_ka_file, monkeypatch):
        # Mock the three aligner imports used inside the method.
        from curriculum_mapper.alignment import aligner as aligner_mod
        from curriculum_mapper.alignment import lexical as lexical_mod
        from curriculum_mapper.alignment import semantic as semantic_mod

        monkeypatch.setattr(aligner_mod, "load_ka_data", lambda: {})

        class _Lex:
            def __init__(self, *a, **k): ...
            def align(self, term):
                return [{"ka_code": "AL", "ka_topic": "t", "score": 0.9}]

        class _Sem:
            def __init__(self, *a, **k): ...
            def align(self, emb):
                return [{"ka_code": "AL", "ka_topic": "t", "score": 0.8}]

        monkeypatch.setattr(lexical_mod, "LexicalAligner", _Lex)
        monkeypatch.setattr(semantic_mod, "SemanticAligner", _Sem)

        runner = BenchmarkRunner(_make_storage(), _make_flexible_em(), gold_path=gold_ka_file)
        out = runner.run_aligner_weight_sweep(semantic_weights=[0.0, 0.65, 1.0])
        assert set(out.keys()) == {0.0, 0.65, 1.0}
        for w, r in out.items():
            assert {"top1_accuracy", "top3_accuracy", "mrr", "semantic_weight"} <= set(r)
        # AL is the only KA and matches gold -> perfect accuracy at all weights.
        assert out[1.0]["top1_accuracy"] == 1.0
        # Determinism: identical on a second call.
        out2 = runner.run_aligner_weight_sweep(semantic_weights=[0.0, 0.65, 1.0])
        assert out == out2


# ── run_llm_extraction_benchmark ───────────────────────────────────────────────

class _FakeLLM:
    model = "fake-llm"

    def extract(self, text, top_n=20):
        # Return the gold terms so the benchmark scores a perfect-ish match.
        return [("sorting algorithms", 1.0), ("binary search", 0.8), ("dynamic programming", 0.6)]


class TestLLMExtractionBenchmark:
    def test_returns_metrics(self, gold_file):
        from curriculum_mapper.ingestion.schema import ModuleDescriptor
        mod = ModuleDescriptor(
            code="MOD001", title="Algorithms", level=2, credits=8, prerequisites=[],
            description="sorting algorithms and binary search", ilos=[], topics=[],
            source="institutional", source_file="MOD001.json",
        )
        storage = _make_storage()
        storage.get_all_modules.return_value = [mod]
        runner = BenchmarkRunner(storage, _make_flexible_em(), gold_path=gold_file)
        result = runner.run_llm_extraction_benchmark(_FakeLLM(), ks=[5, 10])
        assert "macro" in result and "model" in result
        assert result["model"] == "fake-llm"
        assert "F1@10" in result["macro"]


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


class TestLLMModelComparison:
    def test_skips_unavailable_and_runs_available(self, gold_file, monkeypatch):
        import curriculum_mapper.nlp.extractors.llm_extractor as llm_mod
        from curriculum_mapper.ingestion.schema import ModuleDescriptor

        class _FakeLLMEx:
            def __init__(self, model="m", **k):
                self.model = model
                self.is_available = model != "down:model"

            def ping(self):
                return self.is_available

            def extract(self, text, top_n=20):
                return [("sorting algorithms", 1.0), ("binary search", 0.8)]

        monkeypatch.setattr(llm_mod, "LLMExtractor", _FakeLLMEx)
        mod = ModuleDescriptor(code="MOD001", title="Algorithms", level=2, credits=8,
                               prerequisites=[], description="sorting and search", ilos=[],
                               topics=[], source="institutional", source_file="MOD001.json")
        storage = _make_storage()
        storage.get_all_modules.return_value = [mod]
        runner = BenchmarkRunner(storage, _make_flexible_em(), gold_path=gold_file)
        out = runner.run_llm_model_comparison(["good:model", "down:model"], ks=[5, 10])
        assert "good:model" in out and "down:model" not in out


# ── New ablation/analysis methods (baselines, error analysis, per-KA, ambiguity) ─
# (reuses the module-level ``gold_ka_file`` fixture + GOLD_WITH_KA defined above)


def _stable_seed(text: str) -> int:
    """Process-independent seed (Python's hash() is randomised per run)."""
    import hashlib
    return int.from_bytes(hashlib.sha256(text.encode()).digest()[:4], "big")


def _make_term_em(dim: int = 16) -> MagicMock:
    """EmbeddingManager mock: a deterministic unit vector *per individual term*,
    so the same string always embeds identically (exact match => cosine 1.0) and
    distinct terms stay near-orthogonal (no spurious hits)."""
    em = MagicMock()

    def _encode(texts, **kwargs):
        out = []
        for t in texts:
            rng = np.random.default_rng(_stable_seed(t))
            v = rng.standard_normal(dim).astype(np.float32)
            v /= np.linalg.norm(v) + 1e-9
            out.append(v)
        return np.stack(out) if out else np.zeros((0, dim), dtype=np.float32)

    em.encode.side_effect = _encode
    return em


def _ns_module(code, full_text, level=1):
    from types import SimpleNamespace
    return SimpleNamespace(code=code, full_text=full_text, full_text_clean=full_text, level=level)


class TestAmbiguityMarginSweep:
    def test_counts_grow_with_margin(self, gold_file):
        from curriculum_mapper.ingestion.schema import AlignmentResult

        def al(cid, rank, score):
            return AlignmentResult(concept_id=cid, ka_code="AL", ka_topic="t",
                                   method="hybrid", score=score, rank=rank)

        aligns = [al("c1", 1, 0.90), al("c1", 2, 0.89),   # gap 0.01
                  al("c2", 1, 0.90), al("c2", 2, 0.50),   # gap 0.40
                  al("c3", 1, 0.80)]                       # no rank-2 → never ambiguous
        runner = BenchmarkRunner(_make_storage(alignments=aligns), _make_flexible_em(),
                                 gold_path=gold_file)
        out = runner.run_ambiguity_margin_sweep(margins=[0.005, 0.05, 0.5])
        assert out[0.005]["ambiguous_count"] == 0
        assert out[0.05]["ambiguous_count"] == 1     # only c1
        assert out[0.5]["ambiguous_count"] == 2      # c1 and c2
        assert out[0.5]["ambiguous_fraction"] == round(2 / 3, 4)


class TestErrorAnalysis:
    def test_hit_miss_and_present_in_text(self, gold_file):
        # gold MOD001 = sorting algorithms / binary search / dynamic programming
        concepts = [_make_concept("sorting algorithms", ["MOD001"]),
                    _make_concept("unrelated thing", ["MOD001"])]
        storage = _make_storage(concepts=concepts)
        storage.get_all_modules.return_value = [
            _ns_module("MOD001", "sorting algorithms and binary search are covered"),
            _ns_module("MOD002", "processes and threads"),
        ]
        runner = BenchmarkRunner(storage, _make_term_em(), gold_path=gold_file)
        out = runner.run_error_analysis(threshold=0.75, k=10)
        assert out["n_gold"] == 6                       # 3 per module × 2 modules
        assert out["n_hit"] == 1                        # exact "sorting algorithms"
        assert out["n_miss"] == 5
        assert out["miss_present_in_text"] >= 1         # "binary search" is in MOD001 text
        assert out["miss_present_in_text"] + out["miss_absent_from_text"] == 5


class TestPerKaAlignment:
    def test_returns_per_ka_counts(self, gold_ka_file):
        runner = BenchmarkRunner(_make_storage(), _make_term_em(), gold_path=gold_ka_file)
        out = runner.run_per_ka_alignment()
        assert "AL" in out
        assert out["AL"]["n"] == 2
        assert 0.0 <= out["AL"]["top1_accuracy"] <= 1.0


class TestBaselineComparison:
    def test_runs_and_reports_novelty(self, gold_file):
        # Four modules with overlapping vocabulary so TF-IDF/LDA min_df=2 keeps terms.
        mods = [
            _ns_module("MOD001", "sorting algorithms and binary search and data structures"),
            _ns_module("MOD002", "process management virtual memory and data structures"),
            _ns_module("MOD003", "sorting algorithms data structures and graph theory"),
            _ns_module("MOD004", "virtual memory process management and graph theory"),
        ]
        concepts = [_make_concept("sorting algorithms", ["MOD001", "MOD003"]),
                    _make_concept("virtual memory", ["MOD002", "MOD004"]),
                    _make_concept("graph theory", ["MOD003", "MOD004"])]
        storage = _make_storage(concepts=concepts)
        storage.get_all_modules.return_value = mods
        runner = BenchmarkRunner(storage, _make_term_em(), gold_path=gold_file)
        out = runner.run_baseline_comparison(ks=[5, 10])
        for key in ("tfidf_only", "lda", "noun_phrases", "random", "ensemble"):
            assert key in out and "macro" in out[key]
        assert 0.0 <= out["novelty_vs_baselines"] <= 1.0
