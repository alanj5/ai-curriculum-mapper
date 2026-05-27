"""Curriculum gap and redundancy detection.

Gaps: KAs whose coverage fraction is below GAP_COVERAGE_THRESHOLD (10%).
  severity = "critical" (0% coverage) or "warning" (1–9%).

Redundancy: concepts appearing in >= REDUNDANCY_THRESHOLD modules with high
confidence — may indicate over-taught topics worth consolidating.
"""

from __future__ import annotations

from curriculum_mapper.config import GAP_COVERAGE_THRESHOLD, REDUNDANCY_THRESHOLD
from curriculum_mapper.ingestion.schema import Concept


def detect_gaps(
    ka_coverage: dict[str, float],
    ka_data: dict,
) -> list[dict]:
    """Return sorted list of gap dicts (most severe first)."""
    gaps = []
    for ka_code, coverage in ka_coverage.items():
        if coverage < GAP_COVERAGE_THRESHOLD:
            gaps.append({
                "ka_code": ka_code,
                "ka_name": ka_data.get(ka_code, {}).get("name", ka_code),
                "coverage": coverage,
                "severity": "critical" if coverage == 0.0 else "warning",
            })
    return sorted(gaps, key=lambda g: g["coverage"])


def detect_redundancies(concepts: list[Concept]) -> list[dict]:
    """Return concepts appearing in >= REDUNDANCY_THRESHOLD modules."""
    redundant = []
    for c in concepts:
        if len(c.module_codes) >= REDUNDANCY_THRESHOLD and c.confidence > 0.5:
            redundant.append({
                "concept": c.term,
                "module_count": len(c.module_codes),
                "modules": sorted(c.module_codes),
                "confidence": c.confidence,
            })
    return sorted(redundant, key=lambda r: -r["module_count"])


def generate_coverage_report(
    ka_coverage: dict[str, float],
    ka_data: dict,
    concepts: list[Concept],
) -> dict:
    """Full curriculum health report."""
    gaps = detect_gaps(ka_coverage, ka_data)
    redundancies = detect_redundancies(concepts)

    covered_kas = sum(1 for v in ka_coverage.values() if v >= GAP_COVERAGE_THRESHOLD)
    total_kas = len(ka_coverage)

    return {
        "total_kas": total_kas,
        "covered_kas": covered_kas,
        "coverage_fraction": round(covered_kas / total_kas, 4) if total_kas else 0.0,
        "gap_count": len(gaps),
        "critical_gaps": [g["ka_code"] for g in gaps if g["severity"] == "critical"],
        "warning_gaps": [g["ka_code"] for g in gaps if g["severity"] == "warning"],
        "gaps": gaps,
        "redundancy_count": len(redundancies),
        "redundancies": redundancies[:10],  # top 10
        "ka_coverage": ka_coverage,
    }
