#!/usr/bin/env python3
"""Generate a blank second-annotator sheet, and score inter-annotator agreement.

The sheet lists the gold concept terms for a few modules with a blank KA column
for an independent annotator to fill. Cohen's kappa between their labels and the
original gold KAs quantifies inter-annotator agreement.

Usage:
    # 1. Generate a blank sheet for the first 3 gold modules:
    python scripts/make_annotation_sheet.py --modules 3 --out second_annotator.csv

    # 2. After it is filled in, compute agreement:
    python scripts/make_annotation_sheet.py --score second_annotator.csv
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from curriculum_mapper.config import ANNOTATIONS_DIR
from curriculum_mapper.evaluation.metrics import cohens_kappa

GOLD = ANNOTATIONS_DIR / "gold_concepts.json"


def _load_gold() -> dict:
    with open(GOLD) as f:
        return {k: v for k, v in json.load(f).items() if k != "_metadata"}


def generate(n_modules: int, out: Path) -> None:
    gold = _load_gold()
    codes = list(gold.keys())[:n_modules]
    with open(out, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["module_code", "concept_term", "ka_code"])  # ka_code left blank
        for code in codes:
            for c in gold[code]["concepts"]:
                w.writerow([code, c["term"], ""])
    print(f"Wrote blank sheet for {len(codes)} modules ({', '.join(codes)}) to {out}.")
    print("Ask a second annotator to fill the ka_code column independently, then --score it.")


def score(filled: Path) -> None:
    gold = _load_gold()
    # gold lookup: (module, term) -> ka
    gold_ka = {
        (code, c["term"]): c.get("ka")
        for code, data in gold.items()
        for c in data["concepts"]
    }
    a, b = [], []
    with open(filled, newline="") as f:
        for row in csv.DictReader(f):
            key = (row["module_code"], row["concept_term"])
            their = (row.get("ka_code") or "").strip().upper()
            ours = gold_ka.get(key)
            if their and ours:
                a.append(ours)
                b.append(their)
    if not a:
        print("No overlapping labelled rows found.")
        sys.exit(1)
    agree = sum(1 for x, y in zip(a, b) if x == y) / len(a)
    print(f"Compared {len(a)} concept labels.")
    print(f"  Raw agreement : {agree:.3f}")
    print(f"  Cohen's kappa : {cohens_kappa(a, b)}")


def main() -> None:
    ap = argparse.ArgumentParser(description="Second-annotator sheet / agreement")
    ap.add_argument("--modules", type=int, default=3, help="number of gold modules to include")
    ap.add_argument("--out", default="second_annotator_sheet.csv", help="output sheet path")
    ap.add_argument("--score", help="score a filled-in sheet against the gold KAs")
    args = ap.parse_args()
    if args.score:
        score(Path(args.score))
    else:
        generate(args.modules, Path(args.out))


if __name__ == "__main__":
    main()
