"""Alignments router — /api/v1/alignments"""

from __future__ import annotations

from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, Query

from curriculum_mapper.api.dependencies import get_ka_data, get_storage
from curriculum_mapper.api.schemas import AlignmentStatsOut, ValidateRequest
from curriculum_mapper.ingestion.storage import StorageManager, get_connection

router = APIRouter()


@router.get("/")
def list_alignments(
    ka: str | None = Query(None),
    method: str | None = Query(None),
    validated: bool | None = Query(None),
    ambiguous: bool | None = Query(None),
    rank: int | None = Query(None, ge=1, le=3),
    limit: int = Query(200, ge=1, le=1000),
    offset: int = Query(0, ge=0),
    storage: StorageManager = Depends(get_storage),
) -> list[dict]:
    """List alignments with optional filters."""
    alignments = storage.get_all_alignments()
    all_concepts = storage.get_all_concepts()
    concept_terms = {c.id: c.term for c in all_concepts}
    concept_modules = {c.id: c.module_codes for c in all_concepts}

    if ka:
        alignments = [a for a in alignments if a.ka_code == ka.upper()]
    if method:
        alignments = [a for a in alignments if a.method == method]
    if validated is not None:
        alignments = [a for a in alignments if a.validated == validated]
    if ambiguous is not None:
        alignments = [a for a in alignments if a.is_ambiguous == ambiguous]
    if rank is not None:
        alignments = [a for a in alignments if a.rank == rank]

    alignments = sorted(alignments, key=lambda x: -x.score)
    alignments = alignments[offset : offset + limit]

    return [
        {
            "id": a.id,
            "concept_id": a.concept_id,
            "concept_term": concept_terms.get(a.concept_id, ""),
            "source_modules": concept_modules.get(a.concept_id, []),
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
    ]


@router.patch("/{alignment_id}/validate")
def validate_alignment(
    alignment_id: str,
    body: ValidateRequest,
    storage: StorageManager = Depends(get_storage),
) -> dict:
    """Accept, reject, or reassign an alignment (human-in-the-loop)."""
    if body.action not in ("accept", "reject", "reassign"):
        raise HTTPException(
            status_code=422,
            detail="action must be 'accept', 'reject', or 'reassign'",
        )
    if body.action == "reassign" and not body.new_ka_code:
        raise HTTPException(
            status_code=422,
            detail="new_ka_code required for reassign action",
        )

    with get_connection(storage.db_path) as conn:
        # Check alignment exists
        row = conn.execute(
            "SELECT id FROM alignments WHERE id=?", (alignment_id,)
        ).fetchone()
        if row is None:
            raise HTTPException(
                status_code=404,
                detail=f"Alignment '{alignment_id}' not found",
            )

        now = datetime.now(UTC).isoformat()
        by = body.validated_by or "user"

        if body.action == "reassign":
            # A reassignment is an expert correction: point the alignment at the
            # new KA, mark it accepted, and flag it as no longer ambiguous so the
            # change is visible in the table.
            new_ka = (body.new_ka_code or "").upper()  # guaranteed non-empty above
            ka_name = get_ka_data().get(new_ka, {}).get("name", new_ka)
            conn.execute(
                """UPDATE alignments
                   SET ka_code=?, ka_topic=?, validated=1, is_ambiguous=0,
                       validated_by=?, validated_at=?
                   WHERE id=?""",
                (new_ka, f"{ka_name} (reassigned)", by, now, alignment_id),
            )
        else:
            validated_value = 1 if body.action == "accept" else 0
            conn.execute(
                """UPDATE alignments SET validated=?, validated_by=?, validated_at=?
                   WHERE id=?""",
                (validated_value, by, now, alignment_id),
            )

        # Write to user_feedback table
        import uuid
        conn.execute(
            """INSERT INTO user_feedback (id, alignment_id, action, new_ka_code, comment, created_at)
               VALUES (?,?,?,?,?,?)""",
            (
                str(uuid.uuid4()),
                alignment_id,
                body.action,
                body.new_ka_code,
                body.comment,
                datetime.now(UTC).isoformat(),
            ),
        )

    return {"id": alignment_id, "action": body.action, "status": "updated"}


@router.get("/stats", response_model=AlignmentStatsOut)
def alignment_stats(
    storage: StorageManager = Depends(get_storage),
) -> AlignmentStatsOut:
    """Aggregate alignment statistics."""
    alignments = storage.get_all_alignments()

    by_ka: dict[str, int] = {}
    by_method: dict[str, int] = {}
    validated_count = 0
    ambiguous_count = 0
    accepted_count = 0
    rejected_count = 0

    for a in alignments:
        if a.rank == 1:  # count concepts, not individual alignment records
            by_ka[a.ka_code] = by_ka.get(a.ka_code, 0) + 1
        by_method[a.method] = by_method.get(a.method, 0) + 1
        if a.validated is not None:
            validated_count += 1
        if a.is_ambiguous:
            ambiguous_count += 1
        if a.validated is True:
            accepted_count += 1
        if a.validated is False:
            rejected_count += 1

    return AlignmentStatsOut(
        total=len(alignments),
        by_ka=dict(sorted(by_ka.items(), key=lambda x: -x[1])),
        by_method=by_method,
        validated_count=validated_count,
        ambiguous_count=ambiguous_count,
        accepted_count=accepted_count,
        rejected_count=rejected_count,
    )
