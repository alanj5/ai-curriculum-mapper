"""Optional LLM-augmented concept extractor (local, via Ollama).

Motivation: the evaluation localises the dominant error as concept *extraction*
from short descriptors. A local instruction-tuned LLM can recover specialised
terms that surface methods miss (e.g. "virtual memory", "operational semantics").
The model runs entirely on-device through Ollama, preserving the project's
privacy-local principle (no external API calls).

Design notes:
  * Matches the extractor contract used elsewhere (cf. ``keybert_extractor.py``):
    an ``is_available`` property and ``extract(text, top_n) -> [(term, score)]``.
  * The ``ollama`` import is performed lazily inside ``__init__`` so this module
    imports with no dependency (keeping CI deterministic and Ollama-free).
  * Queried at temperature 0 and the parsed output is cached to disk
    (SHA-256 of ``model::text``), so reported numbers reproduce without re-running
    the model — addressing the usual "LLMs are not reproducible" objection.
  * The LLM returns no scores, so a rank-decay (1.0 → ~0.5) gives the ensemble an
    ordering/confidence proxy. Any failure returns ``[]`` and never crashes the
    pipeline.
"""

from __future__ import annotations

import hashlib
import json
import logging
import re

from curriculum_mapper.config import (
    LLM_CACHE,
    LLM_ENDPOINT,
    LLM_MODEL,
    LLM_TIMEOUT,
    LLM_TOP_N,
)

logger = logging.getLogger(__name__)

_PROMPT_TEMPLATE = (
    "You are an expert computer-science curriculum analyst. From the module "
    "description below, extract the key technical computing concepts a student is "
    "taught — specific algorithms, data structures, systems, theories, models, or "
    "methods. Return ONLY a JSON array of at most {top_n} short concept phrases "
    "(1-4 words each), most important first. No prose, no numbering, no duplicates, "
    "no generic words like 'design' or 'analysis'.\n\n"
    "MODULE:\n{text}\n\nJSON array:"
)


def _strip_code_fences(s: str) -> str:
    s = s.strip()
    if s.startswith("```"):
        s = re.sub(r"^```[a-zA-Z]*\n?", "", s)
        s = re.sub(r"\n?```$", "", s)
    return s.strip()


def _parse_concepts(content: str, top_n: int) -> list[str]:
    """Parse an LLM response into a clean, deduplicated concept list.

    Prefers a JSON array; falls back to line/comma splitting with bullet and
    numbering removal. Terms are lowercased, length-filtered, and clamped.
    """
    content = _strip_code_fences(content or "")
    terms: list[str] = []
    try:
        data = json.loads(content)
        if isinstance(data, list):
            terms = [str(x) for x in data]
    except Exception:
        for line in re.split(r"[\n,]", content):
            t = re.sub(r"^[\s\-\*•\d.\)\"']+", "", line).strip()
            if t:
                terms.append(t)

    seen: set[str] = set()
    out: list[str] = []
    for t in terms:
        t = re.sub(r"\s+", " ", str(t).lower()).strip().strip('".,;:[]')
        if not t or len(t) < 3 or len(t.split()) > 6:
            continue
        if t in seen:
            continue
        seen.add(t)
        out.append(t)
    return out[:top_n]


def _rank_decay_scores(n: int) -> list[float]:
    """Descending pseudo-confidence from 1.0 (rank 1) to ~0.5 (rank n)."""
    if n <= 1:
        return [1.0] * n
    return [round(1.0 - 0.5 * i / (n - 1), 4) for i in range(n)]


def _response_content(resp) -> str:
    """Extract message content from an ollama chat response (dict or object)."""
    try:
        return resp["message"]["content"]
    except Exception:
        pass
    try:
        return resp.message.content
    except Exception:
        return ""


class LLMExtractor:
    """Optional local-LLM concept extractor backed by Ollama."""

    def __init__(
        self,
        model: str = LLM_MODEL,
        endpoint: str = LLM_ENDPOINT,
        timeout: float = LLM_TIMEOUT,
        client=None,
        use_cache: bool = True,
    ) -> None:
        self.model = model
        self.endpoint = endpoint
        self.timeout = timeout
        self.use_cache = use_cache
        if client is not None:
            self._client = client
            self._available = True
        else:
            try:
                import ollama
                self._client = ollama.Client(host=endpoint)
                self._available = True
            except Exception as e:  # ollama not installed / client init failed
                logger.warning(f"Ollama client unavailable: {e}. LLMExtractor disabled.")
                self._client = None
                self._available = False

    @property
    def is_available(self) -> bool:
        return self._available

    def ping(self) -> bool:
        """True if the Ollama server is reachable (lightweight check)."""
        if not self._available:
            return False
        try:
            self._client.list()
            return True
        except Exception:
            return False

    def _cache_path(self, text: str):
        key = hashlib.sha256(f"{self.model}::{text}".encode()).hexdigest()
        return LLM_CACHE / f"{key}.json"

    def extract(self, text: str, top_n: int = LLM_TOP_N) -> list[tuple[str, float]]:
        """Return [(concept, score), ...] for one module text."""
        if not text or not text.strip() or not self._available:
            return []

        if self.use_cache:
            cp = self._cache_path(text)
            if cp.exists():
                try:
                    terms = json.loads(cp.read_text())[:top_n]
                    return list(zip(terms, _rank_decay_scores(len(terms))))
                except Exception:
                    pass

        prompt = _PROMPT_TEMPLATE.format(top_n=top_n, text=text[:6000])
        try:
            resp = self._client.chat(
                model=self.model,
                messages=[{"role": "user", "content": prompt}],
                options={"temperature": 0.0},
            )
        except Exception as e:
            logger.warning(f"LLM extraction failed ({self.model}): {e}")
            return []

        terms = _parse_concepts(_response_content(resp), top_n)
        if self.use_cache:
            try:
                self._cache_path(text).write_text(json.dumps(terms))
            except Exception:
                pass
        return list(zip(terms, _rank_decay_scores(len(terms))))
