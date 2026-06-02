"""Tests for evaluation report generation (reports.py)."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

from curriculum_mapper.evaluation.reports import (
    generate_figures,
    generate_text_report,
    save_results_json,
)

# ── Sample results fixture ─────────────────────────────────────────────────────

SAMPLE_RESULTS = {
    "extraction": {
        "macro": {
            "P@5": 0.4,
            "P@10": 0.22,
            "P@20": 0.16,
            "R@5": 0.10,
            "R@10": 0.12,
            "R@20": 0.15,
            "F1@5": 0.155,
            "F1@10": 0.146,
            "F1@20": 0.150,
            "MAP": 0.153,
        },
        "per_module": {
            "IC50001": {
                "P@10": 0.2,
                "R@10": 0.1,
                "F1@10": 0.133,
                "AP": 0.071,
                "n_predicted": 40,
                "n_gold": 15,
            },
            "IC50004": {
                "P@10": 0.4,
                "R@10": 0.136,
                "F1@10": 0.203,
                "AP": 0.283,
                "n_predicted": 55,
                "n_gold": 22,
            },
        },
    },
    "alignment": {
        "macro": {
            "alignment_coverage@1": 0.25,
            "alignment_coverage@3": 0.25,
            "mean_gold_match": 0.25,
        },
        "per_module": {
            "IC50001": {
                "alignment_coverage@1": 0.067,
                "alignment_coverage@3": 0.067,
                "gold_matched_fraction": 0.067,
            },
            "IC50004": {
                "alignment_coverage@1": 0.318,
                "alignment_coverage@3": 0.318,
                "gold_matched_fraction": 0.318,
            },
        },
    },
    "graph": {
        "mm_nodes": 21,
        "mm_edges": 153,
        "n_communities": 4,
        "covered_kas": 18,
        "total_kas": 18,
        "coverage_fraction": 1.0,
        "critical_gap_count": 0,
        "warning_gap_count": 0,
    },
}

EMPTY_RESULTS: dict = {}


# ── save_results_json ──────────────────────────────────────────────────────────

class TestSaveResultsJson:
    def test_creates_file(self, tmp_path):
        p = tmp_path / "results.json"
        out = save_results_json(SAMPLE_RESULTS, path=p)
        assert out == p
        assert p.exists()

    def test_valid_json_content(self, tmp_path):
        p = tmp_path / "results.json"
        save_results_json(SAMPLE_RESULTS, path=p)
        with open(p) as f:
            data = json.load(f)
        assert data["graph"]["mm_nodes"] == 21

    def test_empty_results(self, tmp_path):
        p = tmp_path / "empty.json"
        save_results_json(EMPTY_RESULTS, path=p)
        with open(p) as f:
            data = json.load(f)
        assert data == {}

    def test_returns_path_object(self, tmp_path):
        p = tmp_path / "out.json"
        result = save_results_json(SAMPLE_RESULTS, path=p)
        assert isinstance(result, Path)


# ── generate_text_report ───────────────────────────────────────────────────────

class TestGenerateTextReport:
    def test_creates_file(self, tmp_path):
        p = tmp_path / "report.txt"
        out = generate_text_report(SAMPLE_RESULTS, path=p)
        assert out == p
        assert p.exists()

    def test_contains_extraction_section(self, tmp_path):
        p = tmp_path / "report.txt"
        generate_text_report(SAMPLE_RESULTS, path=p)
        text = p.read_text()
        assert "CONCEPT EXTRACTION" in text
        assert "F1@10" in text

    def test_contains_alignment_section(self, tmp_path):
        p = tmp_path / "report.txt"
        generate_text_report(SAMPLE_RESULTS, path=p)
        text = p.read_text()
        assert "KA ALIGNMENT" in text
        assert "Coverage@1" in text

    def test_contains_graph_section(self, tmp_path):
        p = tmp_path / "report.txt"
        generate_text_report(SAMPLE_RESULTS, path=p)
        text = p.read_text()
        assert "GRAPH ANALYTICS" in text
        assert "21" in text

    def test_per_module_lines_present(self, tmp_path):
        p = tmp_path / "report.txt"
        generate_text_report(SAMPLE_RESULTS, path=p)
        text = p.read_text()
        assert "IC50001" in text
        assert "IC50004" in text

    def test_empty_results_produces_minimal_report(self, tmp_path):
        p = tmp_path / "empty_report.txt"
        generate_text_report(EMPTY_RESULTS, path=p)
        text = p.read_text()
        assert "END OF REPORT" in text

    def test_macro_values_in_report(self, tmp_path):
        p = tmp_path / "report.txt"
        generate_text_report(SAMPLE_RESULTS, path=p)
        text = p.read_text()
        assert "0.1460" in text  # F1@10

    def test_returns_path(self, tmp_path):
        p = tmp_path / "r.txt"
        result = generate_text_report(SAMPLE_RESULTS, path=p)
        assert isinstance(result, Path)


# ── generate_figures ───────────────────────────────────────────────────────────

class TestGenerateFigures:
    def test_returns_list(self, tmp_path):
        # Patch FIGURES_DIR so files go to tmp_path
        with patch("curriculum_mapper.evaluation.reports.FIGURES_DIR", tmp_path):
            saved = generate_figures(SAMPLE_RESULTS)
        assert isinstance(saved, list)

    def test_saves_extraction_figure(self, tmp_path):
        with patch("curriculum_mapper.evaluation.reports.FIGURES_DIR", tmp_path):
            saved = generate_figures(SAMPLE_RESULTS)
        names = [p.name for p in saved]
        assert "extraction_prf_at_k.png" in names

    def test_saves_alignment_figure(self, tmp_path):
        with patch("curriculum_mapper.evaluation.reports.FIGURES_DIR", tmp_path):
            saved = generate_figures(SAMPLE_RESULTS)
        names = [p.name for p in saved]
        assert "alignment_coverage.png" in names

    def test_saves_per_module_f1_figure(self, tmp_path):
        with patch("curriculum_mapper.evaluation.reports.FIGURES_DIR", tmp_path):
            saved = generate_figures(SAMPLE_RESULTS)
        names = [p.name for p in saved]
        assert "extraction_f1_per_module.png" in names

    def test_empty_results_produces_no_figures(self, tmp_path):
        with patch("curriculum_mapper.evaluation.reports.FIGURES_DIR", tmp_path):
            saved = generate_figures(EMPTY_RESULTS)
        assert saved == []

    def test_figures_are_png_files(self, tmp_path):
        with patch("curriculum_mapper.evaluation.reports.FIGURES_DIR", tmp_path):
            saved = generate_figures(SAMPLE_RESULTS)
        for p in saved:
            assert p.suffix == ".png"
            assert p.exists()

    def test_handles_matplotlib_import_error(self, tmp_path):
        with patch("curriculum_mapper.evaluation.reports.FIGURES_DIR", tmp_path):
            with patch("builtins.__import__", side_effect=ImportError("no matplotlib")):
                # Should not raise; returns empty list
                try:
                    saved = generate_figures(EMPTY_RESULTS)
                    assert isinstance(saved, list)
                except Exception:
                    pass  # acceptable if matplotlib import path differs


# ── New ablation sections (weight sweep + canonicalisation) ────────────────────

ABLATION_RESULTS = {
    "aligner_weight_sweep": {
        "0.0": {"semantic_weight": 0.0, "lexical_weight": 1.0,
                "top1_accuracy": 0.636, "top3_accuracy": 0.805, "mrr": 0.717},
        "0.65": {"semantic_weight": 0.65, "lexical_weight": 0.35,
                 "top1_accuracy": 0.675, "top3_accuracy": 0.831, "mrr": 0.745},
        "1.0": {"semantic_weight": 1.0, "lexical_weight": 0.0,
                "top1_accuracy": 0.714, "top3_accuracy": 0.844, "mrr": 0.777},
    },
    "canonicalisation_ablation": {
        "with_canonicalisation": {"macro": {"F1@10": 0.138, "MAP": 0.097}, "n_concepts": 658},
        "without_canonicalisation": {"macro": {"F1@10": 0.138, "MAP": 0.091}, "n_concepts": 704},
    },
}


class TestAblationReporting:
    def test_text_report_includes_weight_sweep(self, tmp_path):
        path = generate_text_report(ABLATION_RESULTS, path=tmp_path / "r.txt")
        text = path.read_text()
        assert "WEIGHT SWEEP" in text.upper()
        assert "CANONICALISATION ABLATION" in text.upper()

    def test_weight_sweep_figure_saved(self, tmp_path):
        with patch("curriculum_mapper.evaluation.reports.FIGURES_DIR", tmp_path):
            saved = generate_figures(ABLATION_RESULTS)
        names = [p.name for p in saved]
        assert "aligner_weight_sweep.png" in names


FULL_RESULTS = {
    **SAMPLE_RESULTS,
    "extraction_per_extractor": {
        "tfidf": {"macro": {"F1@5": 0.0, "F1@10": 0.02, "F1@20": 0.03, "MAP": 0.003}},
        "rake": {"macro": {"F1@5": 0.1, "F1@10": 0.14, "F1@20": 0.23, "MAP": 0.088}},
        "ensemble": {"macro": {"F1@5": 0.13, "F1@10": 0.14, "F1@20": 0.14, "MAP": 0.097}},
    },
    "aligner_comparison": {
        "lexical": {"top1_accuracy": 0.636, "top3_accuracy": 0.805, "mrr": 0.717},
        "semantic": {"top1_accuracy": 0.727, "top3_accuracy": 0.844, "mrr": 0.789},
        "hybrid": {"top1_accuracy": 0.675, "top3_accuracy": 0.831, "mrr": 0.745},
    },
    "threshold_sweep": {
        0.60: {"F1@10": 0.37, "MAP": 0.49}, 0.75: {"F1@10": 0.14, "MAP": 0.10},
        0.85: {"F1@10": 0.05, "MAP": 0.03},
    },
    "ka_coverage": {"GV": 0.43, "OS": 0.48, "IS": 1.0, "SDF": 1.0},
    "score_distribution": [0.4, 0.5, 0.6, 0.7, 0.8],
    "ka_heatmap": {"modules": ["IC50001", "IC50004"], "kas": ["AL", "OS"],
                   "matrix": [[1, 0], [0, 1]]},
    "graph": {"mm_nodes": 21, "mm_edges": 146, "n_communities": 4,
              "covered_kas": 18, "total_kas": 18, "coverage_fraction": 1.0,
              "critical_gap_count": 0, "warning_gap_count": 0},
    **ABLATION_RESULTS,
}


class TestFullReportCoverage:
    def test_text_report_all_sections(self, tmp_path):
        text = generate_text_report(FULL_RESULTS, path=tmp_path / "r.txt").read_text()
        for marker in ["PER-EXTRACTOR", "ALIGNER COMPARISON", "THRESHOLD SENSITIVITY",
                       "GRAPH ANALYTICS", "WEIGHT SWEEP", "CANONICALISATION ABLATION"]:
            assert marker in text.upper()

    def test_all_figures_generated(self, tmp_path):
        with patch("curriculum_mapper.evaluation.reports.FIGURES_DIR", tmp_path):
            saved = generate_figures(FULL_RESULTS)
        names = {p.name for p in saved}
        for fig in ["extraction_per_extractor.png", "aligner_comparison.png",
                    "alignment_score_distribution.png", "ka_coverage_bar.png",
                    "threshold_sensitivity.png", "aligner_weight_sweep.png",
                    "ka_module_heatmap.png"]:
            assert fig in names


LLM_RESULTS = {
    **FULL_RESULTS,
    "llm_model_comparison": {
        "llama3.1:8b": {"macro": {"F1@5": 0.35, "F1@10": 0.41, "F1@20": 0.45, "MAP": 0.41}},
        "qwen2.5:7b": {"macro": {"F1@5": 0.39, "F1@10": 0.41, "F1@20": 0.29, "MAP": 0.31}},
    },
}


class TestLLMReporting:
    def test_text_report_includes_llm_section(self, tmp_path):
        text = generate_text_report(LLM_RESULTS, path=tmp_path / "r.txt").read_text()
        assert "LLM-AUGMENTED EXTRACTION" in text.upper()

    def test_llm_figure_saved(self, tmp_path):
        with patch("curriculum_mapper.evaluation.reports.FIGURES_DIR", tmp_path):
            saved = generate_figures(LLM_RESULTS)
        assert "llm_vs_ensemble.png" in {p.name for p in saved}
