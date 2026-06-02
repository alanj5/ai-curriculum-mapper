"""Concepts router — /api/v1/concepts"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query

from curriculum_mapper.api.dependencies import get_storage
from curriculum_mapper.api.schemas import ConceptOut
from curriculum_mapper.ingestion.storage import StorageManager

router = APIRouter()


@router.get("/", response_model=list[ConceptOut])
def list_concepts(
    ka: str | None = Query(None, description="Filter by KA code"),
    search: str | None = Query(None, description="Full-text search on term"),
    module: str | None = Query(None, description="Filter by module code"),
    min_confidence: float = Query(0.0, ge=0.0, le=1.0),
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
    storage: StorageManager = Depends(get_storage),
) -> list[ConceptOut]:
    """List concepts with optional filters."""
    concepts = storage.get_all_concepts()

    if module:
        module_upper = module.upper()
        concepts = [c for c in concepts if module_upper in c.module_codes]

    if search:
        q = search.lower()
        concepts = [c for c in concepts if q in c.term.lower()]

    if min_confidence > 0:
        concepts = [c for c in concepts if c.confidence >= min_confidence]

    if ka:
        # Filter to concepts that have at least one alignment to this KA
        alignments = storage.get_all_alignments()
        ka_concept_ids = {a.concept_id for a in alignments if a.ka_code == ka.upper()}
        concepts = [c for c in concepts if c.id in ka_concept_ids]

    concepts = sorted(concepts, key=lambda c: -c.confidence)
    concepts = concepts[offset : offset + limit]

    return [
        ConceptOut(
            id=c.id,
            term=c.term,
            variants=c.variants,
            confidence=c.confidence,
            extractors=c.extractors,
            module_codes=c.module_codes,
        )
        for c in concepts
    ]


@router.get("/{concept_id}", response_model=ConceptOut)
def get_concept(
    concept_id: str,
    storage: StorageManager = Depends(get_storage),
) -> ConceptOut:
    """Single concept detail."""
    concepts = storage.get_all_concepts()
    concept = next((c for c in concepts if c.id == concept_id), None)
    if concept is None:
        raise HTTPException(status_code=404, detail=f"Concept '{concept_id}' not found")
    return ConceptOut(
        id=concept.id,
        term=concept.term,
        variants=concept.variants,
        confidence=concept.confidence,
        extractors=concept.extractors,
        module_codes=concept.module_codes,
    )


@router.get("/{concept_id}/alignments")
def get_concept_alignments(
    concept_id: str,
    storage: StorageManager = Depends(get_storage),
) -> list[dict]:
    """All alignment results for a concept."""
    concepts = storage.get_all_concepts()
    concept = next((c for c in concepts if c.id == concept_id), None)
    if concept is None:
        raise HTTPException(status_code=404, detail=f"Concept '{concept_id}' not found")

    alignments = [a for a in storage.get_all_alignments() if a.concept_id == concept_id]
    return [
        {
            "id": a.id,
            "concept_id": a.concept_id,
            "concept_term": concept.term,
            "source_modules": concept.module_codes,
            "ka_code": a.ka_code,
            "ka_topic": a.ka_topic,
            "method": a.method,
            "score": a.score,
            "rank": a.rank,
            "is_ambiguous": a.is_ambiguous,
            "validated": a.validated,
        }
        for a in sorted(alignments, key=lambda x: x.rank)
    ]
