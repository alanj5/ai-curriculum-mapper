"""Module descriptor loaders for different source formats.

Supports:
  - JSON files (structured module descriptors, including Imperial College format)
  - PDF files (parsed with pdfplumber + regex section extraction)
"""

from __future__ import annotations

import json
import logging
import re
from pathlib import Path
from typing import Optional

import pdfplumber

from curriculum_mapper.config import MODULES_DIR
from curriculum_mapper.ingestion.normalizer import normalise_module
from curriculum_mapper.ingestion.schema import ILO, ModuleDescriptor

logger = logging.getLogger(__name__)

# ── Section header patterns for PDF parsing ────────────────────────────────────

_SECTION_PATTERNS: dict[str, list[re.Pattern]] = {
    "title": [
        re.compile(r"(?i)module\s+title[:\s]+(.+)"),
        re.compile(r"(?i)course\s+title[:\s]+(.+)"),
        re.compile(r"(?i)^title[:\s]+(.+)", re.MULTILINE),
    ],
    "description": [
        re.compile(r"(?i)(?:module\s+)?(?:description|overview|aims?)[:\s]*\n(.+?)(?=\n[A-Z][a-z]|\Z)", re.DOTALL),
        re.compile(r"(?i)(?:synopsis|summary)[:\s]*\n(.+?)(?=\n[A-Z][a-z]|\Z)", re.DOTALL),
    ],
    "ilos": [
        re.compile(r"(?i)(?:intended\s+)?learning\s+outcomes?[:\s]*\n(.+?)(?=\n[A-Z][A-Za-z]|\Z)", re.DOTALL),
        re.compile(r"(?i)(?:course\s+)?objectives?[:\s]*\n(.+?)(?=\n[A-Z][A-Za-z]|\Z)", re.DOTALL),
        re.compile(r"(?i)by\s+the\s+end\s+of\s+this\s+(?:module|course).+?(?:students?\s+(?:will|should|can|are\s+able\s+to)[:\s]*\n)(.+?)(?=\n[A-Z]|\Z)", re.DOTALL),
    ],
    "topics": [
        re.compile(r"(?i)(?:syllabus|topics?|content|curriculum)[:\s]*\n(.+?)(?=\n[A-Z][A-Za-z]|\Z)", re.DOTALL),
    ],
    "prerequisites": [
        re.compile(r"(?i)pre-?requisites?[:\s]+(.+?)(?:\n|$)"),
        re.compile(r"(?i)pre-?requisite\s+modules?[:\s]+(.+?)(?:\n|$)"),
    ],
    "level": [
        re.compile(r"(?i)(?:year|level)[:\s]+(\d)"),
        re.compile(r"(?i)(?:year|level)\s+(\d)"),
    ],
    "credits": [
        re.compile(r"(?i)(?:ects\s+)?credits?[:\s]+(\d+)"),
        re.compile(r"(?i)(\d+)\s+(?:ects\s+)?credits?"),
    ],
}


def _extract_ilo_bullets(text: str) -> list[str]:
    """Split ILO block into individual ILO strings."""
    # Split on numbered lists (1. 2. etc.) or bullet prefixes
    items = re.split(r"\n\s*(?:\d+[.)]\s+|[-•*]\s+)", text.strip())
    result = []
    for item in items:
        item = item.strip()
        if item and len(item) > 15:  # skip fragments
            result.append(item)
    return result


def _extract_topic_bullets(text: str) -> list[str]:
    items = re.split(r"\n\s*(?:\d+[.)]\s+|[-•*]\s+|[,;]\s*)", text.strip())
    result = []
    for item in items:
        item = item.strip().rstrip(",;")
        if item and len(item) > 3:
            result.append(item)
    return result


# ── JSON Loader ────────────────────────────────────────────────────────────────


def load_from_json(path: Path) -> Optional[ModuleDescriptor]:
    """Load a structured JSON module descriptor."""
    try:
        with open(path) as f:
            data = json.load(f)

        ilos_raw = (
            data.get("ilos")
            or data.get("learning_outcomes")
            or data.get("learning_objectives")
            or []
        )
        ilos = [
            ILO(text=ilo if isinstance(ilo, str) else ilo.get("text", ""))
            for ilo in ilos_raw
        ]

        module = ModuleDescriptor(
            code=str(data.get("code", path.stem)).upper(),
            title=data.get("title", data.get("name", "Unknown")),
            level=int(data.get("level", data.get("year", 1))),
            credits=int(data.get("credits", data.get("ects", 0))),
            prerequisites=data.get("prerequisites", []),
            description=data.get("description", data.get("overview", data.get("summary", ""))),
            ilos=ilos,
            topics=data.get("topics", data.get("syllabus", [])),
            source=data.get("source", "institutional"),
            source_file=path.name,
        )
        return normalise_module(module)
    except Exception as e:
        logger.warning(f"Failed to load JSON {path}: {e}")
        return None


