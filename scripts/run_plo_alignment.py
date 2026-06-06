#!/usr/bin/env python3
"""Map modules to the programme-level outcomes (PLOs) they fulfil.

Realises the interim's third node type ("Learning Outcomes") and the §2.7.2 /
§2.7.1 interaction "which programme-level outcomes a course fulfils" / "clicking a
PLO links to all courses that address it".

Each module's text (description + ILOs) is embedded with SBERT and compared to
each programme learning-outcome description; the top-scoring outcomes above a
floor are stored as the outcomes that module fulfils. Modules are aligned to the
``beng_computing`` outcome set (the universal Computing outcomes that apply to all
content modules); the full per-programme outcome lists are also stored.

Usage:
    python scripts/run_plo_alignment.py [--top-k 4] [--floor 0.20]
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).parent.parent))

from curriculum_mapper.config import STANDARDS_DIR
from curriculum_mapper.ingestion.schema import PLOAlignment, ProgrammeLearningOutcome
from curriculum_mapper.ingestion.storage import StorageManager
from curriculum_mapper.nlp.embeddings import EmbeddingManager

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s: %(message)s", datefmt="%H:%M:%S")
logger = logging.getLogger(__name__)

OUTCOMES_PATH = STANDARDS_DIR / "programme_outcomes.json"
ALIGN_PROGRAMME = "beng_computing"  # universal Computing outcome set


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--top-k", type=int, default=4, help="max outcomes stored per module")
    ap.add_argument("--floor", type=float, default=0.20, help="minimum cosine to count as fulfilled")
    args = ap.parse_args()

    storage = StorageManager()
    modules = storage.get_all_modules()
    if not modules:
        logger.error("No modules in DB — run ingest_modules.py first.")
        sys.exit(1)

    with open(OUTCOMES_PATH) as fh:
        outcomes = json.load(fh)["programmes"]

    # Persist every programme's outcomes (the "Learning Outcome" nodes).
    storage.clear_plos()
    plo_objs: dict[str, list[ProgrammeLearningOutcome]] = {}
    for programme, plos in outcomes.items():
        plo_objs[programme] = []
        for p in plos:
            obj = ProgrammeLearningOutcome(
                programme=programme, code=p["code"], title=p["title"], description=p["description"]
            )
            storage.insert_plo(obj)
            plo_objs[programme].append(obj)
    logger.info("Stored %d outcomes across %d programmes.",
                sum(len(v) for v in plo_objs.values()), len(plo_objs))

    # Align modules to the universal Computing outcome set.
    em = EmbeddingManager()
    target = plo_objs[ALIGN_PROGRAMME]
    plo_embs = np.asarray(em.encode([f"{p.title}. {p.description}" for p in target]), dtype=np.float32)
    plo_embs /= np.linalg.norm(plo_embs, axis=1, keepdims=True) + 1e-9

    n_aligned = 0
    for m in modules:
        text = m.full_text_clean or m.full_text
        if not text.strip():
            continue
        v = np.asarray(em.encode([text])[0], dtype=np.float32)
        v /= np.linalg.norm(v) + 1e-9
        sims = plo_embs @ v
        order = np.argsort(-sims)
        rank = 0
        for idx in order[: args.top_k]:
            score = float(sims[idx])
            if score < args.floor:
                break
            rank += 1
            storage.insert_plo_alignment(
                PLOAlignment(module_code=m.code, plo_id=target[idx].id,
                             method="semantic", score=round(score, 4), rank=rank)
            )
        n_aligned += rank

    logger.info("Stored %d module→outcome alignments (top-%d, floor %.2f).",
                n_aligned, args.top_k, args.floor)
    # Coverage: how many modules fulfil each outcome
    aligns = storage.get_plo_alignments()
    by_plo: dict[str, int] = {}
    title_of = {p.id: p.title for p in target}
    for a in aligns:
        by_plo[a.plo_id] = by_plo.get(a.plo_id, 0) + 1
    logger.info("Outcome coverage (modules fulfilling each):")
    for pid, n in sorted(by_plo.items(), key=lambda x: -x[1]):
        logger.info("  %-44s %d/%d", title_of.get(pid, pid), n, len(modules))


if __name__ == "__main__":
    main()
