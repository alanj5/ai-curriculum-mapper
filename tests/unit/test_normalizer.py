"""Unit tests for ingestion.normalizer."""

from curriculum_mapper.ingestion.normalizer import clean_text, normalise_module
from curriculum_mapper.ingestion.schema import ModuleDescriptor


class TestCleanText:
    def test_html_stripping(self):
        result = clean_text("<p>Hello <b>world</b></p>")
        assert "<" not in result
        assert "Hello" in result
        assert "world" in result

    def test_unicode_normalisation(self):
        # NFKC: ligature fi → fi
        result = clean_text("eﬁcient")  # eﬁcient
        assert "fi" in result or "efficient" in result.lower()

    def test_acronym_expansion_os(self):
        result = clean_text("The OS scheduler manages processes.", expand_acronyms=True)
        assert "operating system" in result.lower()

    def test_acronym_expansion_ml(self):
        result = clean_text("ML and NLP are subfields of AI.", expand_acronyms=True)
        assert "machine learning" in result.lower()
        assert "natural language processing" in result.lower()
        assert "artificial intelligence" in result.lower()

    def test_no_acronym_expansion_when_disabled(self):
        result = clean_text("OS and ML", expand_acronyms=False)
        assert "operating system" not in result.lower()
        assert "machine learning" not in result.lower()

    def test_whitespace_collapsing(self):
        result = clean_text("  hello   \n\n  world  ")
        assert "  " not in result
        assert result == "hello world"

    def test_bullet_removal(self):
        text = "• First point\n• Second point\n- Third point"
        result = clean_text(text)
        assert "•" not in result
        assert "-" not in result.lstrip()

    def test_empty_string(self):
        assert clean_text("") == ""
        assert clean_text("   ") == ""

    def test_preserves_technical_terms(self):
        result = clean_text("Quicksort, heapsort, and merge sort.")
        assert "quicksort" in result.lower()
        assert "heapsort" in result.lower()
        assert "merge sort" in result.lower()


class TestNormaliseModule:
    def test_description_cleaned(self, algorithms_module):
        normalised = normalise_module(algorithms_module.model_copy(deep=True))
        assert normalised.description_clean
        assert len(normalised.description_clean) > 0

    def test_ilo_texts_cleaned(self, algorithms_module):
        module_copy = algorithms_module.model_copy(deep=True)
        normalised = normalise_module(module_copy)
        for ilo in normalised.ilos:
            assert ilo.text_clean is not None

    def test_acronym_expansion_in_module(self):
        module = ModuleDescriptor(
            code="X",
            title="Test",
            level=1,
            credits=12,
            description="The OS manages processes and the CPU schedules threads.",
            source="test",
            source_file="x.json",
        )
        normalised = normalise_module(module)
        assert "operating system" in normalised.description_clean.lower()
        assert "central processing unit" in normalised.description_clean.lower()
