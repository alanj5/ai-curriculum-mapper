#!/usr/bin/env python3
"""Run the NLP concept extraction pipeline.

Runs the full five-extractor ensemble (TF-IDF, RAKE, TextRank, KeyBERT,
BERTopic) with the concept-specificity filter and SBERT canonicalisation,
persisting the canonical concepts to the database and writing
``data/processed/concepts_inventory.json``.

Usage:
    python scripts/run_nlp_pipeline.py [--llm] [--no-specificity-filter] [--top-n N] [--verbose]
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from curriculum_mapper.config import PROCESSED_DIR

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)


def run_full_pipeline(
    top_n: int = 20, enable_llm: bool = False, specificity_filter: bool = True
) -> dict:
    """Run the full five-extractor pipeline + SBERT canonicalisation.

    With ``enable_llm`` a sixth local-LLM extractor is added (requires Ollama).
    ``specificity_filter=False`` disables the generic-term filter (for ablation).
    """
    from curriculum_mapper.nlp.pipeline import NLPPipeline
    pipeline = NLPPipeline(enable_llm=enable_llm, apply_specificity_filter=specificity_filter)
    return pipeline.run(top_n=top_n)


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the NLP concept extraction pipeline")
    parser.add_argument("--llm", action="store_true",
                        help="Add the optional local-LLM extractor (requires Ollama)")
    parser.add_argument("--no-specificity-filter", action="store_true",
                        help="Disable the generic-term specificity filter (for ablation)")
    parser.add_argument("--top-n", type=int, default=20, help="Top-N per extractor")
    parser.add_argument("--verbose", action="store_true")
    args = parser.parse_args()

    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)

    logger.info("Running the five-extractor pipeline + canonicalisation…")
    results = run_full_pipeline(
        top_n=args.top_n,
        enable_llm=args.llm,
        specificity_filter=not args.no_specificity_filter,
    )

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
