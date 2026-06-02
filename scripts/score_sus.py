#!/usr/bin/env python3
"""Score a System Usability Scale (SUS) questionnaire from a CSV.

Usage:
    # 1. Emit a blank template to fill in (one row per participant):
    python scripts/score_sus.py --template responses.csv

    # 2. After filling it in, score it:
    python scripts/score_sus.py responses.csv [--json out.json]

CSV columns (case-insensitive): Q1..Q10 (the ten SUS items, 1-5). Optional
U1,U2,U3 (usefulness/trust Likert, 1-5) and an id column are ignored for SUS.
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from curriculum_mapper.evaluation.usability import summarise_likert, summarise_sus

SUS_COLS = [f"Q{i}" for i in range(1, 11)]
U_COLS = ["U1", "U2", "U3"]


def _template(path: Path) -> None:
    header = ["participant", *SUS_COLS, *U_COLS]
    with open(path, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(header)
        for p in ("P1", "P2", "P3"):
            w.writerow([p, *([""] * (len(header) - 1))])
    print(f"Wrote blank SUS template to {path} (Q1..Q10 = SUS items 1..5; U1..U3 optional).")


def _read(path: Path):
    with open(path, newline="") as f:
        rows = list(csv.DictReader(f))
    # case-insensitive column lookup
    def col(row, name):
        for k, v in row.items():
            if k and k.strip().lower() == name.lower():
                return v
        return None

    sus, likert = [], []
    for row in rows:
        vals = [col(row, c) for c in SUS_COLS]
        if any(v is None or v == "" for v in vals):
            continue
        sus.append([int(float(v)) for v in vals])
        uvals = [col(row, c) for c in U_COLS]
        if all(v not in (None, "") for v in uvals):
            likert.append([float(v) for v in uvals])
    return sus, likert


def main() -> None:
    ap = argparse.ArgumentParser(description="Score a SUS questionnaire CSV")
    ap.add_argument("csv", help="path to the responses CSV (or template target with --template)")
    ap.add_argument("--template", action="store_true", help="write a blank template instead of scoring")
    ap.add_argument("--json", help="also write the summary to this JSON path")
    args = ap.parse_args()

    path = Path(args.csv)
    if args.template:
        _template(path)
        return

    sus, likert = _read(path)
    if not sus:
        print("No complete SUS rows found (need Q1..Q10 filled).")
        sys.exit(1)

    summary = summarise_sus(sus)
    if likert:
        summary["likert_means"] = summarise_likert(likert)

    print("=" * 50)
    print(f"SUS results  (N = {summary['n']})")
    print("=" * 50)
    print(f"  Mean SUS  : {summary['mean']}  ({summary['band']})")
    print(f"  SD        : {summary['sd']}")
    print(f"  Range     : {summary['min']} – {summary['max']}")
    print(f"  >= 68 avg : {'yes' if summary['above_average'] else 'no'}")
    print(f"  Per-part. : {summary['scores']}")
    if "likert_means" in summary:
        print(f"  Likert U1-U3 means: {summary['likert_means']}")

    if args.json:
        Path(args.json).write_text(json.dumps(summary, indent=2))
        print(f"\nWrote summary to {args.json}")


if __name__ == "__main__":
    main()
