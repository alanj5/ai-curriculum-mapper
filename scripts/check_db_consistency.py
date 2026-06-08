#!/usr/bin/env python3
"""Guard against the two corpora drifting apart.

The project deliberately keeps two databases (see ``make pipeline-all``):

* ``curriculum.db``       -- Imperial only, the report's clean reference run.
* ``curriculum_multi.db`` -- Imperial + MIT OCW, the UI / cross-programme corpus.

They are separate because concept extraction is corpus-dependent, so MIT must
not leak into the Imperial reference numbers. The cost of that separation is
that the two can drift if only one is rebuilt (which is exactly what happened
when the syllabus-inclusion fix landed in the canonical DB but not the multi
DB). This script is a cheap sanity guard: it fails loudly if the combined DB is
missing Imperial modules, is empty, or was clearly built from older code than
the canonical DB.

Exit code 0 = consistent, 1 = drift detected.
"""
from __future__ import annotations

import sqlite3
import sys
from pathlib import Path

DATA = Path(__file__).resolve().parent.parent / "data"
CANON = DATA / "curriculum.db"
MULTI = DATA / "curriculum_multi.db"


def _modules(db: Path) -> set[str]:
    con = sqlite3.connect(db)
    try:
        return {r[0] for r in con.execute("select code from modules")}
    finally:
        con.close()


def _concept_count(db: Path) -> int:
    con = sqlite3.connect(db)
    try:
        return con.execute("select count(*) from concepts").fetchone()[0]
    finally:
        con.close()


def main() -> int:
    problems: list[str] = []

    if not CANON.exists():
        problems.append(f"canonical DB missing: {CANON}")
    if not MULTI.exists():
        problems.append(f"multi DB missing: {MULTI} (run `make pipeline-multi`)")
    if problems:
        print("\n".join("FAIL: " + p for p in problems))
        return 1

    canon_mods, multi_mods = _modules(CANON), _modules(MULTI)
    missing = canon_mods - multi_mods
    if missing:
        problems.append(
            f"multi DB is missing {len(missing)} Imperial module(s) present in the "
            f"canonical DB: {sorted(missing)[:8]}{'…' if len(missing) > 8 else ''} "
            "-- rebuild with `make pipeline-multi`."
        )

    if _concept_count(MULTI) == 0:
        problems.append("multi DB has 0 concepts (stale/empty) -- run `make pipeline-multi`.")
    if _concept_count(CANON) == 0:
        problems.append("canonical DB has 0 concepts (stale/empty) -- run `make pipeline`.")

    if problems:
        print("\n".join("FAIL: " + p for p in problems))
        print("\nFix: `make pipeline-all` rebuilds both corpora from the current code.")
        return 1

    print(
        f"OK: canonical {len(canon_mods)} modules / {_concept_count(CANON)} concepts; "
        f"multi {len(multi_mods)} modules / {_concept_count(MULTI)} concepts; "
        f"multi ⊇ canonical module set."
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
