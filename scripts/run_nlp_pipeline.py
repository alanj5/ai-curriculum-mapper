#!/usr/bin/env python3
"""Run the NLP concept extraction pipeline.

Default (--week2): full five-extractor pipeline with SBERT canonicalization.
  Produces data/processed/concepts_inventory.json

Baseline (no flag): Week-1 extractors only (TF-IDF, RAKE, TextRank) with no
  canonicalization. Useful for comparison.

Usage:
    python scripts/run_nlp_pipeline.py [--week2] [--top-n N] [--verbose]
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from curriculum_mapper.config import PROCESSED_DIR
from curriculum_mapper.ingestion.storage import StorageManager
from curriculum_mapper.nlp.extractors.rake_extractor import RAKEExtractor
from curriculum_mapper.nlp.extractors.textrank_extractor import TextRankExtractor
from curriculum_mapper.nlp.extractors.tfidf_extractor import TFIDFExtractor

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)


def normalise_score(scores: list[float]) -> list[float]:
    """Min-max normalise a list of scores to [0, 1]."""
    if not scores:
        return scores
    min_s, max_s = min(scores), max(scores)
    if max_s == min_s:
        return [1.0 for _ in scores]
    return [(s - min_s) / (max_s - min_s) for s in scores]


def run_pipeline(top_n: int = 20) -> dict:
    storage = StorageManager()
    modules = storage.get_all_modules()
    if not modules:
        logger.error("No modules in DB. Run scripts/ingest_modules.py first.")
        sys.exit(1)
    logger.info(f"Running NLP pipeline on {len(modules)} modules...")

    # Full text per module (description + ILOs + topics)
    texts = [m.full_text_clean or m.full_text for m in modules]

    # ── Corpus-level: TF-IDF ──────────────────────────────────────────────────
    logger.info("Fitting TF-IDF on corpus...")
    tfidf = TFIDFExtractor()
    tfidf.fit(texts)

    # ── Instance-level extractors ─────────────────────────────────────────────
    rake = RAKEExtractor()
    textrank = TextRankExtractor()
    logger.info(f"TextRank available: {textrank.is_available}")

    # ── Per-module extraction ─────────────────────────────────────────────────
    results: dict[str, dict] = {}

    for module, text in zip(modules, texts):
        logger.info(f"Processing {module.code}: {module.title}")

        tfidf_raw = tfidf.extract(text, top_n=top_n)
        rake_raw = rake.extract(text, top_n=top_n)
        textrank_raw = textrank.extract(text, top_n=top_n)

        # Normalise RAKE scores (raw degree ratios can be large)
        if rake_raw:
            rake_scores = normalise_score([s for _, s in rake_raw])
            rake_raw = [(t, s) for (t, _), s in zip(rake_raw, rake_scores)]

        # Merge all candidates into a unified dict: term -> {extractor: score}
        candidates: dict[str, dict[str, float]] = defaultdict(dict)
        for term, score in tfidf_raw:
            candidates[term]["tfidf"] = score
        for term, score in rake_raw:
            candidates[term.lower()]["rake"] = score
        for term, score in textrank_raw:
            candidates[term.lower()]["textrank"] = score

        # Compute aggregate confidence (simple average of available extractor scores)
        WEIGHTS = {"tfidf": 0.30, "rake": 0.30, "textrank": 0.40}
        concept_list = []
        for term, extractor_scores in candidates.items():
            if len(term) < 3:
                continue
            weighted_sum = sum(
                WEIGHTS.get(ext, 0.25) * score
                for ext, score in extractor_scores.items()
            )
            weight_total = sum(
                WEIGHTS.get(ext, 0.25)
                for ext in extractor_scores
            )
            confidence = weighted_sum / weight_total if weight_total > 0 else 0.0
            concept_list.append({
                "term": term,
                "confidence": round(confidence, 4),
                "extractors": list(extractor_scores.keys()),
                "scores": {k: round(v, 4) for k, v in extractor_scores.items()},
            })

        # Sort by confidence descending
        concept_list.sort(key=lambda x: -x["confidence"])

        results[module.code] = {
            "title": module.title,
            "level": module.level,
            "concept_count": len(concept_list),
            "concepts": concept_list[:50],  # cap at 50 per module
        }

    return results


def run_week2_pipeline(
    top_n: int = 20, enable_llm: bool = False, specificity_filter: bool = True
) -> dict:
    """Full Week-2 pipeline: 5 extractors + SBERT canonicalization.

    With ``enable_llm`` a sixth local-LLM extractor is added (requires Ollama).
    ``specificity_filter=False`` disables the generic-term filter (for ablation).
    """
    from curriculum_mapper.nlp.pipeline import NLPPipeline
    pipeline = NLPPipeline(enable_llm=enable_llm, apply_specificity_filter=specificity_filter)
    return pipeline.run(top_n=top_n)


def main() -> None:
    parser = argparse.ArgumentParser(description="Run NLP concept extraction pipeline")
    parser.add_argument("--week2", action="store_true",
                        help="Use full Week-2 pipeline (KeyBERT+BERTopic+canonicalization)")
    parser.add_argument("--llm", action="store_true",
                        help="Add the optional local-LLM extractor (requires Ollama)")
    parser.add_argument("--no-specificity-filter", action="store_true",
                        help="Disable the generic-term specificity filter (for ablation)")
    parser.add_argument("--top-n", type=int, default=20, help="Top-N per extractor")
    parser.add_argument("--verbose", action="store_true")
    args = parser.parse_args()

    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)

    if args.week2:
        logger.info("Running Week-2 pipeline (all 5 extractors + canonicalization)…")
        results = run_week2_pipeline(
            top_n=args.top_n, enable_llm=args.llm,
            specificity_filter=not args.no_specificity_filter,
        )
    else:
        logger.info("Running Week-1 baseline pipeline (TF-IDF + RAKE + TextRank)…")
        results = run_pipeline(top_n=args.top_n)

    # ── Save output ───────────────────────────────────────────────────────────
    output_path = PROCESSED_DIR / "concepts_inventory.json"
    with open(output_path, "w") as f:
        json.dump(results, f, indent=2)
    logger.info(f"Saved concept inventory to {output_path}")

    # ── Print summary ─────────────────────────────────────────────────────────
    total_concepts = sum(v["concept_count"] for v in results.values())
    logger.info(f"\n{'='*60}")
    logger.info("PIPELINE SUMMARY")
    logger.info(f"{'='*60}")
    logger.info(f"Modules processed: {len(results)}")
    logger.info(f"Total concept candidates: {total_concepts}")
    logger.info(f"Average per module: {total_concepts / max(len(results), 1):.1f}")
    logger.info("\nTop concepts per module:")
    for code, data in list(results.items())[:5]:
        top5 = [c["term"] for c in data["concepts"][:5]]
        logger.info(f"  {code}: {', '.join(top5)}")


if __name__ == "__main__":
    main()
