"""Full NLP pipeline orchestrator — Week 2 version with all five extractors.

Execution order:
  1. Load modules from DB
  2. Fit TF-IDF on full corpus (corpus-level)
  3. Fit BERTopic on full corpus (corpus-level)
  4. Per-module: run RAKE, TextRank, KeyBERT, TF-IDF extract
  5. Merge per-module candidates
  6. Canonicalize: SBERT dedup + WordNet merging
  7. Persist Concept objects to DB
  8. Save concepts_inventory.json
"""

from __future__ import annotations

import logging
from collections import defaultdict

from curriculum_mapper.config import (
    _FUNCTION_WORDS,
    CONCEPT_ALLOWLIST,
    DOMAIN_STOP_WORDS,
    GENERIC_CONCEPT_TERMS,
    MAX_CONCEPTS_PER_MODULE,
    TFIDF_TOP_N,
)
from curriculum_mapper.ingestion.storage import StorageManager
from curriculum_mapper.nlp.canonicalizer import Canonicalizer
from curriculum_mapper.nlp.embeddings import EmbeddingManager
from curriculum_mapper.nlp.extractors.bertopic_extractor import BERTopicExtractor
from curriculum_mapper.nlp.extractors.keybert_extractor import KeyBERTExtractor
from curriculum_mapper.nlp.extractors.rake_extractor import RAKEExtractor
from curriculum_mapper.nlp.extractors.textrank_extractor import TextRankExtractor
from curriculum_mapper.nlp.extractors.tfidf_extractor import TFIDFExtractor
from curriculum_mapper.nlp.preprocessor import Preprocessor

logger = logging.getLogger(__name__)


def _normalise_scores(scores: list[float]) -> list[float]:
    """Min-max normalise to [0, 1]."""
    if not scores:
        return scores
    lo, hi = min(scores), max(scores)
    if hi == lo:
        return [1.0] * len(scores)
    return [(s - lo) / (hi - lo) for s in scores]


_VERB_POS = {"VERB", "AUX", "ADP", "DET", "PART"}

# Combined vocabulary with no computing-domain signal, used by the specificity
# filter. A candidate is rejected only when *all* of its tokens are generic.
# Legitimate single-word concepts (CONCEPT_ALLOWLIST) are removed from this set
# so they are never treated as generic (e.g. "process", "value", "type").
_GENERIC_TOKENS = (
    ({w.lower() for w in DOMAIN_STOP_WORDS} | set(GENERIC_CONCEPT_TERMS) | set(_FUNCTION_WORDS))
    - set(CONCEPT_ALLOWLIST)
)


def _is_generic_candidate(term: str) -> bool:
    """True if every alphabetic token in ``term`` is generic (no domain signal).

    Single-word computing concepts (e.g. "graph", "heap", "boolean") are NOT in
    the generic vocabulary, so they survive; purely generic terms such as
    "analysis", "design", "research" and sentence fragments such as
    "capabilities effectively evaluate" are dropped.
    """
    tokens = [t.strip(".,;:()[]'\"") for t in term.lower().split()]
    tokens = [t for t in tokens if t]
    if not tokens:
        return True
    return all(t in _GENERIC_TOKENS or len(t) <= 2 for t in tokens)