# ── PDF Loader ─────────────────────────────────────────────────────────────────


def load_from_pdf(path: Path) -> Optional[ModuleDescriptor]:
    """Extract module descriptor from a PDF using pdfplumber + regex parsing."""
    try:
        with pdfplumber.open(path) as pdf:
            full_text = "\n".join(
                page.extract_text() or "" for page in pdf.pages
            )
    except Exception as e:
        logger.warning(f"Failed to open PDF {path}: {e}")
        return None

    if not full_text.strip():
        logger.warning(f"PDF {path} extracted no text")
        return None

    def _first_match(patterns: list[re.Pattern], default: str = "") -> str:
        for p in patterns:
            m = p.search(full_text)
            if m:
                return m.group(1).strip()
        return default

    # Title: try patterns then fall back to first non-empty line
    title = _first_match(_SECTION_PATTERNS["title"])
    if not title:
        for line in full_text.splitlines():
            line = line.strip()
            if len(line) > 5:
                title = line
                break

    description = _first_match(_SECTION_PATTERNS["description"])
    ilo_text = _first_match(_SECTION_PATTERNS["ilos"])
    topics_text = _first_match(_SECTION_PATTERNS["topics"])
    prereq_text = _first_match(_SECTION_PATTERNS["prerequisites"])
    level_str = _first_match(_SECTION_PATTERNS["level"], "1")
    credits_str = _first_match(_SECTION_PATTERNS["credits"], "0")

    # Infer module code from filename
    code = path.stem.upper()

    ilos = [ILO(text=t) for t in _extract_ilo_bullets(ilo_text)] if ilo_text else []
    topics = _extract_topic_bullets(topics_text) if topics_text else []
    prereqs = [p.strip() for p in re.split(r"[,;]", prereq_text) if p.strip()] if prereq_text else []

    try:
        level = int(re.search(r"\d", level_str).group()) if re.search(r"\d", level_str) else 1
    except Exception:
        level = 1

    try:
        credits = int(re.search(r"\d+", credits_str).group()) if re.search(r"\d+", credits_str) else 0
    except Exception:
        credits = 0

    if not description and not ilos:
        # Fallback: use first 1000 chars as description
        description = full_text[:1000]

    module = ModuleDescriptor(
        code=code,
        title=title or path.stem,
        level=level,
        credits=credits,
        prerequisites=prereqs,
        description=description,
        ilos=ilos,
        topics=topics,
        source="institutional",
        source_file=path.name,
    )
    return normalise_module(module)


# ── Legacy OCW JSON Loader (kept for test coverage) ───────────────────────────


def load_from_ocw_json(path: Path) -> Optional[ModuleDescriptor]:
    """Legacy loader — no longer used for primary data ingestion."""
    try:
        with open(path) as f:
            data = json.load(f)

        description = data.get("description", "")
        ilos_raw = data.get("learning_objectives", [])
        topics_raw = data.get("topics", [])

        if not description and not ilos_raw:
            return None

        ilos = [ILO(text=t) for t in ilos_raw if isinstance(t, str) and t.strip()]
        # Flatten nested topic lists from OCW format
        topics: list[str] = []
        for t in topics_raw:
            if isinstance(t, str):
                topics.append(t)
            elif isinstance(t, list):
                topics.extend(str(x) for x in t if x)

        module = ModuleDescriptor(
            code=data.get("code", path.stem).upper(),
            title=data.get("title", "Unknown"),
            level=int(data.get("level", 2)),
            credits=int(data.get("credits", 12)),
            prerequisites=data.get("prerequisites", []),
            description=description,
            ilos=ilos,
            topics=topics,
            source="mit_ocw",
            source_file=path.name,
        )
        return normalise_module(module)
    except Exception as e:
        logger.warning(f"Failed to load OCW JSON {path}: {e}")
        return None


# ── Batch Loader ───────────────────────────────────────────────────────────────


def load_all_modules(modules_dir: Path = MODULES_DIR) -> list[ModuleDescriptor]:
    """Load all modules from the modules directory, auto-detecting format."""
    modules: list[ModuleDescriptor] = []

    for path in sorted(modules_dir.rglob("*.json")):
        module = load_from_json(path)
        if module:
            modules.append(module)
            logger.info(f"Loaded JSON: {module.code} — {module.title}")

    for path in sorted(modules_dir.rglob("*.pdf")):
        module = load_from_pdf(path)
        if module:
            modules.append(module)
            logger.info(f"Loaded PDF: {module.code} — {module.title}")

    # Remove duplicates by code (keep last loaded)
    seen: dict[str, ModuleDescriptor] = {}
    for m in modules:
        seen[m.code] = m

    result = list(seen.values())
    logger.info(f"Total modules loaded: {len(result)}")
    return result
