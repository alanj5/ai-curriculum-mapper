"""Tests for loading Imperial College module descriptors.

Validates that the loader correctly handles the Imperial JSON format
(using 'learning_objectives' key instead of 'ilos') and that the
34 Imperial module files load cleanly.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from curriculum_mapper.ingestion.loader import load_all_modules, load_from_json

IMPERIAL_DIR = (
    Path(__file__).parent.parent.parent
    / "data" / "raw" / "modules" / "imperial"
)

# ── Helpers ─────────────────────────────────────────────────────────────────


def _imperial_file(code: str) -> Path:
    return IMPERIAL_DIR / f"{code}.json"


# ── loading_objectives key ──────────────────────────────────────────────────


class TestImperialJsonFormat:
    """The Imperial JSONs use 'learning_objectives' not 'ilos'."""

    def test_learning_objectives_mapped_to_ilos(self, tmp_path):
        data = {
            "code": "IC50004",
            "title": "Operating Systems",
            "level": 2,
            "credits": 8,
            "prerequisites": [],
            "description": "Core OS concepts: processes, virtual memory, scheduling.",
            "learning_objectives": [
                "Explain process and thread abstractions",
                "Describe virtual memory and paging",
                "Identify deadlock and race conditions",
            ],
            "topics": ["Processes", "Virtual memory", "Scheduling"],
            "source": "imperial",
        }
        path = tmp_path / "IC50004.json"
        with open(path, "w") as f:
            json.dump(data, f)

        module = load_from_json(path)
        assert module is not None
        assert len(module.ilos) == 3
        assert "Explain process and thread abstractions" in module.ilos[0].text

    def test_source_preserved_as_imperial(self, tmp_path):
        data = {
            "code": "IC40001",
            "title": "Intro to Computer Systems",
            "level": 1,
            "credits": 8,
            "prerequisites": [],
            "description": "Digital logic and CPU design.",
            "learning_objectives": ["Design a CPU"],
            "topics": ["Boolean algebra", "CPU design"],
            "source": "imperial",
        }
        path = tmp_path / "IC40001.json"
        with open(path, "w") as f:
            json.dump(data, f)
        module = load_from_json(path)
        assert module.source == "imperial"

    def test_empty_prerequisites_defaults_to_empty_list(self, tmp_path):
        data = {
            "code": "IC40007",
            "title": "Introduction to Databases",
            "level": 1,
            "credits": 8,
            "description": "Relational model, SQL, normalisation.",
            "learning_objectives": ["Write SQL queries"],
            "topics": ["SQL", "Relational model"],
            "source": "imperial",
        }
        path = tmp_path / "IC40007.json"
        with open(path, "w") as f:
            json.dump(data, f)
        module = load_from_json(path)
        assert module.prerequisites == []

    def test_missing_prerequisites_key_handled(self, tmp_path):
        """No 'prerequisites' key in JSON must not crash the loader."""
        data = {
            "code": "IC99999",
            "title": "Test Module",
            "level": 1,
            "credits": 8,
            "description": "A test module with no prerequisites field.",
            "learning_objectives": ["Do something"],
            "topics": ["Topic A"],
            "source": "imperial",
        }
        path = tmp_path / "IC99999.json"
        with open(path, "w") as f:
            json.dump(data, f)
        module = load_from_json(path)
        assert module is not None
        assert module.prerequisites == []


# ── Real Imperial file loading ──────────────────────────────────────────────


@pytest.mark.skipif(
    not IMPERIAL_DIR.exists(),
    reason="Imperial module files not present (run create_imperial_modules.py first)",
)
class TestImperialFilesLoad:
    def test_all_imperial_files_present(self):
        json_files = list(IMPERIAL_DIR.glob("*.json"))
        assert len(json_files) == 34, (
            f"Expected 34 Imperial module files, found {len(json_files)}"
        )

    def test_all_imperial_modules_load_without_error(self):
        failed = []
        for path in sorted(IMPERIAL_DIR.glob("*.json")):
            module = load_from_json(path)
            if module is None:
                failed.append(path.name)
        assert not failed, f"Failed to load: {failed}"

    def test_all_modules_have_description(self):
        for path in sorted(IMPERIAL_DIR.glob("*.json")):
            module = load_from_json(path)
            assert module is not None
            assert module.description.strip(), f"{path.name} has empty description"

    def test_all_modules_have_ilos(self):
        for path in sorted(IMPERIAL_DIR.glob("*.json")):
            module = load_from_json(path)
            assert module is not None
            assert len(module.ilos) > 0, f"{path.name} has no ILOs"

    def test_all_modules_have_topics(self):
        for path in sorted(IMPERIAL_DIR.glob("*.json")):
            module = load_from_json(path)
            assert module is not None
            assert len(module.topics) > 0, f"{path.name} has no topics"

    def test_level_values_are_valid(self):
        """All Imperial modules should have level 1, 2, or 3."""
        for path in sorted(IMPERIAL_DIR.glob("*.json")):
            module = load_from_json(path)
            assert module is not None
            assert module.level in (1, 2, 3), (
                f"{path.name} has unexpected level {module.level}"
            )

    def test_year1_modules_have_level_1(self):
        """Modules with 40xxx codes (Year 1) should have level=1."""
        year1_codes = [
            "IC40001", "IC40005", "IC40007", "IC40008",
            "IC40009", "IC40016", "IC40017", "IC40018",
        ]
        for code in year1_codes:
            path = _imperial_file(code)
            if path.exists():
                module = load_from_json(path)
                assert module is not None
                assert module.level == 1, f"{code} should be level 1, got {module.level}"

    def test_year2_modules_have_level_2(self):
        """Modules with 50xxx codes (Year 2) should have level=2."""
        year2_codes = [
            "IC50001", "IC50002", "IC50003", "IC50004",
            "IC50005", "IC50008", "IC50009", "IC50010", "IC50013",
        ]
        for code in year2_codes:
            path = _imperial_file(code)
            if path.exists():
                module = load_from_json(path)
                assert module is not None
                assert module.level == 2, f"{code} should be level 2, got {module.level}"

    def test_year4_modules_have_level_3(self):
        """Modules with 60xxx codes (Year 4) should have level=3."""
        for code in ["IC60001", "IC60007"]:
            path = _imperial_file(code)
            if path.exists():
                module = load_from_json(path)
                assert module is not None
                assert module.level == 3, f"{code} should be level 3, got {module.level}"

    def test_os_module_has_expected_topics(self):
        path = _imperial_file("IC50004")
        module = load_from_json(path)
        assert module is not None
        topics_lower = [t.lower() for t in module.topics]
        combined = " ".join(topics_lower)
        assert any(kw in combined for kw in ["process", "thread", "scheduling", "memory"]), (
            f"IC50004 topics don't cover expected OS concepts: {module.topics}"
        )

    def test_algorithms_module_has_expected_topics(self):
        path = _imperial_file("IC50001")
        module = load_from_json(path)
        assert module is not None
        combined = " ".join(module.topics).lower()
        assert any(kw in combined for kw in ["algorithm", "dynamic", "greedy", "graph"]), (
            f"IC50001 topics don't cover expected algorithm concepts: {module.topics}"
        )

    def test_description_clean_populated(self):
        """Normaliser should have run and populated description_clean."""
        for path in sorted(IMPERIAL_DIR.glob("*.json")):
            module = load_from_json(path)
            assert module is not None
            assert module.description_clean, f"{path.name} has empty description_clean"

    def test_ilo_text_clean_populated(self):
        """Normaliser should have run and populated each ilo.text_clean."""
        for path in sorted(IMPERIAL_DIR.glob("*.json")):
            module = load_from_json(path)
            assert module is not None
            for ilo in module.ilos:
                assert ilo.text_clean, (
                    f"{path.name} has an ILO with empty text_clean: '{ilo.text}'"
                )


@pytest.mark.skipif(
    not IMPERIAL_DIR.exists(),
    reason="Imperial module files not present",
)
class TestLoadAllImperialModules:
    def test_load_all_returns_all_modules(self):
        modules = load_all_modules(IMPERIAL_DIR)
        assert len(modules) == 34

    def test_no_duplicate_codes(self):
        modules = load_all_modules(IMPERIAL_DIR)
        codes = [m.code for m in modules]
        assert len(codes) == len(set(codes)), f"Duplicate codes: {codes}"

    def test_all_sources_are_imperial(self):
        modules = load_all_modules(IMPERIAL_DIR)
        # One module (IC60036) carries a provenance note appended to "imperial"
        # because its descriptor page was unavailable; accept the prefix.
        non_imperial = [m.code for m in modules if not m.source.startswith("imperial")]
        assert not non_imperial, f"Non-imperial sources: {non_imperial}"

    def test_full_text_property_non_empty(self):
        modules = load_all_modules(IMPERIAL_DIR)
        for m in modules:
            assert m.full_text.strip(), f"{m.code} has empty full_text"

    def test_full_text_clean_property_non_empty(self):
        modules = load_all_modules(IMPERIAL_DIR)
        for m in modules:
            assert m.full_text_clean.strip(), f"{m.code} has empty full_text_clean"
