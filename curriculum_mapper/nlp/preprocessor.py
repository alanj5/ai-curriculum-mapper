"""NLP Preprocessor.

Transforms raw module text into structured tokens, sentence splits,
and noun chunks using spaCy and NLTK. Designed to be instantiated once
and reused across all modules (model loading is expensive).
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from functools import lru_cache

import spacy
from nltk.corpus import stopwords
from nltk.stem import WordNetLemmatizer

from curriculum_mapper.config import (
    ACRONYM_MAP,
    DOMAIN_STOP_WORDS,
    SPACY_MODEL,
)

# ── Data classes ───────────────────────────────────────────────────────────────


@dataclass
class ProcessedText:
    tokens: list[str]        # lowercased, filtered, lemmatized tokens
    sentences: list[str]     # original sentences (for TextRank)
    noun_chunks: list[str]   # spaCy noun phrases (lowercased)
    raw: str                 # original input text


# ── Preprocessor ───────────────────────────────────────────────────────────────


class Preprocessor:
    """Stateful NLP preprocessor — initialise once, call process() many times."""

    def __init__(self) -> None:
        # Load with dependency parser enabled (needed for noun_chunks);
        # disable NER which is unused and slows processing.
        self._nlp = spacy.load(SPACY_MODEL, disable=["ner"])

        self._lemmatizer = WordNetLemmatizer()

        nltk_stopwords = set(stopwords.words("english"))
        self._stop_words: set[str] = nltk_stopwords | set(DOMAIN_STOP_WORDS)

        # Pre-compile acronym regex
        self._acronym_patterns: list[tuple[re.Pattern, str]] = [
            (re.compile(r"\b" + re.escape(k) + r"\b"), v)
            for k, v in sorted(ACRONYM_MAP.items(), key=lambda x: -len(x[0]))
        ]

    # ── Public interface ───────────────────────────────────────────────────────

    def process(self, text: str) -> ProcessedText:
        """Full preprocessing pipeline for a single text."""
        if not text or not text.strip():
            return ProcessedText(tokens=[], sentences=[], noun_chunks=[], raw=text)

        # Step 1: Expand acronyms before tokenisation
        text_expanded = self._expand_acronyms(text)

        # Step 2: spaCy parse
        doc = self._nlp(text_expanded)

        # Step 3: Sentence splitting
        sentences = [sent.text.strip() for sent in doc.sents if sent.text.strip()]

        # Step 4: Noun chunks (keep multi-word technical phrases)
        noun_chunks = [
            chunk.text.lower()
            for chunk in doc.noun_chunks
            if len(chunk.text) > 2 and len(chunk.text.split()) <= 5
        ]

        # Step 5: Token filtering and lemmatisation
        tokens = []
        for token in doc:
            if self._keep_token(token):
                lemma = self._lemmatizer.lemmatize(token.text.lower())
                if lemma not in self._stop_words and len(lemma) > 2:
                    tokens.append(lemma)

        return ProcessedText(
            tokens=tokens,
            sentences=sentences,
            noun_chunks=list(dict.fromkeys(noun_chunks)),  # deduplicate
            raw=text,
        )

    def process_batch(self, texts: list[str]) -> list[ProcessedText]:
        """Process multiple texts — uses spaCy's pipe() for efficiency."""
        results = []
        for text in texts:
            results.append(self.process(text))
        return results

    # ── Private helpers ────────────────────────────────────────────────────────

    def _expand_acronyms(self, text: str) -> str:
        for pattern, expansion in self._acronym_patterns:
            text = pattern.sub(expansion, text)
        return text

    def _keep_token(self, token) -> bool:
        """Return True if this token should be kept for NLP processing."""
        if token.is_punct:
            return False
        if token.is_space:
            return False
        if token.like_num:
            return False
        if len(token.text) <= 2:
            return False
        # Keep programming language names that might look like stop words
        if token.text.lower() in {"c", "go", "r", "ml"}:
            return False
        return True

    @lru_cache(maxsize=10000)
    def lemmatize(self, word: str) -> str:
        """Cached lemmatisation for individual words."""
        return self._lemmatizer.lemmatize(word.lower())

    def tokenize_phrase(self, phrase: str) -> list[str]:
        """Tokenize and lemmatize a keyphrase (used in canonicalization)."""
        tokens = []
        for token in self._nlp(phrase):
            if self._keep_token(token):
                lemma = self._lemmatizer.lemmatize(token.text.lower())
                if lemma not in self._stop_words and len(lemma) > 2:
                    tokens.append(lemma)
        return tokens
