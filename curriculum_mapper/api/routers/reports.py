"""Reports router — /api/v1/reports"""

from __future__ import annotations

from collections import defaultdict
from datetime import UTC, datetime

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse

from curriculum_mapper.api.dependencies import get_graph_stats, get_ka_data, get_storage
from curriculum_mapper.api.schemas import (
    GapItem,
    KACoverageItem,
    RedundancyItem,
    SummaryOut,
)
from curriculum_mapper.config import GAP_COVERAGE_THRESHOLD, SBERT_MATCH_THRESHOLD
from curriculum_mapper.evaluation.graph_validation import compare_programmes
from curriculum_mapper.graph.gap_detector import detect_gaps, detect_redundancies
from curriculum_mapper.ingestion.storage import StorageManager

router = APIRouter()

# Display labels for the source cohorts used by the comparison/matrix views.
_COHORT_LABELS = {"imperial": "Imperial Computing", "mit_ocw": "MIT OpenCourseWare"}


def _cohort_of(source: str | None) -> str:
    return "mit_ocw" if (source or "").startswith("mit") else "imperial"


@router.get("/coverage", response_model=list[KACoverageItem])
def get_coverage(
    storage: StorageManager = Depends(get_storage),
) -> list[KACoverageItem]:
    """Per-KA coverage: fraction of modules with at least one aligned concept."""
    stats = get_graph_stats()
    ka_data = get_ka_data()
    modules = storage.get_all_modules()
    n_modules = len(modules)

    if stats and "coverage" in stats:
        ka_coverage = stats["coverage"].get("ka_coverage", {})
    else:
        # Recompute on-the-fly
        from curriculum_mapper.graph.analytics import compute_ka_coverage_full
        concepts = storage.get_all_concepts()
        alignments = storage.get_all_alignments()
        ka_coverage = compute_ka_coverage_full(concepts, alignments, ka_data, modules)

    items = []
    for ka_code, ka_info in ka_data.items():
        coverage = ka_coverage.get(ka_code, 0.0)
        module_count = round(coverage * n_modules)
        if coverage >= 0.5:
            severity = "good"
        elif coverage >= GAP_COVERAGE_THRESHOLD:
            severity = "warning"
        else:
            severity = "critical"
        items.append(
            KACoverageItem(
                ka_code=ka_code,
                ka_name=ka_info["name"],
                coverage=coverage,
                module_count=module_count,
                severity=severity,
            )
        )

    return sorted(items, key=lambda x: -x.coverage)


@router.get("/programme-comparison")
def get_programme_comparison(
    storage: StorageManager = Depends(get_storage),
) -> JSONResponse:
    """Per-cohort CS2023 KA coverage for the side-by-side comparison view.

    Realises the interim's "browse two curricula side-by-side … to reveal
    differences in topic coverage" (§2.7) and the §3.5 stretch goal of contrasting
    an external cohort. Reuses :func:`compare_programmes`. On a single-cohort
    database (the canonical Imperial DB) this returns one cohort; the combined
    ``curriculum_multi.db`` returns Imperial vs MIT OCW.
    """
    ka_data = get_ka_data()
    cohorts = compare_programmes(storage)
    cohort_rows = [
        {"key": key, "label": _COHORT_LABELS.get(key, key.replace("_", " ").title()), **vals}
        for key, vals in cohorts.items()
    ]
    return JSONResponse(
        content={
            "kas": [{"code": k, "name": ka_data[k]["name"]} for k in ka_data],
            "cohorts": cohort_rows,
            "comparable": len(cohort_rows) > 1,
        }
    )


