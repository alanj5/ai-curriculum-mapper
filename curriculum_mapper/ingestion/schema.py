"""Pydantic v2 data models — canonical types throughout the pipeline."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


def _uuid() -> str:
    return str(uuid.uuid4())


class ILO(BaseModel):
    """Intended Learning Outcome for a single module."""

    id: str = Field(default_factory=_uuid)
    text: str
    text_clean: str = ""
    bloom_level: Optional[str] = None  # Bloom's taxonomy verb (optional)


class ModuleDescriptor(BaseModel):
    """Canonical representation of a computing module."""

    code: str
    title: str
    level: int  # UG year: 1–4
    credits: int
    prerequisites: list[str] = Field(default_factory=list)
    description: str
    description_clean: str = ""
    ilos: list[ILO] = Field(default_factory=list)
    topics: list[str] = Field(default_factory=list)  # explicit topic lists
    source: str  # institution: "imperial" | "mit_ocw" | "institutional"
    programmes: list[str] = Field(
        default_factory=lambda: ["beng_computing"]
    )  # degree programmes this module belongs to (filter-by-programme)
    source_file: str
    ingested_at: datetime = Field(default_factory=datetime.utcnow)
    # ── Acquisition provenance (set by the live refetch scraper) ──────────────
    source_url: Optional[str] = None  # descriptor page the content was fetched from
    fetched_at: Optional[datetime] = None  # when the live page was retrieved
    content_sha256: Optional[str] = None  # SHA-256 of the fetched page body

    @property
    def full_text(self) -> str:
        """Concatenation of description and all ILO texts."""
        parts = [self.description]
        parts.extend(ilo.text for ilo in self.ilos)
        parts.extend(self.topics)
        return " ".join(p for p in parts if p)

    @property
    def full_text_clean(self) -> str:
        parts = [self.description_clean]
        parts.extend(ilo.text_clean for ilo in self.ilos)
        # Include the official syllabus topics: they name specific technical
        # concepts (e.g. "lambda calculus", "minimum spanning trees") that the
        # prose description and ILOs sometimes state only obliquely. On the gold
        # modules, appending them measurably lifts end-to-end KA Coverage@1
        # (0.196 -> 0.326; see evaluation, concept extraction).
        parts.extend(self.topics)
        return " ".join(p for p in parts if p)


class Concept(BaseModel):
    """A normalised concept extracted from module content."""

    id: str = Field(default_factory=_uuid)
    term: str  # canonical lowercased lemmatized form
    variants: list[str] = Field(default_factory=list)
    confidence: float
    extractors: list[str]  # which extractors contributed
    module_codes: list[str]  # modules this concept appears in


class KnowledgeArea(BaseModel):
    """ACM/IEEE CS2023 Knowledge Area."""

    code: str  # e.g. "AL"
    name: str  # e.g. "Algorithms and Complexity"
    topics: list[str]  # topic strings from CS2023 body of knowledge


class AlignmentResult(BaseModel):
    """Alignment of a Concept to a CS2023 KA topic."""

    id: str = Field(default_factory=_uuid)
    concept_id: str
    ka_code: str
    ka_topic: str
    method: str  # "lexical" | "semantic" | "hybrid"
    score: float  # [0, 1]
    rank: int  # 1 = best match for this concept
    is_ambiguous: bool = False
    validated: Optional[bool] = None  # None=unvalidated, True=accepted, False=rejected
    validated_by: Optional[str] = None
    validated_at: Optional[datetime] = None


class ConceptPrerequisite(BaseModel):
    """A directed prerequisite edge between two concepts (from -> to).

    ``from_concept_id`` is a prerequisite of ``to_concept_id``: it is introduced
    at a lower curriculum level and the two are related. Edges are derived by a
    DAG-safe metadata heuristic (see ``graph/concept_prerequisite.py``).
    """

    id: str = Field(default_factory=_uuid)
    from_concept_id: str  # the prerequisite concept (lower level)
    to_concept_id: str  # the dependent concept (higher level)
    confidence: float  # [0, 1] relatedness strength
    method: str  # "shared_module" | "same_ka" | "sbert"
    inferred: bool = True  # heuristic (True) vs explicit metadata (False)


class ProgrammeLearningOutcome(BaseModel):
    """A programme-level learning outcome (the interim's 'Learning Outcome' node)."""

    id: str = Field(default_factory=_uuid)
    programme: str  # e.g. "beng_computing", "meng_computing", "mit_ocw_cs"
    code: str  # e.g. "PLO-A1"
    title: str
    description: str


class PLOAlignment(BaseModel):
    """Alignment of a module to a programme-level outcome it fulfils."""

    id: str = Field(default_factory=_uuid)
    module_code: str
    plo_id: str
    method: str  # "lexical" | "semantic" | "hybrid"
    score: float  # [0, 1]
    rank: int  # 1 = best-matching PLO for this module
