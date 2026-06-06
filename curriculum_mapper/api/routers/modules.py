"""Modules router — /api/v1/modules"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query

from curriculum_mapper.api.dependencies import get_storage
from curriculum_mapper.api.schemas import ConceptOut, ModuleDetailOut, ModuleOut
from curriculum_mapper.ingestion.storage import StorageManager

router = APIRouter()


@router.get("/", response_model=list[ModuleOut])
def list_modules(
    level: int | None = Query(None, description="Filter by year level 1–4"),
    programme: str | None = Query(None, description="Filter by degree programme id"),
    search: str | None = Query(None, description="Search title or description"),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    storage: StorageManager = Depends(get_storage),
) -> list[ModuleOut]:
    """List all modules with optional level/programme filters and text search."""
    modules = storage.get_all_modules()
    if level is not None:
        modules = [m for m in modules if m.level == level]
    if programme:
        modules = [m for m in modules if programme in m.programmes]
    if search:
        q = search.lower()
        modules = [
            m for m in modules
            if q in m.title.lower() or q in m.description.lower()
        ]
    modules = modules[offset : offset + limit]
    return [
        ModuleOut(
            code=m.code,
            title=m.title,
            level=m.level,
            credits=m.credits,
            prerequisites=m.prerequisites,
            description=m.description,
            source=m.source,
            programmes=m.programmes,
            topics=m.topics,
            ilo_count=len(m.ilos),
        )
        for m in modules
    ]


@router.get("/programmes")
def list_programmes(storage: StorageManager = Depends(get_storage)) -> list[dict]:
    """Degree programmes present in the corpus, with module counts.

    Drives the programme facet (interim §3.2.4 'filter ... by programme')."""
    import json as _json
    from collections import Counter

    from curriculum_mapper.config import DATA_DIR

    names: dict[str, str] = {}
    path = DATA_DIR / "raw" / "programmes.json"
    if path.exists():
        names = _json.loads(path.read_text()).get("programme_names", {})
    names.setdefault("mit_ocw_cs", "MIT OpenCourseWare CS")

    counts: Counter = Counter()
    for m in storage.get_all_modules():
        for p in m.programmes:
            counts[p] += 1
    return [
        {"id": pid, "name": names.get(pid, pid), "module_count": n}
        for pid, n in sorted(counts.items(), key=lambda x: -x[1])
    ]


@router.get("/programmes/{programme}/outcomes")
def get_programme_outcomes(
    programme: str,
    storage: StorageManager = Depends(get_storage),
) -> list[dict]:
    """The programme-level outcomes ('Learning Outcome' nodes) for a programme."""
    return [
        {"id": p.id, "code": p.code, "title": p.title, "description": p.description}
        for p in storage.get_plos(programme)
    ]


@router.get("/plos/{plo_id}/modules")
def get_plo_modules(
    plo_id: str,
    storage: StorageManager = Depends(get_storage),
) -> list[dict]:
    """All modules that address a given programme-level outcome (interim §2.7.1)."""
    titles = {m.code: m.title for m in storage.get_all_modules()}
    aligns = [a for a in storage.get_plo_alignments() if a.plo_id == plo_id]
    return [
        {"code": a.module_code, "title": titles.get(a.module_code, ""), "score": a.score, "rank": a.rank}
        for a in sorted(aligns, key=lambda x: -x.score)
    ]


@router.get("/plo-coverage")
def plo_coverage(storage: StorageManager = Depends(get_storage)) -> list[dict]:
    """How many modules fulfil each programme outcome (the §2.1.2 outcome×course
    coverage, aggregated per outcome). Uses the universal Computing outcome set."""
    from collections import Counter

    plos = {p.id: p for p in storage.get_plos("beng_computing")}
    counts: Counter = Counter(
        a.plo_id for a in storage.get_plo_alignments() if a.plo_id in plos
    )
    n = len(storage.get_all_modules()) or 1
    return [
        {"plo_id": pid, "code": plos[pid].code, "title": plos[pid].title,
         "module_count": c, "fraction": round(c / n, 4)}
        for pid, c in sorted(counts.items(), key=lambda x: -x[1])
    ]


@router.get("/{code}", response_model=ModuleDetailOut)
def get_module(
    code: str,
    storage: StorageManager = Depends(get_storage),
) -> ModuleDetailOut:
    """Full module detail including ILOs."""
    m = storage.get_module(code.upper())
    if m is None:
        raise HTTPException(status_code=404, detail=f"Module '{code}' not found")
    from curriculum_mapper.api.schemas import ILOOut
    return ModuleDetailOut(
        code=m.code,
        title=m.title,
        level=m.level,
        credits=m.credits,
        prerequisites=m.prerequisites,
        description=m.description,
        description_clean=m.description_clean,
        source=m.source,
        topics=m.topics,
        ilo_count=len(m.ilos),
        ilos=[
            ILOOut(
                id=ilo.id,
                text=ilo.text,
                text_clean=ilo.text_clean,
                bloom_level=ilo.bloom_level,
            )
            for ilo in m.ilos
        ],
    )


@router.get("/{code}/concepts", response_model=list[ConceptOut])
def get_module_concepts(
    code: str,
    min_confidence: float = Query(0.0, ge=0.0, le=1.0),
    storage: StorageManager = Depends(get_storage),
) -> list[ConceptOut]:
    """Concepts extracted for a specific module."""
    code = code.upper()
    if storage.get_module(code) is None:
        raise HTTPException(status_code=404, detail=f"Module '{code}' not found")
    concepts = [
        c for c in storage.get_all_concepts()
        if code in c.module_codes and c.confidence >= min_confidence
    ]
    concepts.sort(key=lambda c: -c.confidence)
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


@router.get("/{code}/alignments")
def get_module_alignments(
    code: str,
    storage: StorageManager = Depends(get_storage),
) -> list[dict]:
    """All alignment results for a module's concepts."""
    code = code.upper()
    if storage.get_module(code) is None:
        raise HTTPException(status_code=404, detail=f"Module '{code}' not found")

    concepts = [c for c in storage.get_all_concepts() if code in c.module_codes]
    concept_id_to_term = {c.id: c.term for c in concepts}
    concept_id_to_modules = {c.id: c.module_codes for c in concepts}
    concept_ids = set(concept_id_to_term.keys())

    alignments = [
        a for a in storage.get_all_alignments()
        if a.concept_id in concept_ids
    ]

    return [
        {
            "id": a.id,
            "concept_id": a.concept_id,
            "concept_term": concept_id_to_term.get(a.concept_id, ""),
            "source_modules": concept_id_to_modules.get(a.concept_id, []),
            "ka_code": a.ka_code,
            "ka_topic": a.ka_topic,
            "method": a.method,
            "score": a.score,
            "rank": a.rank,
            "is_ambiguous": a.is_ambiguous,
            "validated": a.validated,
            "validated_by": a.validated_by,
        }
        for a in sorted(alignments, key=lambda x: (-x.score, x.rank))
    ]