@router.get("/coverage-matrix")
def get_coverage_matrix(
    storage: StorageManager = Depends(get_storage),
) -> JSONResponse:
    """Module × CS2023 Knowledge-Area grid: for each module, the count of its
    rank-1-aligned concepts in each KA.

    The interactive form of the report's module×KA coverage heatmap --- the
    interim's "adjacency matrix … may supplement node-link diagrams … to see
    coverage across multiple categories at once without crossing edges".
    """
    ka_data = get_ka_data()
    modules = storage.get_all_modules()
    concepts = storage.get_all_concepts()
    alignments = storage.get_all_alignments()

    best = {a.concept_id: a for a in alignments if a.rank == 1}
    cid_modules = {c.id: c.module_codes for c in concepts}
    cells: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))
    for cid, a in best.items():
        for mc in cid_modules.get(cid, []):
            cells[mc][a.ka_code] += 1

    # Imperial first, then by level then code, so the grid groups sensibly.
    ordered = sorted(modules, key=lambda m: (_cohort_of(m.source) == "mit_ocw", m.level or 0, m.code))
    module_rows = [
        {
            "code": m.code,
            "title": m.title,
            "level": m.level,
            "cohort": _COHORT_LABELS[_cohort_of(m.source)],
        }
        for m in ordered
    ]
    return JSONResponse(
        content={
            "kas": [{"code": k, "name": ka_data[k]["name"]} for k in ka_data],
            "modules": module_rows,
            "cells": {m: dict(kas) for m, kas in cells.items()},
        }
    )


@router.get("/gaps", response_model=list[GapItem])
def get_gaps(
    storage: StorageManager = Depends(get_storage),
) -> list[GapItem]:
    """KAs below the coverage threshold."""
    stats = get_graph_stats()
    ka_data = get_ka_data()
    modules = storage.get_all_modules()

    if stats and "coverage" in stats:
        ka_coverage = stats["coverage"].get("ka_coverage", {})
    else:
        from curriculum_mapper.graph.analytics import compute_ka_coverage_full
        concepts = storage.get_all_concepts()
        alignments = storage.get_all_alignments()
        ka_coverage = compute_ka_coverage_full(concepts, alignments, ka_data, modules)

    gaps = detect_gaps(ka_coverage, ka_data)
    return [
        GapItem(
            ka_code=g["ka_code"],
            ka_name=g["ka_name"],
            coverage=g["coverage"],
            severity=g["severity"],
        )
        for g in gaps
    ]


def _redundancies(storage: StorageManager) -> list[dict]:
    """Redundancies from cached graph stats if present, else computed live.

    Preferring the build-time stats keeps the API consistent with the pipeline
    artefacts and robust to runtime configuration differences.
    """
    stats = get_graph_stats()
    if stats and "coverage" in stats and stats["coverage"].get("redundancies"):
        return stats["coverage"]["redundancies"]
    return detect_redundancies(storage.get_all_concepts())


@router.get("/redundancies", response_model=list[RedundancyItem])
def get_redundancies(
    storage: StorageManager = Depends(get_storage),
) -> list[RedundancyItem]:
    """Concepts appearing in too many modules."""
    return [
        RedundancyItem(
            concept=r["concept"],
            module_count=r["module_count"],
            modules=r["modules"],
            confidence=r["confidence"],
        )
        for r in _redundancies(storage)
    ]


@router.get("/summary", response_model=SummaryOut)
def get_summary(
    storage: StorageManager = Depends(get_storage),
) -> SummaryOut:
    """Full curriculum health summary."""
    ka_data = get_ka_data()
    modules = storage.get_all_modules()
    concepts = storage.get_all_concepts()
    alignments = storage.get_all_alignments()

    stats = get_graph_stats()
    if stats and "coverage" in stats:
        coverage_report = stats["coverage"]
        ka_coverage = coverage_report.get("ka_coverage", {})
    else:
        from curriculum_mapper.graph.analytics import compute_ka_coverage_full
        from curriculum_mapper.graph.gap_detector import generate_coverage_report
        ka_coverage = compute_ka_coverage_full(concepts, alignments, ka_data, modules)
        coverage_report = generate_coverage_report(ka_coverage, ka_data, concepts)

    validated_count = sum(1 for a in alignments if a.validated is not None)
    ambiguous_count = sum(1 for a in alignments if a.is_ambiguous)

    covered_kas = sum(
        1 for v in ka_coverage.values() if v >= GAP_COVERAGE_THRESHOLD
    )
    total_kas = len(ka_data)
    coverage_fraction = covered_kas / total_kas if total_kas else 0.0

    gaps = detect_gaps(ka_coverage, ka_data)
    redundancies = _redundancies(storage)

    critical_gaps = [g for g in gaps if g["severity"] == "critical"]

    return SummaryOut(
        total_modules=len(modules),
        total_concepts=len(concepts),
        total_alignments=len(alignments),
        validated_count=validated_count,
        ambiguous_count=ambiguous_count,
        ka_coverage_fraction=round(coverage_fraction, 4),
        covered_kas=covered_kas,
        total_kas=total_kas,
        gap_count=len(gaps),
        critical_gap_count=len(critical_gaps),
        redundancy_count=len(redundancies),
        top_gaps=[
            GapItem(
                ka_code=g["ka_code"],
                ka_name=g["ka_name"],
                coverage=g["coverage"],
                severity=g["severity"],
            )
            for g in gaps[:5]
        ],
        top_redundancies=[
            RedundancyItem(
                concept=r["concept"],
                module_count=r["module_count"],
                modules=r["modules"],
                confidence=r["confidence"],
            )
            for r in redundancies[:5]
        ],
    )


