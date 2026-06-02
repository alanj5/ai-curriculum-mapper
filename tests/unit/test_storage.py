"""Unit tests for ingestion.storage."""

from curriculum_mapper.ingestion.schema import AlignmentResult, Concept


class TestStorageManager:
    def test_init_creates_tables(self, temp_db):
        """DB initialises with empty tables."""
        assert temp_db.count_modules() == 0
        assert temp_db.count_concepts() == 0
        assert temp_db.count_alignments() == 0

    def test_insert_and_retrieve_module(self, temp_db, algorithms_module):
        temp_db.insert_module(algorithms_module)
        assert temp_db.count_modules() == 1

        retrieved = temp_db.get_module("TEST101")
        assert retrieved is not None
        assert retrieved.code == "TEST101"
        assert retrieved.title == "Introduction to Algorithms and Data Structures"
        assert retrieved.level == 2
        assert len(retrieved.ilos) == 5

    def test_insert_idempotent(self, temp_db, algorithms_module):
        """INSERT OR REPLACE — inserting same module twice does not duplicate."""
        temp_db.insert_module(algorithms_module)
        temp_db.insert_module(algorithms_module)
        assert temp_db.count_modules() == 1

    def test_get_all_modules(self, temp_db, algorithms_module, os_module):
        temp_db.insert_module(algorithms_module)
        temp_db.insert_module(os_module)
        modules = temp_db.get_all_modules()
        assert len(modules) == 2
        codes = {m.code for m in modules}
        assert "TEST101" in codes
        assert "TEST202" in codes

    def test_module_prerequisites_persisted(self, temp_db, os_module):
        temp_db.insert_module(os_module)
        retrieved = temp_db.get_module("TEST202")
        assert "TEST101" in retrieved.prerequisites

    def test_module_topics_persisted(self, temp_db, algorithms_module):
        temp_db.insert_module(algorithms_module)
        retrieved = temp_db.get_module("TEST101")
        assert "Sorting algorithms" in retrieved.topics

    def test_get_nonexistent_module(self, temp_db):
        assert temp_db.get_module("NONEXISTENT") is None

    def test_insert_concept(self, temp_db):
        concept = Concept(
            term="merge sort",
            confidence=0.85,
            extractors=["tfidf", "rake"],
            module_codes=["TEST101"],
            variants=["mergesort", "merge-sort"],
        )
        temp_db.insert_concept(concept)
        assert temp_db.count_concepts() == 1

    def test_insert_and_retrieve_concepts(self, temp_db):
        concepts = [
            Concept(term="quicksort", confidence=0.9, extractors=["rake"],
                    module_codes=["TEST101"]),
            Concept(term="dynamic programming", confidence=0.8, extractors=["tfidf", "textrank"],
                    module_codes=["TEST101", "TEST202"]),
        ]
        for c in concepts:
            temp_db.insert_concept(c)
        all_concepts = temp_db.get_all_concepts()
        assert len(all_concepts) == 2

    def test_insert_alignment(self, temp_db):
        concept = Concept(term="sorting", confidence=0.8, extractors=["tfidf"],
                          module_codes=["TEST101"])
        temp_db.insert_concept(concept)

        alignment = AlignmentResult(
            concept_id=concept.id,
            ka_code="AL",
            ka_topic="Sorting algorithms",
            method="hybrid",
            score=0.92,
            rank=1,
        )
        temp_db.insert_alignment(alignment)
        assert temp_db.count_alignments() == 1

    def test_clear_concepts(self, temp_db):
        concept = Concept(term="test", confidence=0.5, extractors=["tfidf"],
                          module_codes=["X"])
        temp_db.insert_concept(concept)
        assert temp_db.count_concepts() == 1
        temp_db.clear_concepts()
        assert temp_db.count_concepts() == 0
        assert temp_db.count_alignments() == 0


def test_clear_alignments_is_idempotent(tmp_path):
    """run_alignment should be re-runnable without duplicating rows."""
    from curriculum_mapper.ingestion.schema import AlignmentResult, Concept
    from curriculum_mapper.ingestion.storage import StorageManager
    s = StorageManager(db_path=tmp_path / "t.db")
    c = Concept(term="sorting", confidence=0.9, extractors=["tfidf"], module_codes=["M1"])
    s.insert_concept(c)
    a = AlignmentResult(concept_id=c.id, ka_code="AL", ka_topic="t", method="hybrid", score=0.9, rank=1)
    s.insert_alignment(a)
    assert s.count_alignments() == 1
    s.clear_alignments()
    assert s.count_alignments() == 0
