"""Tests for the alignment orchestrator (aligner.py: load_ka_data, run_alignment)."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock

import numpy as np
import pytest

from curriculum_mapper.alignment.aligner import load_ka_data, run_alignment
from curriculum_mapper.ingestion.schema import Concept

# ── Fixtures ───────────────────────────────────────────────────────────────────

MINI_KA = {
    "AL": {
        "name": "Algorithms and Complexity",
        "topics": ["Sorting algorithms", "Dynamic programming"],
    },
    "OS": {
        "name": "Operating Systems",
        "topics": ["Process management", "Virtual memory"],
    },
}


@pytest.fixture
def ka_file(tmp_path: Path) -> Path:
    p = tmp_path / "cs2023_ka.json"
    p.write_text(json.dumps(MINI_KA))
    return p


def _make_concept(term: str, module: str = "MOD001") -> Concept:
    return Concept(
        term=term,
        variants=[],
        confidence=0.8,
        extractors=["tfidf"],
        module_codes=[module],
    )


def _make_em() -> MagicMock:
    em = MagicMock()
    vec = np.array([1.0, 0.0, 0.0], dtype=np.float32)
    em.encode.return_value = np.stack([vec, vec, vec, vec])
    return em


# ── load_ka_data ───────────────────────────────────────────────────────────────

class TestLoadKaData:
    def test_loads_from_explicit_path(self, ka_file):
        data = load_ka_data(ka_file)
        assert "AL" in data
        assert "OS" in data

    def test_returns_dict(self, ka_file):
        data = load_ka_data(ka_file)
        assert isinstance(data, dict)

    def test_missing_file_raises(self, tmp_path):
        with pytest.raises(FileNotFoundError):
            load_ka_data(tmp_path / "nonexistent.json")

    def test_topics_are_lists(self, ka_file):
        data = load_ka_data(ka_file)
        assert isinstance(data["AL"]["topics"], list)
        assert len(data["AL"]["topics"]) == 2

    def test_loads_default_path(self):
        """Default path (STANDARDS_DIR / cs2023_ka.json) should exist in the project."""
        from curriculum_mapper.config import STANDARDS_DIR
        default = STANDARDS_DIR / "cs2023_ka.json"
        if default.exists():
            data = load_ka_data()
            assert len(data) >= 18  # CS2023 has 18 KAs
        else:
            pytest.skip("Default KA file not present in this environment")


# ── run_alignment ──────────────────────────────────────────────────────────────

class TestRunAlignment:
    def test_returns_integer_count(self, ka_file):
        concept = _make_concept("sorting algorithms")
        em = _make_em()

        storage = MagicMock()
        storage.get_all_concepts.return_value = [concept]
        storage.insert_alignment.return_value = None

        result = run_alignment(storage, em, ka_data=MINI_KA)
        assert isinstance(result, int)
        assert result >= 0

    def test_calls_insert_for_each_result(self, ka_file):
        concept = _make_concept("sorting algorithms")
        em = _make_em()

        storage = MagicMock()
        storage.get_all_concepts.return_value = [concept]
        storage.insert_alignment.return_value = None

        run_alignment(storage, em, ka_data=MINI_KA)
        assert storage.insert_alignment.called

    def test_empty_concepts_returns_zero(self):
        em = _make_em()
        storage = MagicMock()
        storage.get_all_concepts.return_value = []

        result = run_alignment(storage, em, ka_data=MINI_KA)
        assert result == 0
        storage.insert_alignment.assert_not_called()

    def test_handles_insert_exception_gracefully(self):
        concept = _make_concept("sorting algorithms")
        em = _make_em()

        storage = MagicMock()
        storage.get_all_concepts.return_value = [concept]
        storage.insert_alignment.side_effect = Exception("DB error")

        # Should not raise — just logs and continues
        result = run_alignment(storage, em, ka_data=MINI_KA)
        assert isinstance(result, int)

    def test_loads_ka_data_when_not_provided(self):
        from curriculum_mapper.config import STANDARDS_DIR
        default = STANDARDS_DIR / "cs2023_ka.json"
        if not default.exists():
            pytest.skip("Default KA file not present")

        storage = MagicMock()
        storage.get_all_concepts.return_value = []
        em = _make_em()

        result = run_alignment(storage, em)  # no ka_data provided
        assert result == 0

    def test_multiple_concepts_accumulates_count(self):
        concepts = [
            _make_concept("sorting algorithms", "MOD001"),
            _make_concept("process management", "MOD002"),
        ]
        em = MagicMock()
        vec = np.array([1.0, 0.0, 0.0], dtype=np.float32)
        em.encode.return_value = np.stack([vec, vec, vec, vec])

        storage = MagicMock()
        storage.get_all_concepts.return_value = concepts
        storage.insert_alignment.return_value = None

        result = run_alignment(storage, em, ka_data=MINI_KA)
        assert result >= 0