@router.get("/export")
def export_report(
    storage: StorageManager = Depends(get_storage),
) -> JSONResponse:
    """Full JSON curriculum snapshot for archiving or external reporting.

    Returns a self-contained document with all pipeline outputs: modules,
    concepts (with variants and confidence), alignments (validated state
    included), KA coverage, gap list, and redundancy list.
    Suitable for curriculum review committees or downstream processing.
    """
    ka_data = get_ka_data()
    modules = storage.get_all_modules()
    concepts = storage.get_all_concepts()
    alignments = storage.get_all_alignments()

    stats = get_graph_stats()
    if stats and "coverage" in stats:
        ka_coverage = stats["coverage"].get("ka_coverage", {})
    else:
        from curriculum_mapper.graph.analytics import compute_ka_coverage_full
        ka_coverage = compute_ka_coverage_full(concepts, alignments, ka_data, modules)

    gaps = detect_gaps(ka_coverage, ka_data)
    redundancies = detect_redundancies(concepts)

    snapshot = {
        "generated_at": datetime.now(UTC).isoformat(),
        "system_version": "1.0.0",
        "evaluation_config": {
            "sbert_model": "all-MiniLM-L6-v2",
            "sbert_match_threshold": SBERT_MATCH_THRESHOLD,
            "gap_coverage_threshold": GAP_COVERAGE_THRESHOLD,
        },
        "summary": {
            "total_modules": len(modules),
            "total_concepts": len(concepts),
            "total_alignments": len(alignments),
            "validated_alignments": sum(1 for a in alignments if a.validated is not None),
            "accepted_alignments": sum(1 for a in alignments if a.validated is True),
            "rejected_alignments": sum(1 for a in alignments if a.validated is False),
            "ambiguous_alignments": sum(1 for a in alignments if a.is_ambiguous),
            "covered_kas": sum(1 for v in ka_coverage.values() if v >= GAP_COVERAGE_THRESHOLD),
            "total_kas": len(ka_data),
        },
        "modules": [
            {
                "code": m.code,
                "title": m.title,
                "level": m.level,
                "credits": m.credits,
                "prerequisites": m.prerequisites,
                "source": m.source,
                "ilo_count": len(m.ilos),
            }
            for m in modules
        ],
        "concepts": [
            {
                "id": c.id,
                "term": c.term,
                "variants": c.variants,
                "confidence": c.confidence,
                "extractors": c.extractors,
                "module_count": len(c.module_codes),
                "module_codes": c.module_codes,
            }
            for c in concepts
        ],
        "alignments": [
            {
                "id": a.id,
                "concept_id": a.concept_id,
                "ka_code": a.ka_code,
                "ka_topic": a.ka_topic,
                "method": a.method,
                "score": a.score,
                "rank": a.rank,
                "is_ambiguous": a.is_ambiguous,
                "validated": a.validated,
                "validated_by": a.validated_by,
            }
            for a in alignments
        ],
        "ka_coverage": [
            {
                "ka_code": ka_code,
                "ka_name": ka_data[ka_code]["name"],
                "coverage_fraction": ka_coverage.get(ka_code, 0.0),
                "module_count": round(ka_coverage.get(ka_code, 0.0) * len(modules)),
            }
            for ka_code in ka_data
        ],
        "gaps": gaps,
        "redundancies": redundancies,
    }

    return JSONResponse(content=snapshot)
