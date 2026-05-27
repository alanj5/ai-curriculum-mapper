"""Unit tests for nlp.extractors.rake_extractor."""

import pytest

from curriculum_mapper.nlp.extractors.rake_extractor import RAKEExtractor


@pytest.fixture(scope="module")
def rake():
    return RAKEExtractor()


class TestRAKEExtractor:
    def test_returns_list_of_tuples(self, rake):
        result = rake.extract("Sorting algorithms include merge sort and quicksort.")
        assert isinstance(result, list)
        if result:
            assert isinstance(result[0], tuple)
            assert len(result[0]) == 2

    def test_empty_text_returns_empty(self, rake):
        assert rake.extract("") == []
        assert rake.extract("   ") == []

    def test_respects_top_n(self, rake):
        text = (
            "Machine learning algorithms, neural networks, deep learning, "
            "support vector machines, random forests, decision trees, "
            "gradient boosting, reinforcement learning, natural language processing."
        )
        result = rake.extract(text, top_n=5)
        assert len(result) <= 5

    def test_multi_word_phrases_extracted(self, rake):
        result = rake.extract(
            "Binary search trees are used in dynamic programming. "
            "Hash tables support constant time lookup."
        )
        terms = [kw for kw, _ in result]
        # Should find multi-word phrases (RAKE's strength)
        multi_word = [t for t in terms if " " in t]
        assert len(multi_word) >= 1, f"No multi-word phrases found in: {terms}"

    def test_domain_stop_words_filtered(self, rake):
        result = rake.extract(
            "Students will understand module learning outcomes this week."
        )
        terms = [kw for kw, _ in result]
        # Domain stop words should not appear as standalone keyphrases
        for stop in ["students", "module", "learning", "outcomes"]:
            assert not any(stop == t.strip() for t in terms), \
                f"Stop word '{stop}' appeared in RAKE results: {terms}"

    def test_technical_terms_in_output(self, rake, algorithms_module):
        result = rake.extract(algorithms_module.full_text, top_n=20)
        terms = [kw for kw, _ in result]
        combined = " ".join(terms)
        assert any(
            kw in combined
            for kw in ["sort", "algorithm", "dynamic", "graph", "hash", "tree", "search"]
        ), f"No expected domain terms in: {terms}"

    def test_scores_are_positive(self, rake):
        result = rake.extract("Neural networks use backpropagation for training.")
        for term, score in result:
            assert score >= 0, f"Negative score {score} for '{term}'"


class TestRAKEFallbackExtract:
    """Tests for the _fallback_extract method called when multi-rake is unavailable."""

    def test_fallback_returns_list_of_tuples(self):
        rake = RAKEExtractor()
        result = rake._fallback_extract(
            "Binary search trees support logarithmic time insertion.", top_n=5
        )
        assert isinstance(result, list)
        if result:
            assert isinstance(result[0], tuple)
            assert len(result[0]) == 2

    def test_fallback_respects_top_n(self):
        rake = RAKEExtractor()
        text = (
            "Algorithms and data structures including sorting searching graphs "
            "trees heaps queues stacks hashing dynamic programming greedy methods."
        )
        result = rake._fallback_extract(text, top_n=3)
        assert len(result) <= 3

    def test_fallback_scores_in_0_1(self):
        rake = RAKEExtractor()
        result = rake._fallback_extract(
            "Dynamic programming solves overlapping subproblems using memoisation.", top_n=10
        )
        for _, score in result:
            assert 0.0 <= score <= 1.0, f"Score out of range: {score}"

    def test_fallback_empty_text_returns_empty(self):
        rake = RAKEExtractor()
        assert rake._fallback_extract("", top_n=5) == []

    def test_fallback_filters_stop_words(self):
        rake = RAKEExtractor()
        result = rake._fallback_extract("the and or but for", top_n=10)
        terms = [t for t, _ in result]
        for stop in ["the", "and", "or", "but", "for"]:
            assert stop not in terms, f"Stop word '{stop}' in fallback results: {terms}"
