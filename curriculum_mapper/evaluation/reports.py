"""Report generation for evaluation results.

Generates:
  - JSON summary: data/processed/evaluation_results.json
  - Text report: data/processed/evaluation_report.txt
  - Figures: data/processed/figures/*.png (matplotlib)
"""

from __future__ import annotations

import json
import logging
from pathlib import Path

from curriculum_mapper.config import FIGURES_DIR, PROCESSED_DIR, SBERT_MATCH_THRESHOLD

logger = logging.getLogger(__name__)


def save_results_json(results: dict, path: Path | None = None) -> Path:
    """Persist benchmark results dict to JSON."""
    path = path or (PROCESSED_DIR / "evaluation_results.json")
    with open(path, "w") as f:
        json.dump(results, f, indent=2)
    logger.info(f"Saved evaluation results to {path}")
    return path


def generate_text_report(results: dict, path: Path | None = None) -> Path:
    """Generate a human-readable plain-text evaluation report."""
    path = path or (PROCESSED_DIR / "evaluation_report.txt")

    lines: list[str] = [
        "=" * 70,
        "AI CURRICULUM MAPPER — EVALUATION REPORT",
        "=" * 70,
        "",
    ]

    # ── Extraction metrics (ensemble) ──────────────────────────────────────────
    ext = results.get("extraction", {})
    if ext:
        macro = ext.get("macro", {})
        lines += [
            f"CONCEPT EXTRACTION — ENSEMBLE (SBERT partial credit, threshold={SBERT_MATCH_THRESHOLD})",
            "-" * 70,
            f"  P@5  = {macro.get('P@5', 0):.4f}",
            f"  P@10 = {macro.get('P@10', 0):.4f}",
            f"  P@20 = {macro.get('P@20', 0):.4f}",
            f"  R@5  = {macro.get('R@5', 0):.4f}",
            f"  R@10 = {macro.get('R@10', 0):.4f}",
            f"  R@20 = {macro.get('R@20', 0):.4f}",
            f"  F1@5  = {macro.get('F1@5', 0):.4f}",
            f"  F1@10 = {macro.get('F1@10', 0):.4f}",
            f"  F1@20 = {macro.get('F1@20', 0):.4f}",
            f"  MAP  = {macro.get('MAP', 0):.4f}",
            "",
            "  Per-module breakdown:",
        ]
        per = ext.get("per_module", {})
        for mod, mres in per.items():
            lines.append(
                f"    {mod}: P@10={mres.get('P@10', 0):.3f} "
                f"R@10={mres.get('R@10', 0):.3f} "
                f"F1@10={mres.get('F1@10', 0):.3f} "
                f"AP={mres.get('AP', 0):.3f} "
                f"(pred={mres.get('n_predicted', 0)}, gold={mres.get('n_gold', 0)})"
            )
        lines.append("")

    # ── Per-extractor comparison ───────────────────────────────────────────────
    per_ext = results.get("extraction_per_extractor", {})
    if per_ext:
        lines += [
            "CONCEPT EXTRACTION — PER-EXTRACTOR (macro F1@10 and MAP)",
            "-" * 70,
            f"  {'Extractor':<12} {'F1@5':>8} {'F1@10':>8} {'F1@20':>8} {'MAP':>8}",
        ]
        for name in ["tfidf", "rake", "textrank", "keybert", "bertopic", "ensemble"]:
            if name not in per_ext:
                continue
            m = per_ext[name].get("macro", {})
            lines.append(
                f"  {name:<12} {m.get('F1@5', 0):>8.4f} {m.get('F1@10', 0):>8.4f} "
                f"{m.get('F1@20', 0):>8.4f} {m.get('MAP', 0):>8.4f}"
            )
        lines.append("")

    # ── Alignment metrics ──────────────────────────────────────────────────────
    aln = results.get("alignment", {})
    if aln:
        macro = aln.get("macro", {})
        lines += [
            "KA ALIGNMENT ACCURACY (against gold concept→KA annotations)",
            "-" * 70,
            f"  Coverage@1 (Top-1 KA accuracy) = {macro.get('alignment_coverage@1', 0):.4f}",
            f"  Coverage@3 (Top-3 KA accuracy) = {macro.get('alignment_coverage@3', 0):.4f}",
            f"  MRR                            = {macro.get('mrr', 0):.4f}",
            f"  Gold match fraction            = {macro.get('mean_gold_match', 0):.4f}",
            "",
            "  Per-module breakdown:",
        ]
        per = aln.get("per_module", {})
        for mod, mres in per.items():
            lines.append(
                f"    {mod}: cov@1={mres.get('alignment_coverage@1', 0):.3f} "
                f"cov@3={mres.get('alignment_coverage@3', 0):.3f} "
                f"MRR={mres.get('mrr', 0):.3f} "
                f"gold_match={mres.get('gold_matched_fraction', 0):.3f}"
            )
        lines.append("")

    # ── Aligner comparison ─────────────────────────────────────────────────────
    aligner_cmp = results.get("aligner_comparison", {})
    if aligner_cmp:
        lines += [
            "ALIGNER COMPARISON (lexical vs semantic vs hybrid)",
            "-" * 70,
            f"  {'Aligner':<10} {'Top-1':>8} {'Top-3':>8} {'MRR':>8}",
        ]
        for name in ["lexical", "semantic", "hybrid"]:
            if name not in aligner_cmp:
                continue
            r = aligner_cmp[name]
            lines.append(
                f"  {name:<10} {r.get('top1_accuracy', 0):>8.4f} "
                f"{r.get('top3_accuracy', 0):>8.4f} {r.get('mrr', 0):>8.4f}"
            )
        lines.append("")

    # ── Threshold sensitivity ──────────────────────────────────────────────────
    sweep = results.get("threshold_sweep", {})
    if sweep:
        f1_key = next(k for k in next(iter(sweep.values())) if k.startswith("F1"))
        lines += [
            f"SBERT THRESHOLD SENSITIVITY ({f1_key} and MAP at K=10)",
            "-" * 70,
            f"  {'Threshold':>12} {f1_key:>10} {'MAP':>10}",
        ]
        for t in sorted(sweep.keys()):
            lines.append(
                f"  {t:>12.2f} {sweep[t].get(f1_key, 0):>10.4f} {sweep[t].get('MAP', 0):>10.4f}"
            )
        lines.append("")

    # ── Aligner weight sweep ───────────────────────────────────────────────────
    wsweep = results.get("aligner_weight_sweep", {})
    if wsweep:
        lines += [
            "ALIGNER WEIGHT SWEEP (semantic/lexical split on gold concept→KA pairs)",
            "-" * 70,
            f"  {'Sem wt':>8} {'Lex wt':>8} {'Top-1':>8} {'Top-3':>8} {'MRR':>8}",
        ]
        for w in sorted(wsweep.keys(), key=float):
            r = wsweep[w]
            lines.append(
                f"  {r.get('semantic_weight', 0):>8.2f} {r.get('lexical_weight', 0):>8.2f} "
                f"{r.get('top1_accuracy', 0):>8.4f} {r.get('top3_accuracy', 0):>8.4f} "
                f"{r.get('mrr', 0):>8.4f}"
            )
        lines.append("")

    # ── Canonicalisation ablation ──────────────────────────────────────────────
    canon = results.get("canonicalisation_ablation", {})
    if canon:
        with_c = canon.get("with_canonicalisation", {})
        without_c = canon.get("without_canonicalisation", {})
        wm, om = with_c.get("macro", {}), without_c.get("macro", {})
        lines += [
            "CANONICALISATION ABLATION (with vs without SBERT/WordNet merging)",
            "-" * 70,
            f"  {'Setting':<22} {'#Concepts':>10} {'F1@10':>8} {'MAP':>8}",
            f"  {'with canonicalisation':<22} {with_c.get('n_concepts', '?'):>10} "
            f"{wm.get('F1@10', 0):>8.4f} {wm.get('MAP', 0):>8.4f}",
            f"  {'without (raw variants)':<22} {without_c.get('n_concepts', '?'):>10} "
            f"{om.get('F1@10', 0):>8.4f} {om.get('MAP', 0):>8.4f}",
            "",
        ]

    # ── LLM extractor comparison ───────────────────────────────────────────────
    llm_comp = results.get("llm_model_comparison", {})
    if llm_comp:
        ens = results.get("extraction", {}).get("macro", {})
        rake = results.get("extraction_per_extractor", {}).get("rake", {}).get("macro", {})
        lines += [
            "LLM-AUGMENTED EXTRACTION (local Ollama models vs ensemble, gold set)",
            "-" * 70,
            f"  {'Extractor':<16} {'F1@5':>8} {'F1@10':>8} {'F1@20':>8} {'MAP':>8}",
        ]
        for name in sorted(llm_comp.keys()):
            m = llm_comp[name].get("macro", {})
            lines.append(
                f"  {name:<16} {m.get('F1@5', 0):>8.4f} {m.get('F1@10', 0):>8.4f} "
                f"{m.get('F1@20', 0):>8.4f} {m.get('MAP', 0):>8.4f}"
            )
        if rake:
            lines.append(
                f"  {'rake (best 1)':<16} {rake.get('F1@5', 0):>8.4f} {rake.get('F1@10', 0):>8.4f} "
                f"{rake.get('F1@20', 0):>8.4f} {rake.get('MAP', 0):>8.4f}"
            )
        if ens:
            lines.append(
                f"  {'ensemble (5)':<16} {ens.get('F1@5', 0):>8.4f} {ens.get('F1@10', 0):>8.4f} "
                f"{ens.get('F1@20', 0):>8.4f} {ens.get('MAP', 0):>8.4f}"
            )
        lines.append("")

    # ── Perturbation robustness ────────────────────────────────────────────────
    perturb = results.get("perturbation", {})
    if perturb:
        lines += [
            "PERTURBATION ROBUSTNESS (drop lowest-confidence concepts)",
            "-" * 70,
            f"  {'%Rem':>5} {'Concepts':>9} {'MMedges':>8} {'Comm':>5} "
            f"{'CoveredKA':>10} {'Coverage':>9} {'Redund':>7}",
        ]
        for f in sorted(perturb.keys(), key=float):
            r = perturb[f]
            lines.append(
                f"  {int(float(f) * 100):>4d}% {r['n_concepts']:>9} {r['mm_edges']:>8} "
                f"{r['n_communities']:>5} {r['covered_kas']:>4}/{r['total_kas']:<5} "
                f"{r['coverage_fraction']:>9.3f} {r['redundancy_count']:>7}"
            )
        lines.append("")

    # ── Graph stats ────────────────────────────────────────────────────────────
    graph = results.get("graph", {})
    if graph:
        lines += [
            "GRAPH ANALYTICS",
            "-" * 70,
            f"  Module-module nodes: {graph.get('mm_nodes', '?')}",
            f"  Module-module edges: {graph.get('mm_edges', '?')}",
            f"  Communities detected: {graph.get('n_communities', '?')}",
            f"  KAs with coverage >= 10%: {graph.get('covered_kas', '?')} / {graph.get('total_kas', '?')}",
            f"  Coverage fraction: {graph.get('coverage_fraction', 0):.4f}",
            f"  Critical gaps (0% coverage): {graph.get('critical_gap_count', '?')}",
            f"  Warning gaps (1-9% coverage): {graph.get('warning_gap_count', '?')}",
            "",
        ]

    lines += ["=" * 70, "END OF REPORT"]

    text = "\n".join(lines)
    with open(path, "w") as f:
        f.write(text)
    logger.info(f"Saved evaluation report to {path}")
    return path


