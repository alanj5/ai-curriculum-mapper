"""Live fetch + parse of Imperial Computing module descriptor pages.

The Department of Computing publishes a descriptor page per module at
  https://www.imperial.ac.uk/computing/current-students/courses/<numeric-code>/
(e.g. internal code ``IC40001`` -> ``.../courses/40001/``). These pages are
*server-rendered static HTML* with a stable heading structure::

    <h1> 40001
    <h2> Introduction to Computer Systems
    <h3> Module aims          -> description (a <p>)
    <h3> Learning outcomes    -> ILOs (a <p> with <br>-separated "- " bullets)
    <h3> Module syllabus      -> topics (a <ul><li> list)
    <h3> Teaching methods / Assessments / Reading list / Module leaders

This module provides:
  * :func:`build_source_url`     internal code -> descriptor URL
  * :func:`parse_descriptor_html`  pure HTML -> :class:`ParsedDescriptor`
  * :func:`fetch_descriptor`     network fetch + provenance (URL, timestamp,
                                 HTTP status, SHA-256 of the body)

Level, credits and prerequisites are *not* published on the descriptor pages,
so the re-runnable CLI (``scripts/fetch_imperial_modules.py``) supplies those
from the curated module table and keeps the reviewed description/outcomes/topics
as the source of record, using the live fetch to attach provenance and to flag
drift between the live page and the reviewed content.

The parser is deliberately network-free so it can be unit-tested against saved
HTML fixtures (no live calls in CI).
"""

from __future__ import annotations

import hashlib
import logging
import re
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Optional

from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

BASE_URL = "https://www.imperial.ac.uk/computing/current-students/courses/{code}/"
DEFAULT_TIMEOUT = 30
USER_AGENT = "ai-curriculum-mapper/1.0 (Imperial BEng FYP; research use)"

# Section headings on the descriptor page, with tolerant aliases.
_AIMS_HEADINGS = ("module aims", "module description", "aims", "description")
_OUTCOME_HEADINGS = ("learning outcomes", "intended learning outcomes", "learning objectives")
_SYLLABUS_HEADINGS = ("module syllabus", "syllabus", "module content", "content")
_PREREQ_HEADINGS = ("pre-requisites", "prerequisites", "pre requisites", "pre-requisite", "prerequisite")

# Module codes appear in prerequisite prose as e.g. "COMP50002" or "50002"; the
# Department uses COMP/numeric codes on the descriptor pages but our internal
# codes are IC-prefixed (COMP50002 -> IC50002).
_CODE_RE = re.compile(r"\b(?:COMP|IC)?\s?([4-7]\d{4})\b")


def _extract_module_codes(text: str) -> list[str]:
    """Pull internal module codes (IC#####) out of free-text prerequisites."""
    out, seen = [], set()
    for m in _CODE_RE.finditer(text or ""):
        code = "IC" + m.group(1)
        if code not in seen:
            seen.add(code)
            out.append(code)
    return out


def build_source_url(code: str) -> str:
    """Map an internal module code (e.g. ``IC40001``) to its descriptor URL."""
    numeric = code.upper().removeprefix("IC")
    return BASE_URL.format(code=numeric)


# ── HTML parsing helpers ─────────────────────────────────────────────────────


def _find_heading(soup: BeautifulSoup, headings: tuple[str, ...]):
    wanted = {h.lower() for h in headings}
    for h in soup.find_all(["h2", "h3"]):
        if h.get_text(strip=True).lower() in wanted:
            return h
    return None


def _siblings_until_next_heading(heading):
    for sib in heading.find_next_siblings():
        if getattr(sib, "name", None) in ("h2", "h3"):
            break
        yield sib


def _bulleted_paragraph(p) -> list[str]:
    """Split a <p> whose lines are <br>-separated ``- `` bullets into items.

    The first line is usually a lead-in ("Upon successful completion ... able
    to:") which ends in a colon and is dropped.
    """
    items: list[str] = []
    for line in p.get_text("\n", strip=True).split("\n"):
        line = line.strip()
        if not line or line.endswith(":"):
            continue
        line = line.lstrip("-–•*• ").strip()
        if len(line) > 3:
            items.append(line)
    return items


