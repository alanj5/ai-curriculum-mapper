#!/usr/bin/env python3
"""Run the hybrid alignment pipeline over all extracted concepts.

Aligns every concept in the DB to ACM/IEEE CS2023 Knowledge Areas using
a hybrid 35% lexical + 65% semantic (SBERT) approach.

Usage:
    python scripts/run_alignment.py [--verbose]

Prerequisites:
    python scripts/ingest_modules.py
    python scripts/run_nlp_pipeline.py
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from curriculum_mapper.alignment.aligner import run_alignment
from curriculum_mapper.config import PROCESSED_DIR, STANDARDS_DIR
from curriculum_mapper.ingestion.storage import StorageManager
from curriculum_mapper.nlp.embeddings import EmbeddingManager

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s: %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)


def main() -> None:
    parser = argparse.ArgumentParser(description="Run hybrid alignment pipeline")
    parser.add_argument("--verbose", action="store_true", help="Enable debug logging")
    args = parser.parse_args()

    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)

    storage = StorageManager()
    n_concepts = storage.count_concepts()
    if n_concepts == 0:
        logger.error("No concepts in DB — run scripts/run_nlp_pipeline.py first.")
        sys.exit(1)
    logger.info(f"Found {n_concepts} concepts in DB.")

    # Load CS2023 knowledge areas
    ka_path = STANDARDS_DIR / "cs2023_ka.json"
    if not ka_path.exists():
        logger.error(f"CS2023 KA file not found: {ka_path}")
        sys.exit(1)
    with open(ka_path) as f:
        ka_data = json.load(f)

    n_topics = sum(len(v["topics"]) for v in ka_data.values())
    logger.info(f"Loaded {len(ka_data)} KAs with {n_topics} topics from CS2023.")

    logger.info("Initialising embedding model (SBERT all-MiniLM-L6-v2)…")
    em = EmbeddingManager()

    logger.info("Running hybrid alignment…")
    n_alignments = run_alignment(storage, em, ka_data)

    # ── Summary ────────────────────────────────────────────────────────────────
    alignments = storage.get_all_alignments()
    ambiguous = sum(1 for a in alignments if a.is_ambiguous)
    ka_hits: dict[str, int] = {}
    for a in alignments:
        if a.rank == 1:
            ka_hits[a.ka_code] = ka_hits.get(a.ka_code, 0) + 1

    summary = {
        "n_concepts_aligned": n_concepts,
        "n_alignment_records": n_alignments,
        "n_ambiguous_concepts": ambiguous,
        "ka_distribution": dict(sorted(ka_hits.items(), key=lambda x: -x[1])),
    }

    out_path = PROCESSED_DIR / "alignment_summary.json"
    with open(out_path, "w") as f:
        json.dump(summary, f, indent=2)

    logger.info("=" * 60)
    logger.info("ALIGNMENT SUMMARY")
    logger.info("=" * 60)
    logger.info(f"  Concepts aligned:    {n_concepts}")
    logger.info(f"  Alignment records:   {n_alignments}")
    logger.info(f"  Ambiguous concepts:  {ambiguous} ({100*ambiguous/max(n_concepts,1):.1f}%)")
    logger.info("  KA distribution (top 10):")
    for ka, count in list(summary["ka_distribution"].items())[:10]:
        logger.info(f"    {ka}: {count} concepts")
    logger.info(f"  Summary saved to {out_path}")


if __name__ == "__main__":
    main()