@router.get("/{code}/plos")
def get_module_plos(
    code: str,
    storage: StorageManager = Depends(get_storage),
) -> list[dict]:
    """Programme-level outcomes this module fulfils (interim §2.7.2)."""
    code = code.upper()
    if storage.get_module(code) is None:
        raise HTTPException(status_code=404, detail=f"Module '{code}' not found")
    plos = {p.id: p for p in storage.get_plos()}
    aligns = [a for a in storage.get_plo_alignments() if a.module_code == code and a.plo_id in plos]
    return [
        {
            "plo_id": a.plo_id, "code": plos[a.plo_id].code, "title": plos[a.plo_id].title,
            "description": plos[a.plo_id].description, "programme": plos[a.plo_id].programme,
            "score": a.score, "rank": a.rank,
        }
        for a in sorted(aligns, key=lambda x: x.rank)
    ]


@router.get("/{code}/neighbors")
def get_module_neighbors(
    code: str,
    limit: int = Query(5, ge=1, le=20),
    storage: StorageManager = Depends(get_storage),
) -> list[dict]:
    """Similar modules from the module-module graph, ranked by Jaccard similarity."""
    from curriculum_mapper.api.dependencies import get_graph_module_module
    code = code.upper()
    if storage.get_module(code) is None:
        raise HTTPException(status_code=404, detail=f"Module '{code}' not found")

    G = get_graph_module_module()
    if G is None or code not in G:
        return []

    neighbors = []
    for neighbor in G.neighbors(code):
        edge_data = G[code][neighbor]
        neighbors.append({
            "code": neighbor,
            "weight": edge_data.get("weight", 0.0),
            "type": edge_data.get("type", "similarity"),
            "shared_count": edge_data.get("shared_count", 0),
        })
    neighbors.sort(key=lambda x: -x["weight"])
    return neighbors[:limit]