class NLPPipeline:
    """Full five-extractor NLP pipeline with canonicalization."""

    def __init__(self) -> None:
        logger.info("Initialising NLP pipeline…")
        self.storage = StorageManager()
        self.em = EmbeddingManager()
        self.tfidf = TFIDFExtractor()
        self.rake = RAKEExtractor()
        self.textrank = TextRankExtractor()
        self.keybert = KeyBERTExtractor(self.em)
        self.bertopic = BERTopicExtractor(self.em)
        self.canonicalizer = Canonicalizer(self.em)
        self.preprocessor = Preprocessor()
        logger.info(
            f"Pipeline ready. KeyBERT={self.keybert.is_available}, "
            f"BERTopic={self.bertopic.is_available}, "
            f"TextRank={self.textrank.is_available}"
        )

    def _filter_noun_headed(
        self, candidates: dict[str, dict[str, float]]
    ) -> dict[str, dict[str, float]]:
        """Drop candidates whose first token is a verb, auxiliary, preposition, or determiner."""
        if not candidates:
            return candidates
        terms = list(candidates.keys())
        docs = list(self.preprocessor._nlp.pipe(terms, disable=["ner", "parser"]))
        return {
            term: candidates[term]
            for term, doc in zip(terms, docs)
            if doc and doc[0].pos_ not in _VERB_POS
        }

    def run(self, top_n: int = TFIDF_TOP_N) -> dict:
        """Run the full pipeline and return the concepts inventory dict."""
        modules = self.storage.get_all_modules()
        if not modules:
            logger.error("No modules in DB — run ingest_modules.py first.")
            return {}

        texts = [m.full_text_clean or m.full_text for m in modules]
        logger.info(f"Running pipeline on {len(modules)} modules…")

        # ── Corpus-level fitting ───────────────────────────────────────────────
        logger.info("Fitting TF-IDF…")
        self.tfidf.fit(texts)

        logger.info("Fitting BERTopic (may take 30–60 s)…")
        bertopic_results = self.bertopic.fit_transform(texts)

        # ── Per-module extraction ─────────────────────────────────────────────
        all_candidates: dict[str, dict[str, dict[str, float]]] = {}

        for i, (module, text) in enumerate(zip(modules, texts)):
            logger.info(f"  Extracting: {module.code}")
            candidates: dict[str, dict[str, float]] = defaultdict(dict)

            for term, score in self.tfidf.extract(text, top_n=top_n):
                candidates[term.lower()]["tfidf"] = score

            rake_raw = self.rake.extract(text, top_n=top_n)
            if rake_raw:
                norm_scores = _normalise_scores([s for _, s in rake_raw])
                for (term, _), ns in zip(rake_raw, norm_scores):
                    candidates[term.lower()]["rake"] = ns

            for term, score in self.textrank.extract(text, top_n=top_n):
                candidates[term.lower()]["textrank"] = score

            for term, score in self.keybert.extract(text, top_n=top_n):
                candidates[term.lower()]["keybert"] = score

            for word in bertopic_results.get(i, []):
                candidates[word.lower()].setdefault("bertopic", 1.0)

            # Filter: (1) very short terms, (2) all-generic terms with no domain
            # signal (specificity filter), then (3) verb-headed phrases.
            length_filtered = {
                t: s
                for t, s in candidates.items()
                if len(t) >= 3 and not _is_generic_candidate(t)
            }
            all_candidates[module.code] = self._filter_noun_headed(length_filtered)

        # ── Canonicalize ──────────────────────────────────────────────────────
        logger.info("Canonicalizing concepts…")
        concepts = self.canonicalizer.canonicalize(all_candidates)

        # ── Persist to DB ─────────────────────────────────────────────────────
        self.storage.clear_concepts()
        for concept in concepts:
            self.storage.insert_concept(concept)
        logger.info(f"Persisted {len(concepts)} canonical concepts to DB.")

        # ── Build per-module inventory for JSON output ─────────────────────────
        # Build lookup: module_code → concepts containing it
        module_concept_map: dict[str, list] = defaultdict(list)
        for c in concepts:
            for mc in c.module_codes:
                module_concept_map[mc].append(c)

        results: dict[str, dict] = {}
        for module in modules:
            mc_concepts = sorted(
                module_concept_map[module.code],
                key=lambda c: -c.confidence,
            )[:MAX_CONCEPTS_PER_MODULE]
            results[module.code] = {
                "title": module.title,
                "level": module.level,
                "concept_count": len(mc_concepts),
                "concepts": [
                    {
                        "term": c.term,
                        "confidence": c.confidence,
                        "extractors": c.extractors,
                        "variants": c.variants[:3],
                    }
                    for c in mc_concepts
                ],
            }

        return results
