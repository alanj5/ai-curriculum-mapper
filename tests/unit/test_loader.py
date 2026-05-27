"""Unit tests for ingestion.loader."""

import json

from curriculum_mapper.ingestion.loader import (
    load_all_modules,
    load_from_json,
    load_from_ocw_json,
)


class TestLoadFromJson:
    def test_loads_valid_json(self, tmp_path, sample_module_data):
        path = tmp_path / "TEST101.json"
        with open(path, "w") as f:
            json.dump(sample_module_data, f)

        module = load_from_json(path)
        assert module is not None
        assert module.code == "TEST101"
        assert module.title == "Introduction to Algorithms and Data Structures"
        assert module.level == 2
        assert module.credits == 12

    def test_returns_none_on_invalid_json(self, tmp_path):
        path = tmp_path / "bad.json"
        path.write_text("NOT JSON {{{")
        module = load_from_json(path)
        assert module is None

    def test_ilos_loaded(self, tmp_path, sample_module_data):
        path = tmp_path / "TEST101.json"
        with open(path, "w") as f:
            json.dump(sample_module_data, f)
        module = load_from_json(path)
        assert len(module.ilos) == 5

    def test_topics_loaded(self, tmp_path, sample_module_data):
        path = tmp_path / "TEST101.json"
        with open(path, "w") as f:
            json.dump(sample_module_data, f)
        module = load_from_json(path)
        assert "Sorting algorithms" in module.topics

    def test_description_clean_populated(self, tmp_path, sample_module_data):
        path = tmp_path / "TEST101.json"
        with open(path, "w") as f:
            json.dump(sample_module_data, f)
        module = load_from_json(path)
        assert module.description_clean  # normaliser ran

    def test_source_set_to_institutional(self, tmp_path, sample_module_data):
        path = tmp_path / "TEST101.json"
        with open(path, "w") as f:
            json.dump(sample_module_data, f)
        module = load_from_json(path)
        assert module.source == "institutional"


class TestLoadFromOcwJson:
    def test_loads_ocw_format(self, tmp_path):
        ocw_data = {
            "code": "MIT601",
            "title": "Introduction to Algorithms",
            "level": 2,
            "credits": 12,
            "prerequisites": [],
            "description": "Covers sorting, graph algorithms, and dynamic programming.",
            "learning_objectives": [
                "Implement sorting algorithms",
                "Analyse time complexity",
            ],
            "topics": ["Sorting", "Graph algorithms"],
            "source": "mit_ocw",
        }
        path = tmp_path / "MIT601.json"
        with open(path, "w") as f:
            json.dump(ocw_data, f)

        module = load_from_ocw_json(path)
        assert module is not None
        assert module.code == "MIT601"
        assert module.source == "mit_ocw"
        assert len(module.ilos) == 2

    def test_returns_none_when_no_description(self, tmp_path):
        ocw_data = {"code": "X", "title": "Empty", "description": "", "learning_objectives": []}
        path = tmp_path / "X.json"
        with open(path, "w") as f:
            json.dump(ocw_data, f)
        module = load_from_ocw_json(path)
        assert module is None


class TestLoadAllModules:
    def test_loads_all_json_files(self, tmp_path, sample_module_data):
        for i in range(3):
            data = sample_module_data.copy()
            data["code"] = f"MOD{i:03}"
            path = tmp_path / f"MOD{i:03}.json"
            with open(path, "w") as f:
                json.dump(data, f)

        modules = load_all_modules(tmp_path)
        assert len(modules) == 3

    def test_deduplicates_by_code(self, tmp_path, sample_module_data):
        """Two files with same code → only one module."""
        for name in ["a.json", "b.json"]:
            path = tmp_path / name
            with open(path, "w") as f:
                json.dump(sample_module_data, f)

        modules = load_all_modules(tmp_path)
        assert len(modules) == 1

    def test_empty_directory_returns_empty(self, tmp_path):
        modules = load_all_modules(tmp_path)
        assert modules == []
