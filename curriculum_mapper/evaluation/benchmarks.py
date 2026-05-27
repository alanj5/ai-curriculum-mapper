"""Benchmark runner for concept extraction and alignment evaluation.

Runs against gold-annotated modules to produce P@K, R@K, F1@K, MRR, and MAP
for both concept extraction and KA alignment tasks.

Gold data format (data/annotations/gold_concepts.json):
  {module_code: {"module_title": ..., "concepts": [{"term": ..., "ka": ...}, ...]}, ...}
"""

from __future__ import annotations

import json
import logging
from collections import defaultdict
from pathlib import Path

import numpy as np

from curriculum_mapper.config import ANNOTATIONS_DIR
from curriculum_mapper.evaluation.metrics import (
    average_precision,
    f1_at_k,
    precision_at_k,
    recall_at_k,
)
from curriculum_mapper.ingestion.storage import StorageManager
from curriculum_mapper.nlp.embeddings import EmbeddingManager

logger = logging.getLogger(__name__)

GOLD_PATH = ANNOTATIONS_DIR / "gold_concepts.json"


def load_gold(path: Path = GOLD_PATH) -> dict[str, list[str]]:
    """Load gold concept annotations. Returns {module_code: [term, ...]}."""
    with open(path) as f:
        raw = json.load(f)
    result: dict[str, list[str]] = {}
    for code, data in raw.items():
        if code == "_metadata":
            continue
        concepts = data["concepts"]
        if concepts and isinstance(concepts[0], dict):
            result[code] = [c["term"] for c in concepts]
        else:
            result[code] = list(concepts)
    return result


def load_gold_with_ka(path: Path = GOLD_PATH) -> dict[str, dict[str, str]]:
    """Load gold annotations with KA codes. Returns {module_code: {term: ka_code}}."""
    with open(path) as f:
        raw = json.load(f)
    result: dict[str, dict[str, str]] = {}
    for code, data in raw.items():
        if code == "_metadata":
            continue
        concepts = data["concepts"]
        if concepts and isinstance(concepts[0], dict):
            result[code] = {c["term"]: c["ka"] for c in concepts if "ka" in c}
    return result


