"""Reports router — /api/v1/reports"""

from __future__ import annotations

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
from curriculum_mapper.graph.gap_detector import detect_gaps, detect_redundancies
from curriculum_mapper.ingestion.storage import StorageManager

router = APIRouter()


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


@router.get("/redundancies", response_model=list[RedundancyItem])
def get_redundancies(
    storage: StorageManager = Depends(get_storage),
) -> list[RedundancyItem]:
    """Concepts appearing in too many modules."""
    concepts = storage.get_all_concepts()
    redundancies = detect_redundancies(concepts)
    return [
        RedundancyItem(
            concept=r["concept"],
            module_count=r["module_count"],
            modules=r["modules"],
            confidence=r["confidence"],
        )
        for r in redundancies
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
    redundancies = detect_redundancies(concepts)

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
