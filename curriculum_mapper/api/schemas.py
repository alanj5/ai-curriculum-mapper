"""Pydantic response schemas for the API layer.

These are separate from ingestion/schema.py models — they define the
exact JSON shapes returned by the API and can differ from storage models
(e.g. flattening nested objects for easier frontend consumption).
"""

from __future__ import annotations

from typing import Any, Optional

from pydantic import BaseModel

# ── Modules ────────────────────────────────────────────────────────────────────

class ILOOut(BaseModel):
    id: str
    text: str
    text_clean: str
    bloom_level: Optional[str] = None


class ModuleOut(BaseModel):
    code: str
    title: str
    level: int
    credits: int
    prerequisites: list[str]
    description: str
    source: str
    programmes: list[str] = []
    topics: list[str]
    ilo_count: int


class ModuleDetailOut(ModuleOut):
    description_clean: str
    ilos: list[ILOOut]


# ── Concepts ──────────────────────────────────────────────────────────────────

class ConceptOut(BaseModel):
    id: str
    term: str
    variants: list[str]
    confidence: float
    extractors: list[str]
    module_codes: list[str]


# ── Alignments ────────────────────────────────────────────────────────────────

class AlignmentOut(BaseModel):
    id: str
    concept_id: str
    concept_term: Optional[str] = None   # joined from concepts table
    ka_code: str
    ka_topic: str
    method: str
    score: float
    rank: int
    is_ambiguous: bool
    validated: Optional[bool]
    validated_by: Optional[str]


class ValidateRequest(BaseModel):
    action: str                      # "accept" | "reject" | "reassign"
    new_ka_code: Optional[str] = None
    comment: Optional[str] = None
    validated_by: Optional[str] = "user"


class AlignmentStatsOut(BaseModel):
    total: int
    by_ka: dict[str, int]
    by_method: dict[str, int]
    validated_count: int
    ambiguous_count: int
    accepted_count: int
    rejected_count: int


# ── Graph ─────────────────────────────────────────────────────────────────────

class CytoscapeNode(BaseModel):
    data: dict[str, Any]


class CytoscapeEdge(BaseModel):
    data: dict[str, Any]


class CytoscapeGraph(BaseModel):
    nodes: list[CytoscapeNode]
    edges: list[CytoscapeEdge]


class CommunityOut(BaseModel):
    communities: dict[str, int]


class CentralityOut(BaseModel):
    centrality: dict[str, dict[str, float]]


# ── Reports ───────────────────────────────────────────────────────────────────

class KACoverageItem(BaseModel):
    ka_code: str
    ka_name: str
    coverage: float
    module_count: int
    severity: str    # "good" | "warning" | "critical"


class GapItem(BaseModel):
    ka_code: str
    ka_name: str
    coverage: float
    severity: str


class RedundancyItem(BaseModel):
    concept: str
    module_count: int
    modules: list[str]
    confidence: float


class SummaryOut(BaseModel):
    total_modules: int
    total_concepts: int
    total_alignments: int
    validated_count: int
    ambiguous_count: int
    ka_coverage_fraction: float
    covered_kas: int
    total_kas: int
    gap_count: int
    critical_gap_count: int
    redundancy_count: int
    top_gaps: list[GapItem]
    top_redundancies: list[RedundancyItem]
