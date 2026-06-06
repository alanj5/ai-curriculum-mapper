#!/usr/bin/env python3
"""Re-runnable acquisition of Imperial Computing module descriptors.

This is the reproducible, provenance-recording counterpart to
``create_imperial_modules.py``. For each module it:

  1. fetches the live descriptor page
     (``https://www.imperial.ac.uk/computing/current-students/courses/<code>/``),
  2. records provenance --- ``source_url``, ``fetched_at`` (UTC), the page's
     HTTP status and the SHA-256 of the response body,
  3. parses title / aims / learning outcomes / syllabus from the static HTML,
  4. writes a module JSON in the canonical on-disk format plus the provenance.

Level, credits and prerequisites are not published on the descriptor pages, so
they are taken from the curated table in ``create_imperial_modules.py``. By
default the *curated* description / outcomes / topics remain the reviewed source
of record (the live page is used to attach provenance and to flag drift); pass
``--adopt-parsed`` to instead write the freshly parsed content.

Usage::

    python scripts/fetch_imperial_modules.py                 # fetch + stamp provenance
    python scripts/fetch_imperial_modules.py --only IC40001  # one module (debug)
    python scripts/fetch_imperial_modules.py --offline        # no network (CI/curated)
    python scripts/fetch_imperial_modules.py --adopt-parsed   # use live-parsed content
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

# Allow ``import create_imperial_modules`` when run as a script.
sys.path.insert(0, str(Path(__file__).parent))
from create_imperial_modules import IMPERIAL_DIR, MODULES  # noqa: E402

from curriculum_mapper.ingestion.imperial_scraper import (  # noqa: E402
    build_source_url,
    fetch_descriptor,
)


def _norm(text: str) -> str:
    return " ".join(text.lower().split())


def _content_drift(curated: dict, parsed) -> list[str]:
    """Return the names of fields whose live-parsed content differs from curated."""
    drift: list[str] = []
    if parsed is None:
        return drift
    if parsed.description and _norm(parsed.description) != _norm(curated["description"]):
        drift.append("description")
    if parsed.learning_objectives and {
        _norm(x) for x in parsed.learning_objectives
    } != {_norm(x) for x in curated["learning_objectives"]}:
        drift.append("learning_objectives")
    if parsed.topics and {_norm(x) for x in parsed.topics} != {
        _norm(x) for x in curated["topics"]
    }:
        drift.append("topics")
    return drift


def build_record(curated: dict, *, offline: bool, adopt_parsed: bool, retries: int) -> dict:
    """Build the JSON record for one module, fetching provenance unless offline."""
    code = curated["code"]
    record = dict(curated)  # start from curated content (authoritative by default)
    record["source_url"] = build_source_url(code)

    if offline:
        record["fetched_at"] = None
        record["content_sha256"] = None
        record["fetch_ok"] = False
        record["fetch_note"] = "offline: curated content, no live provenance"
        return record

    result = fetch_descriptor(code, retries=retries)
    record["fetched_at"] = result.fetched_at
    record["content_sha256"] = result.content_sha256
    record["fetch_ok"] = result.ok
    record["http_status"] = result.http_status

    if not result.ok:
        record["fetch_note"] = (
            f"fetch failed ({result.error}); curated content retained as fallback"
        )
        return record

    drift = _content_drift(curated, result.parsed)
    record["content_drift"] = drift
    if adopt_parsed and result.parsed and not result.parsed.is_empty:
        record["title"] = result.parsed.title or curated["title"]
        record["description"] = result.parsed.description or curated["description"]
        record["learning_objectives"] = (
            result.parsed.learning_objectives or curated["learning_objectives"]
        )
        record["topics"] = result.parsed.topics or curated["topics"]
        record["fetch_note"] = "content adopted from live page"
    else:
        record["fetch_note"] = (
            "curated content retained; live page fetched for provenance"
            + (f"; drift in {drift}" if drift else "")
        )
    return record


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--offline", action="store_true", help="skip the network; curated content only")
    parser.add_argument("--adopt-parsed", action="store_true", help="write freshly parsed live content")
    parser.add_argument("--only", help="fetch a single module code (e.g. IC40001)")
    parser.add_argument("--retries", type=int, default=2, help="network retries per page")
    args = parser.parse_args()

    modules = MODULES
    if args.only:
        modules = [m for m in MODULES if m["code"].upper() == args.only.upper()]
        if not modules:
            print(f"No module with code {args.only}", file=sys.stderr)
            return 2

    IMPERIAL_DIR.mkdir(parents=True, exist_ok=True)
    fetched, fell_back, drifted = 0, 0, 0
    started = datetime.now(timezone.utc).isoformat()

    for curated in modules:
        record = build_record(
            curated, offline=args.offline, adopt_parsed=args.adopt_parsed, retries=args.retries
        )
        path = IMPERIAL_DIR / f"{record['code']}.json"
        with open(path, "w") as fh:
            json.dump(record, fh, indent=2)

        if record.get("fetch_ok"):
            fetched += 1
            if record.get("content_drift"):
                drifted += 1
                print(f"  drift  {record['code']}: {record['content_drift']}")
        elif not args.offline:
            fell_back += 1
            print(f"  fallback {record['code']}: {record.get('fetch_note')}")

    print(
        f"\nRun started {started}\n"
        f"{len(modules)} modules written to {IMPERIAL_DIR}\n"
        f"  fetched OK : {fetched}\n"
        f"  fell back  : {fell_back}\n"
        f"  with drift : {drifted}"
        + ("\n  (offline mode: provenance not recorded)" if args.offline else "")
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
