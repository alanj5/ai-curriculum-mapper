"""Alignment orchestrator — runs HybridAligner over all concepts in the DB."""

from __future__ import annotations

import json
import logging
from pathlib import Path

from curriculum_mapper.alignment.hybrid import HybridAligner
from curriculum_mapper.config import STANDARDS_DIR
from curriculum_mapper.ingestion.storage import StorageManager
from curriculum_mapper.nlp.embeddings import EmbeddingManager

logger = logging.getLogger(__name__)


def load_ka_data(path: Path | None = None) -> dict:
    p = path or (STANDARDS_DIR / "cs2023_ka.json")
    with open(p) as f:
        return json.load(f)


def run_alignment(
    storage: StorageManager,
    em: EmbeddingManager,
    ka_data: dict | None = None,
) -> int:
    """Align all concepts in DB to CS2023 KAs. Returns number of alignments inserted."""
    if ka_data is None:
        ka_data = load_ka_data()

    aligner = HybridAligner(ka_data, em)
    concepts = storage.get_all_concepts()
    logger.info(f"Aligning {len(concepts)} concepts to {sum(len(v['topics']) for v in ka_data.values())} KA topics…")

    total = 0
    for concept in concepts:
        results = aligner.align(concept)
        for result in results:
            try:
                storage.insert_alignment(result)
                total += 1
            except Exception as e:
                logger.debug(f"Alignment insert failed for {concept.term}: {e}")

    logger.info(f"Alignment complete. {total} alignment records inserted.")
    return total
