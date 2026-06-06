"""Tests for the live Imperial descriptor scraper.

The HTML parser is network-free and tested against a saved fixture that mirrors
the real page structure (``<br>``-bulleted learning outcomes + ``<ul>``
syllabus). The network layer is exercised with a stubbed session so CI never
makes a live call.
"""

from __future__ import annotations

import hashlib
from pathlib import Path

from curriculum_mapper.ingestion.imperial_scraper import (
    build_source_url,
    fetch_descriptor,
    parse_descriptor_html,
)

FIXTURE = Path(__file__).parent.parent / "fixtures" / "imperial_descriptor_sample.html"


def _html() -> str:
    return FIXTURE.read_text()


# ── URL construction ─────────────────────────────────────────────────────────


class TestSourceUrl:
    def test_strips_ic_prefix(self):
        assert build_source_url("IC40001") == (
            "https://www.imperial.ac.uk/computing/current-students/courses/40001/"
        )

    def test_case_insensitive(self):
        assert build_source_url("ic60005").endswith("/courses/60005/")


# ── HTML parsing ─────────────────────────────────────────────────────────────


class TestParseDescriptor:
    def test_code_and_title(self):
        p = parse_descriptor_html(_html())
        assert p.code == "40001"
        assert p.title == "Introduction to Computer Systems"

    def test_description_from_aims(self):
        p = parse_descriptor_html(_html())
        assert p.description.startswith("In this module you will study")
        # must not bleed into later sections
        assert "first principles" not in p.description

    def test_outcomes_from_br_bulleted_paragraph(self):
        p = parse_descriptor_html(_html())
        assert len(p.learning_objectives) == 3
        # the colon lead-in line is dropped
        assert not any(o.endswith(":") for o in p.learning_objectives)
        assert p.learning_objectives[0].startswith("Explain combinatorial")

    def test_topics_from_unordered_list(self):
        p = parse_descriptor_html(_html())
        assert p.topics == [
            "Number representations and computer arithmetic",
            "Boolean algebra",
            "Combinatorial logic functions",
            "Finite state machines",
        ]

    def test_parsing_is_deterministic(self):
        assert parse_descriptor_html(_html()) == parse_descriptor_html(_html())

    def test_empty_html_yields_empty_descriptor(self):
        p = parse_descriptor_html("<html><body><p>nothing</p></body></html>")
        assert p.is_empty


# ── Network layer (stubbed) ──────────────────────────────────────────────────


class _StubResponse:
    def __init__(self, status_code: int, text: str):
        self.status_code = status_code
        self.text = text
        self.content = text.encode()


class _StubSession:
    def __init__(self, response):
        self._response = response
        self.calls: list[str] = []

    def get(self, url, timeout=None, headers=None):
        self.calls.append(url)
        return self._response


class TestFetchProvenance:
    def test_successful_fetch_records_provenance(self):
        html = _html()
        sess = _StubSession(_StubResponse(200, html))
        result = fetch_descriptor("IC40001", session=sess)
        assert result.ok is True
        assert result.http_status == 200
        assert result.source_url.endswith("/courses/40001/")
        assert result.content_sha256 == hashlib.sha256(html.encode()).hexdigest()
        assert result.fetched_at  # ISO timestamp present
        assert result.parsed is not None and result.parsed.code == "40001"

    def test_404_falls_back_without_parse(self):
        sess = _StubSession(_StubResponse(404, "Not Found"))
        result = fetch_descriptor("IC60036", session=sess, retries=0)
        assert result.ok is False
        assert result.http_status == 404
        assert result.parsed is None
        # provenance still captured for the failed attempt
        assert result.content_sha256 is not None
        assert result.error == "HTTP 404"
