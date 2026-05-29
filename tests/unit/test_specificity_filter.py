"""Unit tests for the concept-specificity filter (nlp.pipeline._is_generic_candidate).

The filter rejects candidate concepts whose tokens are all generic academic /
process vocabulary (no computing-domain signal), while preserving genuine
computing concepts. This addresses the HCI over-coverage artefact where generic
terms such as "design"/"evaluation"/"research" were aligned to HCI topics.
"""

import pytest

from curriculum_mapper.nlp.pipeline import _is_generic_candidate


class TestSpecificityFilter:
    @pytest.mark.parametrize(
        "term",
        [
            "analysis",
            "evaluation",
            "design",
            "research",
            "study",
            "principles",
            "approaches",
            "basic research",
            "capabilities effectively evaluate",
            "characterise evaluate different",
            "main principles",
            "",
            "   ",
        ],
    )
    def test_generic_terms_rejected(self, term):
        assert _is_generic_candidate(term) is True

    @pytest.mark.parametrize(
        "term",
        [
            "graph",
            "heap",
            "boolean",
            "complexity",
            "concurrency",
            "virtual memory",
            "dynamic programming",
            "binary search tree",
            "human-centred design",
            "predictive models",
            "operating system",
            "turing machine",
            # Allowlisted single words that also appear in stop-word lists.
            "processes",
            "process",
            "value",
            "types",
        ],
    )
    def test_domain_concepts_kept(self, term):
        assert _is_generic_candidate(term) is False

    def test_one_contentful_token_survives(self):
        # "design" is generic but "patterns" is not -> phrase is kept.
        assert _is_generic_candidate("design patterns") is False

    def test_case_insensitive(self):
        assert _is_generic_candidate("ANALYSIS") is True
        assert _is_generic_candidate("Graph") is False

    def test_punctuation_stripped(self):
        assert _is_generic_candidate("analysis,") is True
        assert _is_generic_candidate("(research)") is True
