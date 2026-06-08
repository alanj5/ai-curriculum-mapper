"""Text normalisation for module descriptors.

Applies: HTML stripping, Unicode normalisation, acronym expansion,
and whitespace collapsing. Does NOT do NLP tokenisation (that is the
preprocessor's job); this step prepares clean raw text.
"""

from __future__ import annotations

import re
import unicodedata

from curriculum_mapper.config import ACRONYM_MAP
from curriculum_mapper.ingestion.schema import ModuleDescriptor

# Pre-compile regex patterns once at import time
_HTML_TAG = re.compile(r"<[^>]+>")
_WHITESPACE = re.compile(r"\s+")
_BULLET_PREFIX = re.compile(r"^[•‣◦⁃∙\*\-\+•]\s*", re.MULTILINE)

# Pedagogical scaffolding that introduces learning-outcome clauses in Imperial
# (and generally, any university) module descriptors. These verb phrases carry no
# technical signal but, in the full official descriptions, dilute concept
# extraction by wrapping every real concept in boilerplate ("...develop an
# understanding of the [main operating system abstractions]..."). Stripping them
# is corpus-independent text hygiene — it removes scaffolding, never content.
_SCAFFOLD = re.compile(
    r"\b(?:"
    r"in this (?:module|course),?\s+you\s+will(?:\s+have\s+the\s+opportunity\s+to|\s+be\s+able\s+to|\s+learn\s+to)?"
    r"|(?:develop|gain|acquire|obtain|demonstrate|build|broaden)\s+(?:a|an|your)?\s*"
    r"(?:deep|thorough|critical|good|basic|sound|comprehensive|solid|broad|working)?\s*"
    r"(?:understanding|knowledge|awareness|appreciation|grasp)\s+of"
    r"|the\s+opportunity\s+to|the\s+ability\s+to|be\s+able\s+to"
    # Clause-initial pedagogical verbs that introduce (rather than name) a concept,
    # stripped only with their following article/qualifier so the concept survives
    # (e.g. "explore the [trade-offs]", "study the different [sub-systems]").
    r"|(?:explore|investigate|examine|study|consider|apply|describe|evaluate|"
    r"appraise|analyse|analyze|assess|recognise|recognize|identify|understand)\s+"
    r"(?:the|a|an|how|why|different|various|your)"
    r")\b[:\s]*",
    re.IGNORECASE,
)

# Build acronym regex: only match whole words (word boundaries)
# Sort by length descending so longer matches take priority (e.g. "IPC" before "IP")
_ACRONYM_PATTERNS: list[tuple[re.Pattern, str]] = [
    (re.compile(r"\b" + re.escape(k) + r"\b"), v)
    for k, v in sorted(ACRONYM_MAP.items(), key=lambda x: -len(x[0]))
]


def _strip_html(text: str) -> str:
    return _HTML_TAG.sub(" ", text)


def _unicode_normalise(text: str) -> str:
    return unicodedata.normalize("NFKC", text)


def _expand_acronyms(text: str) -> str:
    for pattern, expansion in _ACRONYM_PATTERNS:
        text = pattern.sub(expansion, text)
    return text


def _collapse_whitespace(text: str) -> str:
    text = _BULLET_PREFIX.sub("", text)
    return _WHITESPACE.sub(" ", text).strip()


def clean_text(text: str, expand_acronyms: bool = True) -> str:
    """Full cleaning pipeline for a single text string."""
    if not text:
        return ""
    text = _strip_html(text)
    text = _unicode_normalise(text)
    text = _SCAFFOLD.sub(" ", text)
    if expand_acronyms:
        text = _expand_acronyms(text)
    text = _collapse_whitespace(text)
    return text


def normalise_module(module: ModuleDescriptor) -> ModuleDescriptor:
    """Return a new ModuleDescriptor with all clean fields populated.

    The original text fields are preserved; only the *_clean fields are set.
    """
    module.description_clean = clean_text(module.description)
    for ilo in module.ilos:
        ilo.text_clean = clean_text(ilo.text)
    return module
