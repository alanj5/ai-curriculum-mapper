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

    # ── Aligner weight sweep ───────────────────────────────────────────────────

    def run_aligner_weight_sweep(
        self,
        semantic_weights: list[float] | None = None,
    ) -> dict[float, dict]:
        """Sweep the hybrid lexical/semantic weight on gold concept→KA pairs.

        For each semantic weight ``w`` (lexical weight = ``1 - w``) the hybrid
        score is recomputed per KA from the same underlying lexical and semantic
        component scores, then Top-1/Top-3/MRR are measured against the gold KA.
        ``w = 1.0`` is semantic-only; ``w = 0.0`` is lexical-only. This turns the
        fixed 35/65 split into an empirically justified choice.

        Returns {semantic_weight: {top1, top3, mrr}}.
        """
        from curriculum_mapper.alignment.aligner import load_ka_data
        from curriculum_mapper.alignment.lexical import LexicalAligner
        from curriculum_mapper.alignment.semantic import SemanticAligner
        from curriculum_mapper.config import SIMILARITY_THRESHOLD, TOP_K_ALIGNMENTS

        if semantic_weights is None:
            semantic_weights = [0.0, 0.25, 0.35, 0.5, 0.65, 0.75, 1.0]

        ka_data = load_ka_data()
        lex = LexicalAligner(ka_data)
        sem = SemanticAligner(ka_data, self.em)

        all_pairs: list[tuple[str, str]] = []
        for concept_ka_map in self.gold_with_ka.values():
            for term, ka in concept_ka_map.items():
                all_pairs.append((term, ka))
        if not all_pairs:
            logger.warning("No gold KA annotations found — update gold_concepts.json.")
            return {}

        # Pre-compute lexical and semantic component scores per (term, ka_code).
        # Each component is deduped to its best-scoring topic per KA (as hybrid does).
        def _best_per_ka(aligned: list[dict]) -> dict[str, float]:
            best: dict[str, float] = {}
            for r in aligned:
                code = r["ka_code"]
                if r["score"] > best.get(code, 0.0):
                    best[code] = r["score"]
            return best

        components: list[tuple[str, dict[str, float], dict[str, float]]] = []
        for term, gold_ka in all_pairs:
            lex_scores = _best_per_ka(lex.align(term))
            emb = self.em.encode([term])[0]
            sem_scores = _best_per_ka(sem.align(emb))
            components.append((gold_ka, lex_scores, sem_scores))

        results: dict[float, dict] = {}
        for w in semantic_weights:
            hits1 = hits3 = 0
            rrs: list[float] = []
            for gold_ka, lex_scores, sem_scores in components:
                combined: dict[str, float] = {}
                for code in sorted(set(lex_scores) | set(sem_scores)):
                    score = (1 - w) * lex_scores.get(code, 0.0) + w * sem_scores.get(code, 0.0)
                    if score >= SIMILARITY_THRESHOLD:
                        combined[code] = score
                # Deterministic ordering: by score desc, then KA code asc (ties).
                ranked = [c for c, _ in sorted(combined.items(), key=lambda kv: (-kv[1], kv[0]))]
                ranked = ranked[:TOP_K_ALIGNMENTS]
                if gold_ka in ranked[:1]:
                    hits1 += 1
                if gold_ka in ranked[:3]:
                    hits3 += 1
                rrs.append(1.0 / (ranked.index(gold_ka) + 1) if gold_ka in ranked else 0.0)
            total = len(components)
            results[w] = {
                "semantic_weight": w,
                "lexical_weight": round(1 - w, 2),
                "top1_accuracy": round(hits1 / total, 4),
                "top3_accuracy": round(hits3 / total, 4),
                "mrr": round(float(np.mean(rrs)), 4),
            }
            logger.info(
                f"  sem={w:.2f}/lex={1 - w:.2f}: Top-1={results[w]['top1_accuracy']:.4f}, "
                f"Top-3={results[w]['top3_accuracy']:.4f}, MRR={results[w]['mrr']:.4f}"
            )
        return results

    # ── Canonicalisation ablation ──────────────────────────────────────────────

    def run_canonicalisation_ablation(self, ks: list[int] | None = None) -> dict:
        """Compare extraction metrics with vs without SBERT canonicalisation.

        The DB currently holds canonicalised concepts (the production setting).
        The "raw" arm reconstructs the pre-canonicalisation candidate set by
        expanding each concept into its surface variants, giving an
        upper bound on the un-merged concept count and its effect on F1@K/MAP.
        Returns {"with_canonicalisation": {...}, "without_canonicalisation": {...}}.
        """
        if ks is None:
            ks = [5, 10, 20]

        concepts = self.storage.get_all_concepts()
        if not concepts:
            logger.error("No concepts in DB.")
            return {}

        # With canonicalisation: canonical terms only.
        mc_canon: dict[str, list[str]] = defaultdict(list)
        n_canon = 0
        for c in sorted(concepts, key=lambda x: -x.confidence):
            n_canon += 1
            for mc in c.module_codes:
                mc_canon[mc].append(c.term)

        # Without canonicalisation: canonical term + all variants (un-merged).
        mc_raw: dict[str, list[str]] = defaultdict(list)
        n_raw = 0
        for c in sorted(concepts, key=lambda x: -x.confidence):
            surface_forms = [c.term, *(c.variants or [])]
            n_raw += len(surface_forms)
            for mc in c.module_codes:
                mc_raw[mc].extend(surface_forms)

        with_canon = self._run_metrics_for_module_concepts(dict(mc_canon), ks)
        without_canon = self._run_metrics_for_module_concepts(dict(mc_raw), ks)
        with_canon["n_concepts"] = n_canon
        without_canon["n_concepts"] = n_raw
        logger.info(
            f"Canonicalisation ablation: with={n_canon} concepts "
            f"(F1@10={with_canon['macro'].get('F1@10', 0):.4f}), "
            f"without={n_raw} surface forms "
            f"(F1@10={without_canon['macro'].get('F1@10', 0):.4f})"
        )
        return {
            "with_canonicalisation": with_canon,
            "without_canonicalisation": without_canon,
        }

    # ── LLM-augmented extraction ───────────────────────────────────────────────

    def run_llm_extraction_benchmark(self, llm_extractor, ks: list[int] | None = None) -> dict:
        """Evaluate a local-LLM extractor on the gold modules (no DB writes).

        Runs the LLM extractor live on each gold module's text and scores its
        concepts against gold with the same partial-credit metrics as the
        ensemble (reusing ``_run_metrics_for_module_concepts``).
        """
        if ks is None:
            ks = [5, 10, 20]
        module_text = {
            m.code: (m.full_text_clean or m.full_text)
            for m in self.storage.get_all_modules()
        }
        mc: dict[str, list[str]] = {}
        for code in self.gold:
            terms = [t for t, _ in llm_extractor.extract(module_text.get(code, ""))]
            mc[code] = terms
        result = self._run_metrics_for_module_concepts(mc, ks)
        macro = result.get("macro", {})
        result["model"] = getattr(llm_extractor, "model", "llm")
        logger.info(
            f"  LLM extraction [{result['model']}]: F1@10={macro.get('F1@10', 0):.4f}, "
            f"MAP={macro.get('MAP', 0):.4f}"
        )
        return result

    def run_llm_model_comparison(
        self, models: list[str], ks: list[int] | None = None
    ) -> dict[str, dict]:
        """Compare several local-LLM models as extractors on the gold set.

        Returns {model_name: extraction-metrics}. Models whose Ollama server is
        unreachable are skipped (with a warning), so the call degrades gracefully.
        """
        from curriculum_mapper.nlp.extractors.llm_extractor import LLMExtractor

        out: dict[str, dict] = {}
        for name in models:
            ex = LLMExtractor(model=name)
            if not ex.is_available or not ex.ping():
                logger.warning(f"LLM model '{name}' unavailable (no Ollama server); skipping.")
                continue
            out[name] = self.run_llm_extraction_benchmark(ex, ks)
        return out

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

    # ── Baseline comparison (interim §4.2) ─────────────────────────────────────

    def run_baseline_comparison(
        self, ks: list[int] | None = None, top_n: int = 15
    ) -> dict:
        """Compare the production ensemble against simple baselines on the gold set.

        Baselines run on raw module text *without* the ensemble's specificity /
        noun-headed filters, so the comparison isolates the value the ensemble
        adds: (1) TF-IDF-only, (2) an unsupervised LDA topic model, (3) all noun
        phrases, (4) random tokens. Also reports the ensemble's *novelty* — the
        fraction of its concepts that no baseline produces (SBERT cosine < 0.85).
        Returns {method: extraction-metrics, ..., "novelty_vs_baselines": float}.
        """
        import random as _random
        from collections import Counter as _Counter

        from sklearn.decomposition import LatentDirichletAllocation
        from sklearn.feature_extraction.text import CountVectorizer

        from curriculum_mapper.nlp.extractors.tfidf_extractor import TFIDFExtractor
        from curriculum_mapper.nlp.preprocessor import Preprocessor

        if ks is None:
            ks = [5, 10, 20]

        modules = self.storage.get_all_modules()
        texts = {m.code: (m.full_text_clean or m.full_text) for m in modules}
        corpus_codes = [m.code for m in modules]
        corpus_texts = [texts[c] for c in corpus_codes]

        # (1) raw TF-IDF-only
        tf = TFIDFExtractor()
        tf.fit(corpus_texts)
        tfidf_mc = {c: [t for t, _ in tf.extract(texts[c], top_n=top_n)] for c in self.gold}

        # (2) LDA topic-word baseline (deterministic seed)
        cv = CountVectorizer(
            stop_words="english", ngram_range=(1, 2), min_df=2, max_df=0.85,
            token_pattern=r"(?u)\b[a-zA-Z][a-zA-Z\-]{2,}\b",
        )
        dtm = cv.fit_transform(corpus_texts)
        n_topics = min(10, max(2, len(corpus_texts) // 3))
        lda = LatentDirichletAllocation(n_components=n_topics, random_state=42, max_iter=20)
        doc_topic = lda.fit_transform(dtm)
        vocab = cv.get_feature_names_out()
        topic_words = [[vocab[i] for i in t.argsort()[::-1][:top_n]] for t in lda.components_]
        lda_mc = {
            corpus_codes[ci]: topic_words[int(doc_topic[ci].argmax())]
            for ci in range(len(corpus_codes))
            if corpus_codes[ci] in self.gold
        }

        # (3) all noun phrases (frequency-ranked)
        pre = Preprocessor()
        np_mc: dict[str, list[str]] = {}
        for c in self.gold:
            doc = pre._nlp(texts.get(c, ""))
            chunks = [ch.text.lower().strip() for ch in doc.noun_chunks
                      if 1 <= len(ch.text.split()) <= 4]
            np_mc[c] = [t for t, _ in _Counter(chunks).most_common(top_n)]

        # (4) random tokens (seeded)
        rnd = _random.Random(42)
        rand_mc: dict[str, list[str]] = {}
        for c in self.gold:
            toks = sorted({w.lower() for w in texts.get(c, "").split() if len(w) > 3})
            rnd.shuffle(toks)
            rand_mc[c] = toks[:top_n]

        baselines = {"tfidf_only": tfidf_mc, "lda": lda_mc,
                     "noun_phrases": np_mc, "random": rand_mc}
        out: dict[str, object] = {}
        for name, mc in baselines.items():
            metrics = self._run_metrics_for_module_concepts(mc, ks)
            out[name] = metrics
            macro = metrics["macro"]
            logger.info(f"  baseline {name:12s}: F1@10={macro.get('F1@10', 0):.4f}, "
                        f"MAP={macro.get('MAP', 0):.4f}")

        # ensemble (from DB) for the same gold modules
        concepts = self.storage.get_all_concepts()
        ens_mc: dict[str, list[str]] = defaultdict(list)
        for con in sorted(concepts, key=lambda x: -x.confidence):
            for mod in con.module_codes:
                ens_mc[mod].append(con.term)
        ens_metrics = self._run_metrics_for_module_concepts(dict(ens_mc), ks)
        out["ensemble"] = ens_metrics
        logger.info(f"  {'ensemble':21s}: F1@10={ens_metrics['macro'].get('F1@10', 0):.4f}, "
                    f"MAP={ens_metrics['macro'].get('MAP', 0):.4f}")

        # novelty: ensemble concepts (on gold modules) unmatched by any baseline term
        baseline_terms = {t.lower() for mc in baselines.values()
                          for c in self.gold for t in mc.get(c, [])}
        ens_terms = list(dict.fromkeys(t for c in self.gold for t in ens_mc.get(c, [])))
        novelty = 0.0
        if ens_terms and baseline_terms:
            base_embs = self.em.encode(list(baseline_terms))
            ens_embs = self.em.encode(ens_terms)
            novel = sum(1 for e in ens_embs if float(np.max(e @ base_embs.T)) < 0.85)
            novelty = round(novel / len(ens_terms), 4)
        out["novelty_vs_baselines"] = novelty
        logger.info(f"  ensemble novelty vs baselines: {novelty:.4f}")
        return out

    # ── Extraction error analysis (interim §4.3.1) ─────────────────────────────

    def run_error_analysis(self, threshold: float = 0.75, k: int = 10) -> dict:
        """Categorise extraction errors against gold to localise the bottleneck.

        Each gold concept is HIT if any extracted concept for its module is within
        ``threshold`` cosine, else a MISS; misses are split by length (single- vs
        multi-word) and by whether the term occurs verbatim in the module text
        (present-but-unextracted → a filter/ranking miss; absent → not in the
        descriptor). Top-``k`` predictions that match no gold concept are counted
        as false positives. Returns category counts and rates.
        """
        from curriculum_mapper.evaluation.metrics import _is_hit

        concepts = self.storage.get_all_concepts()
        if not concepts:
            return {}
        module_concepts: dict[str, list[str]] = defaultdict(list)
        for c in sorted(concepts, key=lambda x: -x.confidence):
            for mc in c.module_codes:
                module_concepts[mc].append(c.term)
        # Check misses against the FULL descriptor (description + ILOs + syllabus
        # topics) so "present in text" reflects whether the concept is anywhere in
        # the source the annotator read — not just the description+ILOs the
        # pipeline currently consumes.
        mod_text = {m.code: m.full_text.lower()
                    for m in self.storage.get_all_modules()}

        n_gold = n_hit = 0
        miss_single = miss_multi = miss_in_text = miss_absent = 0
        n_pred_topk = fp_topk = 0

        for code, gold_terms in self.gold.items():
            if not gold_terms:
                continue
            predicted = module_concepts.get(code, [])
            pred_embs = self.em.encode(predicted) if predicted else None
            gold_embs = self.em.encode(gold_terms)
            text = mod_text.get(code, "")

            for gi, g in enumerate(gold_terms):
                n_gold += 1
                if pred_embs is not None and _is_hit(gold_embs[gi], pred_embs, threshold):
                    n_hit += 1
                else:
                    if len(g.split()) == 1:
                        miss_single += 1
                    else:
                        miss_multi += 1
                    if g.lower() in text:
                        miss_in_text += 1
                    else:
                        miss_absent += 1

            # false positives among the top-k predictions
            topk = predicted[:k]
            if topk and gold_embs is not None:
                topk_embs = self.em.encode(topk)
                for pe in topk_embs:
                    n_pred_topk += 1
                    if not _is_hit(pe, gold_embs, threshold):
                        fp_topk += 1

        n_miss = n_gold - n_hit
        out = {
            "n_gold": n_gold,
            "n_hit": n_hit,
            "n_miss": n_miss,
            "miss_rate": round(n_miss / n_gold, 4) if n_gold else 0.0,
            "miss_single_word": miss_single,
            "miss_multi_word": miss_multi,
            "miss_present_in_text": miss_in_text,
            "miss_absent_from_text": miss_absent,
            "n_pred_topk": n_pred_topk,
            "false_positive_topk": fp_topk,
            "fp_rate_topk": round(fp_topk / n_pred_topk, 4) if n_pred_topk else 0.0,
        }
        logger.info(
            f"Error analysis: {n_miss}/{n_gold} gold missed ({out['miss_rate']:.0%}); "
            f"of misses {miss_in_text} present-in-text vs {miss_absent} absent; "
            f"top-{k} FP rate {out['fp_rate_topk']:.0%}"
        )
        return out

    # ── Per-KA alignment accuracy (interim §4.3.2) ─────────────────────────────

    def run_per_ka_alignment(self) -> dict[str, dict]:
        """Top-1 alignment accuracy broken down by gold Knowledge Area.

        Uses the semantic aligner (best in the aligner comparison) on each gold
        concept and records whether its top KA matches the gold KA, grouped by
        KA — surfacing which Knowledge Areas the aligner handles best/worst.
        """
        from curriculum_mapper.alignment.aligner import load_ka_data
        from curriculum_mapper.alignment.semantic import SemanticAligner

        sem = SemanticAligner(load_ka_data(), self.em)
        by_ka: dict[str, dict[str, int]] = defaultdict(lambda: {"n": 0, "hit1": 0})
        for concept_ka_map in self.gold_with_ka.values():
            for term, gold_ka in concept_ka_map.items():
                emb = self.em.encode([term])[0]
                ka_list: list[str] = []
                seen: set[str] = set()
                for r in sem.align(emb):
                    if r["ka_code"] not in seen:
                        seen.add(r["ka_code"])
                        ka_list.append(r["ka_code"])
                by_ka[gold_ka]["n"] += 1
                if ka_list and ka_list[0] == gold_ka:
                    by_ka[gold_ka]["hit1"] += 1
        out = {
            ka: {"n": v["n"], "top1_accuracy": round(v["hit1"] / v["n"], 4)}
            for ka, v in sorted(by_ka.items())
        }
        for ka, v in out.items():
            logger.info(f"  KA {ka:4s}: n={v['n']:3d}  Top-1={v['top1_accuracy']:.3f}")
        return out

    # ── Ambiguity-margin sweep (justifies δ) ───────────────────────────────────

    def run_ambiguity_margin_sweep(self, margins: list[float] | None = None) -> dict:
        """Ambiguous rank-1 alignments as a function of the margin δ.

        A rank-1 alignment is flagged ambiguous when its score and the rank-2
        score differ by less than δ. Sweeping δ shows how the chosen δ trades the
        number of human-review flags against confidence — turning the fixed 0.08
        into a justified operating point. Computed from stored alignment scores.
        """
        if margins is None:
            margins = [0.02, 0.04, 0.06, 0.08, 0.10, 0.15, 0.20]

        by_concept: dict[str, dict[int, float]] = defaultdict(dict)
        for a in self.storage.get_all_alignments():
            by_concept[a.concept_id][a.rank] = a.score

        n_rank1 = 0
        gaps: list[float] = []
        for ranks in by_concept.values():
            if 1 in ranks:
                n_rank1 += 1
                if 2 in ranks:
                    gaps.append(ranks[1] - ranks[2])

        out: dict[float, dict] = {}
        for m in margins:
            n_amb = sum(1 for g in gaps if g < m)
            out[m] = {
                "margin": m,
                "ambiguous_count": n_amb,
                "ambiguous_fraction": round(n_amb / n_rank1, 4) if n_rank1 else 0.0,
            }
            logger.info(f"  δ={m:.2f}: {n_amb}/{n_rank1} rank-1 ambiguous "
                        f"({out[m]['ambiguous_fraction']:.1%})")
        return out

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
