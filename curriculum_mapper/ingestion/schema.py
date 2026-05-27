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
    source: str  # "institutional" | "imperial"
    source_file: str
    ingested_at: datetime = Field(default_factory=datetime.utcnow)

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
