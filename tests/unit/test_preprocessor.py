"""Unit tests for nlp.preprocessor."""

import pytest

from curriculum_mapper.nlp.preprocessor import Preprocessor, ProcessedText


@pytest.fixture(scope="module")
def preprocessor():
    return Preprocessor()


class TestPreprocessor:
    def test_returns_processed_text(self, preprocessor):
        result = preprocessor.process("Students learn sorting algorithms.")
        assert isinstance(result, ProcessedText)

    def test_empty_string(self, preprocessor):
        result = preprocessor.process("")
        assert result.tokens == []
        assert result.sentences == []
        assert result.noun_chunks == []

    def test_whitespace_only(self, preprocessor):
        result = preprocessor.process("   \n\t  ")
        assert result.tokens == []

    def test_domain_stop_words_removed(self, preprocessor):
        result = preprocessor.process(
            "Students will understand the module learning outcomes."
        )
        # "students", "module", "learning", "outcomes" should be filtered
        assert "student" not in result.tokens
        assert "module" not in result.tokens

    def test_lemmatisation(self, preprocessor):
        result = preprocessor.process("sorting algorithms are analysed")
        # "sorting" → "sorting", "algorithms" → "algorithm", "analysed" → "analysed"
        assert "sorting" in result.tokens or "sort" in result.tokens
        assert "algorithm" in result.tokens

    def test_sentences_extracted(self, preprocessor):
        result = preprocessor.process(
            "First sentence. Second sentence. Third sentence."
        )
        assert len(result.sentences) >= 2

    def test_noun_chunks_extracted(self, preprocessor):
        result = preprocessor.process(
            "Binary search trees and priority queues are fundamental data structures."
        )
        " ".join(result.noun_chunks)
        # Should capture multi-word technical phrases
        assert len(result.noun_chunks) > 0

    def test_acronym_expansion(self, preprocessor):
        result = preprocessor.process("The OS uses virtual memory management.")
        # "OS" should have been expanded before tokenisation
        assert "operating" in result.tokens or "system" in result.tokens

    def test_technical_terms_preserved(self, preprocessor):
        result = preprocessor.process(
            "Quicksort uses divide and conquer. Hash tables have O(1) lookup."
        )
        assert "quicksort" in result.tokens
        assert "hash" in result.tokens or "table" in result.tokens

    def test_punctuation_removed(self, preprocessor):
        result = preprocessor.process("Algorithms: sorting, searching, and graph traversal.")
        for token in result.tokens:
            assert ":" not in token
            assert "," not in token

    def test_numbers_removed(self, preprocessor):
        result = preprocessor.process("Chapter 3 covers 5 sorting algorithms.")
        for token in result.tokens:
            assert not token.isdigit()

    def test_raw_preserved(self, preprocessor):
        text = "Some raw text."
        result = preprocessor.process(text)
        assert result.raw == text

    def test_deduplication_noun_chunks(self, preprocessor):
        result = preprocessor.process(
            "Binary search trees. Binary search trees are efficient. Binary search trees."
        )
        # No duplicate noun chunks
        assert len(result.noun_chunks) == len(set(result.noun_chunks))

    def test_lemmatize_method(self, preprocessor):
        assert preprocessor.lemmatize("sorting") in ("sorting", "sort")
        assert preprocessor.lemmatize("algorithms") in ("algorithm", "algorithms")

    def test_tokenize_phrase(self, preprocessor):
        tokens = preprocessor.tokenize_phrase("binary search trees")
        assert "binary" in tokens or "search" in tokens or "tree" in tokens