def generate_figures(results: dict) -> list[Path]:
    """Generate matplotlib figures. Returns list of saved figure paths."""
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except ImportError:
        logger.warning("matplotlib not available — skipping figure generation.")
        return []

    FIGURES_DIR.mkdir(parents=True, exist_ok=True)
    saved: list[Path] = []

    # ── Figure 1: P/R/F1 at K (ensemble) ─────────────────────────────────────
    ext = results.get("extraction", {}).get("macro", {})
    if ext:
        ks = [5, 10, 20]
        p_vals = [ext.get(f"P@{k}", 0) for k in ks]
        r_vals = [ext.get(f"R@{k}", 0) for k in ks]
        f1_vals = [ext.get(f"F1@{k}", 0) for k in ks]

        fig, ax = plt.subplots(figsize=(7, 4))
        x = range(len(ks))
        ax.plot(x, p_vals, "o-", label="Precision@K", color="#2196F3")
        ax.plot(x, r_vals, "s-", label="Recall@K", color="#4CAF50")
        ax.plot(x, f1_vals, "^-", label="F1@K", color="#FF5722")
        ax.set_xticks(list(x))
        ax.set_xticklabels([f"K={k}" for k in ks])
        ax.set_ylim(0, 1)
        ax.set_ylabel("Score")
        ax.set_title("Concept Extraction: P/R/F1 at K (ensemble, SBERT partial credit)")
        ax.legend()
        ax.grid(True, alpha=0.3)
        fig.tight_layout()
        path = FIGURES_DIR / "extraction_prf_at_k.png"
        fig.savefig(path, dpi=150)
        plt.close(fig)
        saved.append(path)

    # ── Figure 2: Alignment coverage per module ───────────────────────────────
    aln = results.get("alignment", {})
    per = aln.get("per_module", {})
    if per:
        modules = list(per.keys())
        cov1 = [per[m].get("alignment_coverage@1", 0) for m in modules]
        cov3 = [per[m].get("alignment_coverage@3", 0) for m in modules]

        fig, ax = plt.subplots(figsize=(8, 4))
        x = range(len(modules))
        ax.bar([xi - 0.2 for xi in x], cov1, width=0.35, label="Top-1 Accuracy", color="#2196F3")
        ax.bar([xi + 0.2 for xi in x], cov3, width=0.35, label="Top-3 Accuracy", color="#4CAF50")
        ax.set_xticks(list(x))
        ax.set_xticklabels(modules, rotation=30, ha="right")
        ax.set_ylim(0, 1)
        ax.set_ylabel("KA Alignment Accuracy")
        ax.set_title("KA Alignment Accuracy per Annotated Module (hybrid aligner)")
        ax.legend()
        ax.grid(True, alpha=0.3, axis="y")
        fig.tight_layout()
        path = FIGURES_DIR / "alignment_coverage.png"
        fig.savefig(path, dpi=150)
        plt.close(fig)
        saved.append(path)

    # ── Figure 3: Per-module extraction F1@10 ─────────────────────────────────
    ext_per = results.get("extraction", {}).get("per_module", {})
    if ext_per:
        modules = list(ext_per.keys())
        f1_10 = [ext_per[m].get("F1@10", 0) for m in modules]

        fig, ax = plt.subplots(figsize=(8, 4))
        bars = ax.bar(range(len(modules)), f1_10, color="#9C27B0")
        ax.set_xticks(list(range(len(modules))))
        ax.set_xticklabels(modules, rotation=30, ha="right")
        ax.set_ylim(0, 1)
        ax.set_ylabel("F1@10")
        ax.set_title("Concept Extraction F1@10 per Annotated Module (ensemble)")
        ax.grid(True, alpha=0.3, axis="y")
        for bar, val in zip(bars, f1_10):
            ax.text(
                bar.get_x() + bar.get_width() / 2,
                bar.get_height() + 0.01,
                f"{val:.2f}",
                ha="center", va="bottom", fontsize=9,
            )
        fig.tight_layout()
        path = FIGURES_DIR / "extraction_f1_per_module.png"
        fig.savefig(path, dpi=150)
        plt.close(fig)
        saved.append(path)

    # ── Figure 4: Per-extractor F1@10 comparison ─────────────────────────────
    per_ext = results.get("extraction_per_extractor", {})
    if per_ext:
        extractor_order = ["tfidf", "rake", "textrank", "keybert", "bertopic", "ensemble"]
        present = [e for e in extractor_order if e in per_ext]
        f1_5 = [per_ext[e].get("macro", {}).get("F1@5", 0) for e in present]
        f1_10 = [per_ext[e].get("macro", {}).get("F1@10", 0) for e in present]
        map_vals = [per_ext[e].get("macro", {}).get("MAP", 0) for e in present]

        x = range(len(present))
        width = 0.25
        fig, ax = plt.subplots(figsize=(10, 5))
        ax.bar([xi - width for xi in x], f1_5, width=width, label="F1@5", color="#2196F3")
        ax.bar(list(x), f1_10, width=width, label="F1@10", color="#FF5722")
        ax.bar([xi + width for xi in x], map_vals, width=width, label="MAP", color="#4CAF50")
        ax.set_xticks(list(x))
        labels = [e.upper() if e != "ensemble" else "Ensemble" for e in present]
        ax.set_xticklabels(labels, rotation=20, ha="right")
        ax.set_ylim(0, max(max(f1_5 + f1_10 + map_vals, default=0) + 0.05, 0.3))
        ax.set_ylabel("Score (macro average)")
        ax.set_title("Concept Extraction: Per-Extractor vs Ensemble Comparison")
        ax.legend()
        ax.grid(True, alpha=0.3, axis="y")
        fig.tight_layout()
        path = FIGURES_DIR / "extraction_per_extractor.png"
        fig.savefig(path, dpi=150)
        plt.close(fig)
        saved.append(path)
        logger.info(f"Saved figure: {path}")

    # ── Figure 5: Aligner comparison ──────────────────────────────────────────
    aligner_cmp = results.get("aligner_comparison", {})
    if aligner_cmp:
        aligner_order = ["lexical", "semantic", "hybrid"]
        present = [a for a in aligner_order if a in aligner_cmp]
        top1 = [aligner_cmp[a].get("top1_accuracy", 0) for a in present]
        top3 = [aligner_cmp[a].get("top3_accuracy", 0) for a in present]
        mrr_vals = [aligner_cmp[a].get("mrr", 0) for a in present]

        x = range(len(present))
        width = 0.25
        fig, ax = plt.subplots(figsize=(7, 4))
        ax.bar([xi - width for xi in x], top1, width=width, label="Top-1 Accuracy", color="#2196F3")
        ax.bar(list(x), top3, width=width, label="Top-3 Accuracy", color="#FF5722")
        ax.bar([xi + width for xi in x], mrr_vals, width=width, label="MRR", color="#4CAF50")
        ax.set_xticks(list(x))
        ax.set_xticklabels([a.capitalize() for a in present])
        ax.set_ylim(0, 1)
        ax.set_ylabel("Score")
        ax.set_title("KA Alignment: Lexical vs Semantic vs Hybrid Aligner")
        ax.legend()
        ax.grid(True, alpha=0.3, axis="y")
        for i, (t1, t3, mr) in enumerate(zip(top1, top3, mrr_vals)):
            ax.text(i - width, t1 + 0.01, f"{t1:.2f}", ha="center", va="bottom", fontsize=8)
            ax.text(i, t3 + 0.01, f"{t3:.2f}", ha="center", va="bottom", fontsize=8)
            ax.text(i + width, mr + 0.01, f"{mr:.2f}", ha="center", va="bottom", fontsize=8)
        fig.tight_layout()
        path = FIGURES_DIR / "aligner_comparison.png"
        fig.savefig(path, dpi=150)
        plt.close(fig)
        saved.append(path)
        logger.info(f"Saved figure: {path}")

    # ── Figure 6: Alignment score distribution ────────────────────────────────
    score_data = results.get("score_distribution", [])
    if score_data:
        fig, ax = plt.subplots(figsize=(7, 4))
        ax.hist(score_data, bins=30, color="#607D8B", edgecolor="white", linewidth=0.5)
        ax.set_xlabel("Hybrid Alignment Score")
        ax.set_ylabel("Frequency")
        ax.set_title(f"Distribution of {len(score_data)} Alignment Scores")
        ax.axvline(x=0.35, color="#F44336", linestyle="--", label="Threshold (0.35)")
        ax.legend()
        ax.grid(True, alpha=0.3, axis="y")
        fig.tight_layout()
        path = FIGURES_DIR / "alignment_score_distribution.png"
        fig.savefig(path, dpi=150)
        plt.close(fig)
        saved.append(path)

    # ── Figure 7: KA coverage horizontal bar ─────────────────────────────────
    ka_cov = results.get("ka_coverage", {})
    if ka_cov:
        ka_codes = list(ka_cov.keys())
        coverages = [ka_cov[k] for k in ka_codes]
        colors = [
            "#4CAF50" if c >= 0.5 else "#FF9800" if c >= 0.1 else "#F44336"
            for c in coverages
        ]
        sorted_pairs = sorted(zip(ka_codes, coverages, colors), key=lambda t: t[1])
        ka_codes_s, cov_s, colors_s = zip(*sorted_pairs) if sorted_pairs else ([], [], [])

        fig, ax = plt.subplots(figsize=(9, 7))
        bars = ax.barh(range(len(ka_codes_s)), cov_s, color=list(colors_s))
        ax.set_yticks(range(len(ka_codes_s)))
        ax.set_yticklabels(list(ka_codes_s), fontsize=9)
        ax.set_xlim(0, 1.05)
        ax.set_xlabel("Module Coverage Fraction")
        ax.set_title("CS2023 Knowledge Area Coverage by Module Alignment")
        ax.axvline(x=0.1, color="#F44336", linestyle="--", alpha=0.5, label="Gap threshold (10%)")
        ax.legend(fontsize=8)
        for bar, val in zip(bars, cov_s):
            ax.text(
                val + 0.01, bar.get_y() + bar.get_height() / 2,
                f"{val:.0%}", va="center", ha="left", fontsize=8,
            )
        ax.grid(True, alpha=0.3, axis="x")
        fig.tight_layout()
        path = FIGURES_DIR / "ka_coverage_bar.png"
        fig.savefig(path, dpi=150)
        plt.close(fig)
        saved.append(path)

    # ── Figure 8: SBERT threshold sensitivity ────────────────────────────────
    sweep = results.get("threshold_sweep", {})
    if sweep:
        try:
            thresholds = sorted(sweep.keys())
            f1_key = next(k for k in next(iter(sweep.values())) if k.startswith("F1"))
            f1_vals = [sweep[t][f1_key] for t in thresholds]
            map_vals = [sweep[t]["MAP"] for t in thresholds]

            fig, ax = plt.subplots(figsize=(7, 4))
            ax.plot(thresholds, f1_vals, "o-", color="#FF5722", label=f1_key)
            ax.plot(thresholds, map_vals, "s--", color="#4CAF50", label="MAP")
            chosen = 0.75
            ax.axvline(x=chosen, color="#9C27B0", linestyle=":", alpha=0.8,
                       label=f"Chosen threshold ({chosen})")
            ax.set_xlabel("SBERT Partial-Credit Threshold")
            ax.set_ylabel("Score (macro average)")
            ax.set_title("Metric Sensitivity to SBERT Matching Threshold")
            ax.set_xticks(thresholds)
            ax.set_xticklabels([f"{t:.2f}" for t in thresholds])
            ax.set_ylim(0, max(max(f1_vals + map_vals) + 0.05, 0.3))
            ax.legend()
            ax.grid(True, alpha=0.3)
            fig.tight_layout()
            path = FIGURES_DIR / "threshold_sensitivity.png"
            fig.savefig(path, dpi=150)
            plt.close(fig)
            saved.append(path)
            logger.info(f"Saved figure: {path}")
        except Exception as e:
            logger.warning(f"Threshold sensitivity figure failed: {e}")

    # ── Figure 8b: Aligner weight sweep ──────────────────────────────────────
    wsweep = results.get("aligner_weight_sweep", {})
    if wsweep:
        try:
            ws = sorted(wsweep.keys(), key=float)
            sem_w = [float(w) for w in ws]
            top1 = [wsweep[w]["top1_accuracy"] for w in ws]
            top3 = [wsweep[w]["top3_accuracy"] for w in ws]
            mrr_vals = [wsweep[w]["mrr"] for w in ws]

            fig, ax = plt.subplots(figsize=(7, 4))
            ax.plot(sem_w, top1, "o-", color="#2196F3", label="Top-1 Accuracy")
            ax.plot(sem_w, top3, "s-", color="#FF5722", label="Top-3 Accuracy")
            ax.plot(sem_w, mrr_vals, "^--", color="#4CAF50", label="MRR")
            ax.axvline(x=0.65, color="#9C27B0", linestyle=":", alpha=0.8,
                       label="Production split (0.65)")
            ax.set_xlabel("Semantic weight (lexical weight = 1 − semantic)")
            ax.set_ylabel("Score")
            ax.set_title("Aligner Performance vs Lexical/Semantic Weight")
            ax.set_ylim(0, 1)
            ax.legend(fontsize=8)
            ax.grid(True, alpha=0.3)
            fig.tight_layout()
            path = FIGURES_DIR / "aligner_weight_sweep.png"
            fig.savefig(path, dpi=150)
            plt.close(fig)
            saved.append(path)
            logger.info(f"Saved figure: {path}")
        except Exception as e:
            logger.warning(f"Aligner weight sweep figure failed: {e}")

    # ── Figure 8d: LLM vs ensemble extraction ────────────────────────────────
    llm_comp = results.get("llm_model_comparison", {})
    if llm_comp:
        try:
            ens = results.get("extraction", {}).get("macro", {})
            rake = results.get("extraction_per_extractor", {}).get("rake", {}).get("macro", {})
            labels, f1s, maps = [], [], []
            for name in sorted(llm_comp.keys()):
                m = llm_comp[name].get("macro", {})
                labels.append(name.replace(":", "\n"))
                f1s.append(m.get("F1@10", 0))
                maps.append(m.get("MAP", 0))
            if rake:
                labels.append("RAKE\n(best 1)")
                f1s.append(rake.get("F1@10", 0))
                maps.append(rake.get("MAP", 0))
            if ens:
                labels.append("Ensemble\n(5)")
                f1s.append(ens.get("F1@10", 0))
                maps.append(ens.get("MAP", 0))

            x = range(len(labels))
            width = 0.38
            fig, ax = plt.subplots(figsize=(8, 4.5))
            ax.bar([xi - width / 2 for xi in x], f1s, width=width, label="F1@10", color="#2196F3")
            ax.bar([xi + width / 2 for xi in x], maps, width=width, label="MAP", color="#4CAF50")
            ax.set_xticks(list(x))
            ax.set_xticklabels(labels, fontsize=8)
            ax.set_ylabel("Score (macro average)")
            ax.set_title("Concept Extraction: Local-LLM Extractors vs Ensemble (gold set)")
            ax.legend()
            ax.grid(True, alpha=0.3, axis="y")
            fig.tight_layout()
            path = FIGURES_DIR / "llm_vs_ensemble.png"
            fig.savefig(path, dpi=150)
            plt.close(fig)
            saved.append(path)
            logger.info(f"Saved figure: {path}")
        except Exception as e:
            logger.warning(f"LLM comparison figure failed: {e}")

    # ── Figure 8c: Perturbation robustness ───────────────────────────────────
    perturb = results.get("perturbation", {})
    if perturb:
        try:
            fr = sorted(perturb.keys(), key=float)
            xpct = [float(f) * 100 for f in fr]
            base = perturb[fr[0]]

            def _pct(key):
                b = base[key] or 1
                return [100.0 * perturb[f][key] / b for f in fr]

            fig, ax = plt.subplots(figsize=(7, 4))
            ax.plot(xpct, _pct("mm_edges"), "o-", color="#2196F3", label="Module–module edges")
            ax.plot(xpct, _pct("covered_kas"), "s-", color="#4CAF50", label="Covered KAs")
            ax.plot(xpct, _pct("redundancy_count"), "^--", color="#FF5722", label="Redundancies")
            ax.plot(xpct, _pct("n_communities"), "d:", color="#9C27B0", label="Communities")
            ax.set_xlabel("Lowest-confidence concepts removed (%)")
            ax.set_ylabel("Retained, % of full-pipeline value")
            ax.set_title("Curriculum-Diagnostic Robustness to Concept Pruning")
            ax.set_ylim(0, 110)
            ax.axhline(100, color="#475569", linewidth=0.8, alpha=0.5)
            ax.legend(fontsize=8)
            ax.grid(True, alpha=0.3)
            fig.tight_layout()
            path = FIGURES_DIR / "perturbation_robustness.png"
            fig.savefig(path, dpi=150)
            plt.close(fig)
            saved.append(path)
            logger.info(f"Saved figure: {path}")
        except Exception as e:
            logger.warning(f"Perturbation robustness figure failed: {e}")

    # ── Figure 9: Module × KA heatmap ────────────────────────────────────────
    ka_heatmap_data = results.get("ka_heatmap", {})
    if ka_heatmap_data:
        try:
            import numpy as np
            module_codes = ka_heatmap_data.get("modules", [])
            ka_codes = ka_heatmap_data.get("kas", [])
            matrix = np.array(ka_heatmap_data.get("matrix", []))

            if matrix.size > 0:
                fig, ax = plt.subplots(figsize=(14, 7))
                im = ax.imshow(matrix, aspect="auto", cmap="Blues", vmin=0, vmax=1)
                ax.set_xticks(range(len(ka_codes)))
                ax.set_xticklabels(ka_codes, rotation=45, ha="right", fontsize=8)
                ax.set_yticks(range(len(module_codes)))
                ax.set_yticklabels(module_codes, fontsize=8)
                ax.set_xlabel("CS2023 Knowledge Area")
                ax.set_ylabel("Module")
                ax.set_title("Module × Knowledge Area Coverage Matrix")
                plt.colorbar(im, ax=ax, shrink=0.6, label="Covered (1) / Not covered (0)")
                fig.tight_layout()
                path = FIGURES_DIR / "ka_module_heatmap.png"
                fig.savefig(path, dpi=150)
                plt.close(fig)
                saved.append(path)
                logger.info(f"Saved figure: {path}")
        except Exception as e:
            logger.warning(f"KA heatmap generation failed: {e}")

    logger.info(f"Generated {len(saved)} figures in {FIGURES_DIR}")
    return saved