def _section_paragraph(soup: BeautifulSoup, headings: tuple[str, ...]) -> str:
    h = _find_heading(soup, headings)
    if not h:
        return ""
    parts: list[str] = []
    for sib in _siblings_until_next_heading(h):
        if getattr(sib, "name", None) in ("p", "div"):
            text = sib.get_text(" ", strip=True)
            if text:
                parts.append(text)
    return " ".join(parts).strip()


def _section_items(soup: BeautifulSoup, headings: tuple[str, ...]) -> list[str]:
    """Extract list items, handling both ``<ul><li>`` and ``<br>``-bulleted ``<p>``."""
    h = _find_heading(soup, headings)
    if not h:
        return []
    items: list[str] = []
    for sib in _siblings_until_next_heading(h):
        name = getattr(sib, "name", None)
        if name in ("ul", "ol"):
            items += [li.get_text(" ", strip=True) for li in sib.find_all("li")]
        elif name == "p":
            items += _bulleted_paragraph(sib)
    # de-duplicate while preserving order, drop fragments
    seen: set[str] = set()
    out: list[str] = []
    for it in (x.strip() for x in items):
        if len(it) > 3 and it.lower() not in seen:
            seen.add(it.lower())
            out.append(it)
    return out


@dataclass
class ParsedDescriptor:
    """Descriptor fields parsed out of a course page (network-free)."""

    code: Optional[str] = None
    title: Optional[str] = None
    description: str = ""
    learning_objectives: list[str] = field(default_factory=list)
    topics: list[str] = field(default_factory=list)
    prerequisites: list[str] = field(default_factory=list)  # module codes (IC#####)
    prerequisites_text: str = ""                            # the published prose, verbatim

    @property
    def is_empty(self) -> bool:
        return not (self.description or self.learning_objectives or self.topics)


def parse_descriptor_html(html: str) -> ParsedDescriptor:
    """Parse a module descriptor page's HTML into structured fields."""
    soup = BeautifulSoup(html, "html.parser")
    h1 = soup.find("h1")
    code = h1.get_text(strip=True) if h1 else None
    title = None
    if h1:
        h2 = h1.find_next("h2")
        if h2:
            title = h2.get_text(strip=True)
    prereq_text = _section_paragraph(soup, _PREREQ_HEADINGS)
    return ParsedDescriptor(
        code=code,
        title=title,
        description=_section_paragraph(soup, _AIMS_HEADINGS),
        learning_objectives=_section_items(soup, _OUTCOME_HEADINGS),
        topics=_section_items(soup, _SYLLABUS_HEADINGS),
        prerequisites=_extract_module_codes(prereq_text),
        prerequisites_text=prereq_text,
    )


# ── Network fetch + provenance ───────────────────────────────────────────────


@dataclass
class FetchResult:
    """Outcome of fetching one descriptor page, with provenance."""

    code: str
    source_url: str
    fetched_at: str  # ISO-8601 UTC
    http_status: Optional[int] = None
    content_sha256: Optional[str] = None
    ok: bool = False
    error: Optional[str] = None
    parsed: Optional[ParsedDescriptor] = None


def fetch_descriptor(
    code: str,
    *,
    session: Any = None,
    timeout: int = DEFAULT_TIMEOUT,
    retries: int = 2,
    backoff: float = 1.5,
) -> FetchResult:
    """Fetch one descriptor page; always returns a result carrying provenance.

    Records the source URL, fetch timestamp, HTTP status and SHA-256 of the
    response body even on failure. On a 200 with a non-empty body the page is
    parsed; otherwise ``ok`` is ``False`` and ``parsed`` is ``None``.
    """
    import requests  # local import keeps the parser importable without requests

    url = build_source_url(code)
    fetched_at = datetime.now(timezone.utc).isoformat()
    sess = session or requests.Session()
    result = FetchResult(code=code, source_url=url, fetched_at=fetched_at)

    for attempt in range(retries + 1):
        try:
            resp = sess.get(url, timeout=timeout, headers={"User-Agent": USER_AGENT})
            result.http_status = resp.status_code
            result.content_sha256 = hashlib.sha256(resp.content).hexdigest()
            if resp.status_code == 200 and resp.text.strip():
                result.parsed = parse_descriptor_html(resp.text)
                result.ok = True
                return result
            result.error = f"HTTP {resp.status_code}"
        except Exception as exc:  # network error / timeout
            result.error = str(exc)
            logger.warning("Fetch failed for %s (%s): %s", code, url, exc)
        if attempt < retries:
            time.sleep(backoff * (attempt + 1))
    return result
