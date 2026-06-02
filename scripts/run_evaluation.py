#!/usr/bin/env python3
"""Run the full evaluation benchmark suite.

Evaluates concept extraction (P@K, R@K, F1@K, MAP) and KA alignment accuracy
against gold-annotated Imperial College modules using SBERT partial credit.

Also runs per-extractor comparison and lexical vs semantic vs hybrid aligner comparison.

Usage:
    python scripts/run_evaluation.py [--verbose] [--no-figures] [--quick]

    --quick: skip per-extractor and aligner comparisons (faster, ensemble only)

Prerequisites:
    python scripts/run_nlp_pipeline.py --week2
    python scripts/run_alignment.py
    python scripts/build_graph.py  (for KA heatmap)
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from curriculum_mapper.config import PROCESSED_DIR
from curriculum_mapper.evaluation.benchmarks import BenchmarkRunner
from curriculum_mapper.evaluation.reports import (
    generate_figures,
    generate_text_report,
    save_results_json,
)
from curriculum_mapper.ingestion.storage import StorageManager
from curriculum_mapper.nlp.embeddings import EmbeddingManager

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s: %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)


def _build_ka_heatmap_data(storage: StorageManager) -> dict:
    """Build module × KA binary matrix for heatmap figure."""
    modules = storage.get_all_modules()
    alignments = storage.get_all_alignments()
    concepts = storage.get_all_concepts()

    if not modules or not alignments or not concepts:
        return {}

    # Map concept_id → module_codes
    concept_modules: dict[str, list[str]] = {c.id: c.module_codes for c in concepts}

    # Map module → set of KAs it covers
    module_kas: dict[str, set[str]] = {m.code: set() for m in modules}
    for a in alignments:
        if a.rank == 1:
            for mod in concept_modules.get(a.concept_id, []):
                module_kas[mod].add(a.ka_code)

    # Fixed KA order (CS2023)
    ka_order = ["AL", "AR", "CN", "DS", "GV", "HCI", "IAS", "IM", "IS",
                "NC", "OS", "PBD", "PD", "PL", "SDF", "SE", "SF", "SP"]
    module_order = sorted(module_kas.keys())

    matrix = [
        [1 if ka in module_kas.get(mod, set()) else 0 for ka in ka_order]
        for mod in module_order
    ]

    return {"modules": module_order, "kas": ka_order, "matrix": matrix}


def _build_ka_coverage_data(graph_stats_path: Path) -> dict:
    """Load per-KA module coverage fractions from graph_stats.json."""
    if not graph_stats_path.exists():
        return {}
    with open(graph_stats_path) as f:
        gs = json.load(f)
    coverage = gs.get("coverage", {})
    # build_graph writes per-KA fractions under "ka_coverage"; older runs used
    # "per_ka" (dict of {fraction: ...}). Support both for robustness.
    ka_cov = coverage.get("ka_coverage")
    if ka_cov:
        return dict(ka_cov)
    per_ka = coverage.get("per_ka", {})
    if not per_ka:
        return {}
    return {ka: info.get("fraction", 0) for ka, info in per_ka.items()}


def _build_score_distribution(storage: StorageManager) -> list[float]:
    """Collect all alignment scores for histogram."""
    alignments = storage.get_all_alignments()
    return [a.score for a in alignments if a.score is not None]


def main() -> None:
    parser = argparse.ArgumentParser(description="Run evaluation benchmarks")
    parser.add_argument("--verbose", action="store_true")
    parser.add_argument("--no-figures", action="store_true", help="Skip matplotlib figures")
    parser.add_argument("--quick", action="store_true",
                        help="Skip per-extractor and aligner comparison (faster)")
    parser.add_argument("--no-threshold-sweep", action="store_true",
                        help="Skip SBERT threshold sensitivity sweep")
    parser.add_argument("--llm-compare", action="store_true",
                        help="Compare candidate local-LLM extractors on the gold set (needs Ollama)")
    args = parser.parse_args()

    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)

    storage = StorageManager()

    if storage.count_concepts() == 0:
        logger.error("No concepts in DB — run run_nlp_pipeline.py --week2 first.")
        sys.exit(1)
    if storage.count_alignments() == 0:
        logger.error("No alignments in DB — run run_alignment.py first.")
        sys.exit(1)

    logger.info("Initialising embedding model for evaluation (SBERT partial credit)…")
    em = EmbeddingManager()

    runner = BenchmarkRunner(storage, em)

    if args.quick:
        logger.info("Running benchmarks (quick mode — ensemble only)…")
        results = runner.run_all()
    else:
        logger.info("Running full extended benchmarks (per-extractor + aligner comparison)…")
        results = runner.run_all_extended()

    if not args.quick and not args.no_threshold_sweep:
        logger.info("Running SBERT threshold sensitivity sweep…")
        results["threshold_sweep"] = runner.run_threshold_sweep()

    if not args.quick:
        logger.info("Running aligner weight sweep (lexical/semantic split)…")
        results["aligner_weight_sweep"] = runner.run_aligner_weight_sweep()
        logger.info("Running canonicalisation ablation…")
        results["canonicalisation_ablation"] = runner.run_canonicalisation_ablation()
        logger.info("Running perturbation-robustness analysis…")
        from curriculum_mapper.alignment.aligner import load_ka_data
        from curriculum_mapper.evaluation.robustness import run_perturbation_robustness
        results["perturbation"] = run_perturbation_robustness(storage, load_ka_data())

    # ── Optional: local-LLM extractor benchmark / model comparison ─────────────
    from curriculum_mapper.config import LLM_EXTRACTOR_ENABLED, LLM_MODEL
    if args.llm_compare or LLM_EXTRACTOR_ENABLED:
        from curriculum_mapper.nlp.extractors.llm_extractor import LLMExtractor
        probe = LLMExtractor()
        if probe.is_available and probe.ping():
            models = ["llama3.1:8b", "qwen2.5:7b"] if args.llm_compare else [LLM_MODEL]
            logger.info(f"Running LLM extraction benchmark for: {models}")
            comp = runner.run_llm_model_comparison(models)
            if comp:
                results["llm_model_comparison"] = comp
                # Headline LLM slot = best model by MAP.
                best_name, best_res = max(
                    comp.items(), key=lambda kv: kv[1].get("macro", {}).get("MAP", 0)
                )
                results["llm_extraction"] = best_res
                logger.info(f"Best LLM extractor by MAP: {best_name}")
        else:
            logger.warning("LLM requested but Ollama server unreachable; skipping LLM benchmark.")

    # Attach graph stats
    graph_stats_path = PROCESSED_DIR / "graph_stats.json"
    if graph_stats_path.exists():
        with open(graph_stats_path) as f:
            gs = json.load(f)
        coverage = gs.get("coverage", {})
        mm = gs.get("module_module", {})
        results["graph"] = {
            "mm_nodes": mm.get("nodes", "?"),
            "mm_edges": mm.get("edges", "?"),
            "n_communities": mm.get("n_communities", "?"),
            "total_kas": coverage.get("total_kas", "?"),
            "covered_kas": coverage.get("covered_kas", "?"),
            "coverage_fraction": coverage.get("coverage_fraction", 0),
            "critical_gap_count": len(coverage.get("critical_gaps", [])),
            "warning_gap_count": len(coverage.get("warning_gaps", [])),
        }

    # Attach KA coverage per-KA fractions for the bar chart
    ka_cov = _build_ka_coverage_data(graph_stats_path)
    if ka_cov:
        results["ka_coverage"] = ka_cov

    # Attach alignment score distribution
    results["score_distribution"] = _build_score_distribution(storage)

    # Attach KA heatmap data
    logger.info("Building module × KA coverage matrix for heatmap…")
    results["ka_heatmap"] = _build_ka_heatmap_data(storage)

    # Save outputs
    json_path = save_results_json(results)
    txt_path = generate_text_report(results)

    if not args.no_figures:
        figs = generate_figures(results)
        logger.info(f"Generated {len(figs)} figures.")

    # Print report to console
    with open(txt_path) as f:
        print(f.read())

    logger.info(f"JSON results: {json_path}")
    logger.info(f"Text report:  {txt_path}")


if __name__ == "__main__":
    main()