class BenchmarkRunner:
    """Runs evaluation benchmarks against gold-annotated data."""

    def __init__(
        self,
        storage: StorageManager,
        em: EmbeddingManager,
        gold_path: Path = GOLD_PATH,
    ) -> None:
        self.storage = storage
        self.em = em
        self.gold = load_gold(gold_path)
        self.gold_with_ka = load_gold_with_ka(gold_path)
        logger.info(f"Loaded gold annotations for {len(self.gold)} modules.")

    # ── Shared helper ──────────────────────────────────────────────────────────

    def _run_metrics_for_module_concepts(
        self,
        module_concepts: dict[str, list[str]],
        ks: list[int],
    ) -> dict:
        """Compute P@K/R@K/F1@K/MAP for a given per-module concept ranking."""
        results: dict[str, dict] = {}
        all_aps: list[float] = []

        for module_code, gold_terms in self.gold.items():
            predicted = module_concepts.get(module_code, [])
            module_results: dict[str, float] = {}

            for k in ks:
                module_results[f"P@{k}"] = precision_at_k(predicted, gold_terms, k, self.em)
                module_results[f"R@{k}"] = recall_at_k(predicted, gold_terms, k, self.em)
                module_results[f"F1@{k}"] = f1_at_k(predicted, gold_terms, k, self.em)

            ap = average_precision(predicted, gold_terms, self.em)
            module_results["AP"] = ap
            all_aps.append(ap)
            module_results["n_predicted"] = len(predicted)
            module_results["n_gold"] = len(gold_terms)
            results[module_code] = module_results

        macro: dict[str, float] = {}
        if results:
            for k in ks:
                macro[f"P@{k}"] = round(np.mean([r[f"P@{k}"] for r in results.values()]), 4)
                macro[f"R@{k}"] = round(np.mean([r[f"R@{k}"] for r in results.values()]), 4)
                macro[f"F1@{k}"] = round(np.mean([r[f"F1@{k}"] for r in results.values()]), 4)
            macro["MAP"] = round(float(np.mean(all_aps)), 4)

        return {"per_module": results, "macro": macro}

    # ── Ensemble extraction benchmark ──────────────────────────────────────────

    def run_extraction_benchmark(self, ks: list[int] | None = None) -> dict:
        """Evaluate concept extraction (ensemble) against gold. Returns metrics dict."""
        if ks is None:
            ks = [5, 10, 20]

        concepts = self.storage.get_all_concepts()
        if not concepts:
            logger.error("No concepts in DB — run NLP pipeline first.")
            return {}

        module_concepts: dict[str, list[str]] = defaultdict(list)
        for c in sorted(concepts, key=lambda x: -x.confidence):
            for mc in c.module_codes:
                module_concepts[mc].append(c.term)

        result = self._run_metrics_for_module_concepts(dict(module_concepts), ks)
        macro = result.get("macro", {})
        logger.info(
            f"Extraction benchmark (ensemble): P@10={macro.get('P@10', 0):.4f}, "
            f"F1@10={macro.get('F1@10', 0):.4f}, MAP={macro.get('MAP', 0):.4f}"
        )
        return result

    # ── Per-extractor extraction benchmark ────────────────────────────────────

    def run_extraction_benchmark_per_extractor(
        self, ks: list[int] | None = None
    ) -> dict[str, dict]:
        """Evaluate each extractor individually + ensemble.

        For each extractor, filters the concept set to concepts found by that
        extractor (sorted by overall confidence) and computes P@K, R@K, F1@K, MAP.
        Returns {extractor_name: {macro: {...}, per_module: {...}}, "ensemble": {...}}.
        """
        if ks is None:
            ks = [5, 10, 20]

        concepts = self.storage.get_all_concepts()
        if not concepts:
            logger.error("No concepts in DB.")
            return {}

        extractor_names = ["tfidf", "rake", "textrank", "keybert", "bertopic"]
        results: dict[str, dict] = {}

        for extractor in extractor_names:
            mc: dict[str, list[str]] = defaultdict(list)
            for c in sorted(concepts, key=lambda x: -x.confidence):
                if extractor in c.extractors:
                    for mod in c.module_codes:
                        mc[mod].append(c.term)
            results[extractor] = self._run_metrics_for_module_concepts(dict(mc), ks)
            macro = results[extractor].get("macro", {})
            logger.info(
                f"  {extractor:10s}: F1@10={macro.get('F1@10', 0):.4f}, MAP={macro.get('MAP', 0):.4f}"
            )

        # Ensemble (all concepts)
        mc_all: dict[str, list[str]] = defaultdict(list)
        for c in sorted(concepts, key=lambda x: -x.confidence):
            for mod in c.module_codes:
                mc_all[mod].append(c.term)
        results["ensemble"] = self._run_metrics_for_module_concepts(dict(mc_all), ks)
        macro = results["ensemble"].get("macro", {})
        logger.info(
            f"  {'ensemble':10s}: F1@10={macro.get('F1@10', 0):.4f}, MAP={macro.get('MAP', 0):.4f}"
        )

        return results

    # ── Alignment benchmark ────────────────────────────────────────────────────

    def run_alignment_benchmark(self, ks: list[int] | None = None) -> dict:
        """Evaluate KA alignment using gold concept→KA annotations.

        For each gold concept, find the closest extracted concept via SBERT,
        then check if that concept's predicted KA list contains the gold KA.
        If KA codes are present in gold data, computes Top-K accuracy and MRR;
        otherwise falls back to coverage (does the concept have any alignment?).
        """
        if ks is None:
            ks = [1, 3]

        alignments = self.storage.get_all_alignments()
        concepts = self.storage.get_all_concepts()

        if not alignments or not concepts:
            logger.warning("No alignments in DB — run alignment pipeline first.")
            return {}

        concept_id_to_term = {c.id: c.term for c in concepts}

        # concept_id → sorted list of ka_codes by rank
        concept_ka_ranked: dict[str, list[str]] = defaultdict(list)
        for a in sorted(alignments, key=lambda x: (x.concept_id, x.rank)):
            concept_ka_ranked[a.concept_id].append(a.ka_code)

        results: dict[str, dict] = {}
        has_ka_labels = bool(self.gold_with_ka)

        # Use gold_with_ka if KA codes are available, else fall back to plain gold terms
        gold_source: dict[str, tuple[list[str], list[str] | None]] = {}
        if has_ka_labels:
            for mod, concept_ka_map in self.gold_with_ka.items():
                gold_source[mod] = (list(concept_ka_map.keys()), list(concept_ka_map.values()))
        else:
            for mod, terms in self.gold.items():
                gold_source[mod] = (terms, None)

        for module_code, (gold_terms, gold_kas) in gold_source.items():
            total_gold = len(gold_terms)
            if not total_gold:
                continue

            module_concept_ids = [c.id for c in concepts if module_code in c.module_codes]
            if not module_concept_ids:
                results[module_code] = {f"alignment_coverage@{k}": 0.0 for k in ks}
                results[module_code]["n_gold"] = total_gold
                results[module_code]["gold_matched_fraction"] = 0.0
                results[module_code]["mrr"] = 0.0
                continue

            gold_embs = self.em.encode(gold_terms)
            mc_terms = [concept_id_to_term[cid] for cid in module_concept_ids]
            mc_embs = self.em.encode(mc_terms)
            sims = gold_embs @ mc_embs.T  # (G, M)

            covered_at_k: dict[int, int] = {k: 0 for k in ks}
            matched = 0
            rrs: list[float] = []

            for g_idx, gold_term in enumerate(gold_terms):
                gold_ka = gold_kas[g_idx] if gold_kas else None
                best_mc_idx = int(np.argmax(sims[g_idx]))
                best_sim = float(sims[g_idx, best_mc_idx])

                if best_sim >= 0.75:
                    matched += 1
                    best_cid = module_concept_ids[best_mc_idx]
                    ka_list = concept_ka_ranked.get(best_cid, [])

                    for k in ks:
                        if gold_ka is not None:
                            # KA accuracy: correct KA in top-k predictions
                            if gold_ka in ka_list[:k]:
                                covered_at_k[k] += 1
                        else:
                            # Fallback: concept has any alignment in top-k
                            if len(ka_list[:k]) > 0:
                                covered_at_k[k] += 1

                    if gold_ka is not None and gold_ka in ka_list:
                        rrs.append(1.0 / (ka_list.index(gold_ka) + 1))
                    else:
                        rrs.append(0.0)
                else:
                    rrs.append(0.0)

            module_results: dict[str, float] = {
                f"alignment_coverage@{k}": round(covered_at_k[k] / total_gold, 4)
                for k in ks
            }
            module_results["gold_matched_fraction"] = round(matched / total_gold, 4)
            module_results["mrr"] = round(float(np.mean(rrs)), 4) if rrs else 0.0
            module_results["n_gold"] = total_gold
            results[module_code] = module_results

        macro: dict[str, float] = {}
        if results:
            for k in ks:
                key = f"alignment_coverage@{k}"
                vals = [r[key] for r in results.values() if key in r]
                macro[key] = round(float(np.mean(vals)), 4) if vals else 0.0
            match_vals = [r["gold_matched_fraction"] for r in results.values()]
            macro["mean_gold_match"] = round(float(np.mean(match_vals)), 4)
            mrr_vals = [r.get("mrr", 0.0) for r in results.values()]
            macro["mrr"] = round(float(np.mean(mrr_vals)), 4)

        logger.info(
            f"Alignment benchmark: coverage@1={macro.get('alignment_coverage@1', 0):.4f}, "
            f"coverage@3={macro.get('alignment_coverage@3', 0):.4f}, "
            f"MRR={macro.get('mrr', 0):.4f}"
        )
        return {"per_module": results, "macro": macro}

    # ── Aligner comparison ─────────────────────────────────────────────────────

    def run_aligner_comparison(self) -> dict[str, dict]:
        """Compare lexical, semantic, and hybrid aligners on gold concept→KA pairs.

        Directly aligns each gold concept string against CS2023 KAs using each
        aligner variant. Returns Top-1 accuracy, Top-3 accuracy, and MRR.
        """
        from curriculum_mapper.alignment.aligner import load_ka_data
        from curriculum_mapper.alignment.hybrid import HybridAligner
        from curriculum_mapper.alignment.lexical import LexicalAligner
        from curriculum_mapper.alignment.semantic import SemanticAligner
        from curriculum_mapper.ingestion.schema import Concept

        ka_data = load_ka_data()
        lex = LexicalAligner(ka_data)
        sem = SemanticAligner(ka_data, self.em)
        hyb = HybridAligner(ka_data, self.em)

        # Collect all (term, gold_ka) pairs across all annotated modules
        all_pairs: list[tuple[str, str]] = []
        for concept_ka_map in self.gold_with_ka.values():
            for term, ka in concept_ka_map.items():
                all_pairs.append((term, ka))

        if not all_pairs:
            logger.warning("No gold KA annotations found — update gold_concepts.json.")
            return {}

        results: dict[str, dict] = {}

        for aligner_name in ["lexical", "semantic", "hybrid"]:
            hits1 = hits3 = 0
            rrs: list[float] = []

            for term, gold_ka in all_pairs:
                if aligner_name == "lexical":
                    aligned = lex.align(term)
                    ka_list = [r["ka_code"] for r in aligned]
                elif aligner_name == "semantic":
                    emb = self.em.encode([term])[0]
                    aligned = sem.align(emb)
                    # Dedup by KA
                    seen: set[str] = set()
                    ka_list = []
                    for r in aligned:
                        if r["ka_code"] not in seen:
                            seen.add(r["ka_code"])
                            ka_list.append(r["ka_code"])
                else:
                    # Hybrid via a dummy Concept object
                    dummy = Concept(
                        term=term,
                        confidence=1.0,
                        extractors=["tfidf"],
                        module_codes=[],
                    )
                    aligned_results = hyb.align(dummy)
                    ka_list = [r.ka_code for r in aligned_results]

                if gold_ka in ka_list[:1]:
                    hits1 += 1
                if gold_ka in ka_list[:3]:
                    hits3 += 1

                if gold_ka in ka_list:
                    rrs.append(1.0 / (ka_list.index(gold_ka) + 1))
                else:
                    rrs.append(0.0)

            total = len(all_pairs)
            results[aligner_name] = {
                "top1_accuracy": round(hits1 / total, 4),
                "top3_accuracy": round(hits3 / total, 4),
                "mrr": round(float(np.mean(rrs)), 4),
                "total_evaluated": total,
            }
            logger.info(
                f"  {aligner_name:8s}: Top-1={results[aligner_name]['top1_accuracy']:.4f}, "
                f"Top-3={results[aligner_name]['top3_accuracy']:.4f}, "
                f"MRR={results[aligner_name]['mrr']:.4f}"
            )

        return results

    # ── Full run ───────────────────────────────────────────────────────────────

    # ── SBERT threshold sensitivity sweep ─────────────────────────────────────

    def run_threshold_sweep(
        self,
        thresholds: list[float] | None = None,
        k: int = 10,
    ) -> dict[float, dict]:
        """Run extraction benchmark at multiple SBERT partial-credit thresholds.

        Shows sensitivity of F1@K and MAP to the threshold choice, confirming
        the selected threshold (0.75) is not cherry-picked.
        Returns {threshold: {"F1@K": ..., "MAP": ...}}.
        """
        if thresholds is None:
            thresholds = [0.60, 0.65, 0.70, 0.75, 0.80, 0.85]

        concepts = self.storage.get_all_concepts()
        if not concepts:
            return {}

        # Build per-module ranked concept lists once
        module_concepts: dict[str, list[str]] = defaultdict(list)
        for c in sorted(concepts, key=lambda x: -x.confidence):
            for mc in c.module_codes:
                module_concepts[mc].append(c.term)

        results: dict[float, dict] = {}
        for t in thresholds:
            f1_vals, map_vals = [], []
            for module_code, gold_terms in self.gold.items():
                predicted = module_concepts.get(module_code, [])
                f1_vals.append(f1_at_k(predicted, gold_terms, k, self.em, threshold=t))
                map_vals.append(average_precision(predicted, gold_terms, self.em, threshold=t))
            results[t] = {
                f"F1@{k}": round(float(np.mean(f1_vals)), 4),
                "MAP": round(float(np.mean(map_vals)), 4),
            }
            logger.info(f"  threshold={t:.2f}: F1@{k}={results[t][f'F1@{k}']:.4f}, MAP={results[t]['MAP']:.4f}")

        return results

    def run_all(self, ks: list[int] | None = None) -> dict:
        """Run all benchmarks and return combined results."""
        logger.info("Running extraction benchmark (ensemble)…")
        extraction = self.run_extraction_benchmark(ks)
        logger.info("Running alignment benchmark…")
        alignment = self.run_alignment_benchmark()
        return {
            "extraction": extraction,
            "alignment": alignment,
        }

    def run_all_extended(self, ks: list[int] | None = None) -> dict:
        """Run all benchmarks including per-extractor and aligner comparisons."""
        logger.info("Running extraction benchmark (ensemble)…")
        extraction = self.run_extraction_benchmark(ks)

        logger.info("Running per-extractor extraction benchmarks…")
        extraction_per_extractor = self.run_extraction_benchmark_per_extractor(ks)

        logger.info("Running alignment benchmark…")
        alignment = self.run_alignment_benchmark()

        logger.info("Running aligner comparison…")
        aligner_comparison = self.run_aligner_comparison()

        return {
            "extraction": extraction,
            "extraction_per_extractor": extraction_per_extractor,
            "alignment": alignment,
            "aligner_comparison": aligner_comparison,
            # threshold_sweep added separately by run_evaluation.py
        }
