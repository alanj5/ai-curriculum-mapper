"""Unit tests for nlp.extractors.tfidf_extractor."""

import pytest

from curriculum_mapper.nlp.extractors.tfidf_extractor import TFIDFExtractor


@pytest.fixture
def fitted_extractor(small_corpus) -> TFIDFExtractor:
    extractor = TFIDFExtractor()
    extractor.fit(small_corpus)
    return extractor


class TestTFIDFExtractor:
    def test_not_fitted_returns_empty(self):
        extractor = TFIDFExtractor()
        result = extractor.extract("some text")
        assert result == []

    def test_fit_sets_fitted_flag(self, small_corpus):
        extractor = TFIDFExtractor()
        assert not extractor.is_fitted
        extractor.fit(small_corpus)
        assert extractor.is_fitted

    def test_fit_requires_multiple_docs(self):
        extractor = TFIDFExtractor()
        # Should not raise but will warn
        extractor.fit(["single document"])
        # min_df=2 means nothing will have count >= 2 in 1 doc
        assert not extractor.is_fitted

    def test_extract_returns_list_of_tuples(self, fitted_extractor, small_corpus):
        result = fitted_extractor.extract(small_corpus[0])
        assert isinstance(result, list)
        if result:
            assert isinstance(result[0], tuple)
            assert len(result[0]) == 2

    def test_scores_in_valid_range(self, fitted_extractor, small_corpus):
        result = fitted_extractor.extract(small_corpus[0])
        for term, score in result:
            assert 0 <= score <= 1.0, f"Score {score} for '{term}' out of range"

    def test_respects_top_n(self, fitted_extractor, small_corpus):
        result = fitted_extractor.extract(small_corpus[0], top_n=5)
        assert len(result) <= 5

    def test_results_sorted_descending(self, fitted_extractor, small_corpus):
        result = fitted_extractor.extract(small_corpus[0], top_n=20)
        scores = [s for _, s in result]
        assert scores == sorted(scores, reverse=True)

    def test_empty_text_returns_empty(self, fitted_extractor):
        assert fitted_extractor.extract("") == []
        assert fitted_extractor.extract("   ") == []

    def test_domain_terms_extracted(self, fitted_extractor, algorithms_module):
        result = fitted_extractor.extract(algorithms_module.full_text, top_n=20)
        extracted_terms = [term for term, _ in result]
        extracted_text = " ".join(extracted_terms)
        # High-confidence technical terms should appear
        assert any(
            term in extracted_text
            for term in ["sort", "algorithm", "graph", "dynamic", "hash", "tree"]
        ), f"Expected domain terms not found in: {extracted_terms}"

    def test_fit_extract_all_returns_per_doc(self, small_corpus):
        extractor = TFIDFExtractor()
        results = extractor.fit_extract_all(small_corpus, top_n=5)
        assert len(results) == len(small_corpus)
        for doc_results in results:
            assert isinstance(doc_results, list)
