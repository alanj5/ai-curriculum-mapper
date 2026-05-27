"""Unit tests for nlp.extractors.textrank_extractor."""

import pytest

from curriculum_mapper.nlp.extractors.textrank_extractor import TextRankExtractor


@pytest.fixture(scope="module")
def textrank():
    return TextRankExtractor()


class TestTextRankExtractor:
    def test_returns_list_of_tuples(self, textrank):
        result = textrank.extract(
            "Sorting algorithms such as merge sort and quicksort are fundamental. "
            "Graph algorithms include breadth-first search and depth-first search."
        )
        assert isinstance(result, list)
        if result:
            assert isinstance(result[0], tuple)
            assert len(result[0]) == 2

    def test_empty_text_returns_empty(self, textrank):
        assert textrank.extract("") == []
        assert textrank.extract("   ") == []

    def test_respects_top_n(self, textrank):
        text = (
            "Operating systems manage processes and threads. Virtual memory uses paging. "
            "File systems store data. Scheduling algorithms decide CPU allocation. "
            "Deadlock occurs when processes wait indefinitely. Semaphores prevent races."
        )
        result = textrank.extract(text, top_n=5)
        assert len(result) <= 5

    def test_results_sorted_descending(self, textrank):
        result = textrank.extract(
            "Dynamic programming solves overlapping subproblems. "
            "Greedy algorithms make locally optimal choices. "
            "Divide and conquer splits problems recursively."
        )
        scores = [s for _, s in result]
        assert scores == sorted(scores, reverse=True)

    def test_no_duplicate_phrases(self, textrank):
        result = textrank.extract(
            "Binary search trees. Binary search trees are efficient. Binary search trees."
        )
        terms = [t for t, _ in result]
        assert len(terms) == len(set(terms)), f"Duplicates found: {terms}"

    def test_captures_domain_terms(self, textrank, algorithms_module):
        result = textrank.extract(algorithms_module.full_text, top_n=20)
        terms = [t for t, _ in result]
        combined = " ".join(terms)
        assert any(
            kw in combined
            for kw in ["sort", "algorithm", "dynamic", "graph", "hash", "tree"]
        ), f"No expected domain terms in TextRank output: {terms}"

    def test_phrase_length_limit(self, textrank):
        """Extracted phrases should not be excessively long."""
        result = textrank.extract(
            "Introduction to algorithms and data structures for computer science students."
        )
        for phrase, _ in result:
            word_count = len(phrase.split())
            assert word_count <= 5, f"Phrase too long ({word_count} words): '{phrase}'"

    def test_availability_property(self, textrank):
        assert isinstance(textrank.is_available, bool)


class TestTextRankFallbackPath:
    """Test the noun-chunk fallback path when pytextrank is unavailable."""

    def test_fallback_via_forced_unavailable(self):
        """Simulate unavailable mode by patching _available to False."""
        tr = TextRankExtractor()
        original = tr._available
        tr._available = False
        try:
            result = tr.extract(
                "Sorting algorithms include merge sort and quicksort. "
                "Graph algorithms use breadth-first search."
            )
            # Fallback uses noun chunks — should still return tuples
            assert isinstance(result, list)
            if result:
                assert isinstance(result[0], tuple)
                assert len(result[0]) == 2
        finally:
            tr._available = original

    def test_fallback_returns_unique_chunks(self):
        tr = TextRankExtractor()
        tr._available = False
        try:
            result = tr.extract(
                "Binary search trees. Binary search trees are efficient. Binary search trees."
            )
            terms = [t for t, _ in result]
            assert len(terms) == len(set(terms)), f"Duplicates in fallback: {terms}"
        finally:
            tr._available = True

    def test_fallback_scores_are_positive(self):
        tr = TextRankExtractor()
        tr._available = False
        try:
            result = tr.extract(
                "Operating systems manage virtual memory and process scheduling."
            )
            for _, score in result:
                assert score > 0
        finally:
            tr._available = True
