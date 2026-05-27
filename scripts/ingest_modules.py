#!/usr/bin/env python3
"""Ingest all module descriptors from data/raw/modules/ into the SQLite DB.

Usage:
    python scripts/ingest_modules.py [--verbose]
"""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

# Ensure project root is on path
sys.path.insert(0, str(Path(__file__).parent.parent))

from curriculum_mapper.ingestion.loader import load_all_modules
from curriculum_mapper.ingestion.storage import StorageManager

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)


def main() -> None:
    parser = argparse.ArgumentParser(description="Ingest module descriptors into DB")
    parser.add_argument("--verbose", action="store_true")
    args = parser.parse_args()

    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)

    storage = StorageManager()
    logger.info(f"Modules in DB before ingest: {storage.count_modules()}")

    modules = load_all_modules()
    if not modules:
        logger.error("No modules found — run scripts/create_imperial_modules.py first")
        sys.exit(1)

    inserted = 0
    for module in modules:
        try:
            storage.insert_module(module)
            inserted += 1
            if args.verbose:
                logger.debug(
                    f"  {module.code}: {module.title} "
                    f"(level {module.level}, {len(module.ilos)} ILOs, "
                    f"{len(module.topics)} topics)"
                )
        except Exception as e:
            logger.warning(f"Failed to insert {module.code}: {e}")

    total = storage.count_modules()
    logger.info(f"Inserted {inserted} modules. Total in DB: {total}")

    if total < 20:
        logger.warning(
            f"Only {total} modules in DB — target is 20+. "
            "Add more modules to data/raw/modules/ or run scripts/create_imperial_modules.py."
        )
    else:
        logger.info("Week 1 criterion MET: 20+ modules in DB ✓")


if __name__ == "__main__":
    main()
