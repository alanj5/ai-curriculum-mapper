"""Unit tests for the optional LLM concept extractor (mocked; no Ollama needed)."""

from __future__ import annotations

import pytest

from curriculum_mapper.nlp.extractors.llm_extractor import (
    LLMExtractor,
    _parse_concepts,
    _rank_decay_scores,
)


class TestParseConcepts:
    def test_json_array(self):
        out = _parse_concepts('["dynamic programming", "binary search", "heap"]', 10)
        assert out == ["dynamic programming", "binary search", "heap"]

    def test_json_with_code_fence(self):
        content = '```json\n["virtual memory", "deadlock"]\n```'
        assert _parse_concepts(content, 10) == ["virtual memory", "deadlock"]

    def test_line_fallback_with_bullets_and_numbers(self):
        content = "1. Sorting Algorithms\n- Binary Search\n* heaps"
        assert _parse_concepts(content, 10) == ["sorting algorithms", "binary search", "heaps"]

    def test_dedup_and_length_filter(self):
        content = '["graph", "graph", "x", "a very long phrase that exceeds the limit by far"]'
        # "graph" deduped; "x" too short (<3); long phrase >6 words dropped.
        assert _parse_concepts(content, 10) == ["graph"]

    def test_clamp_to_top_n(self):
        content = '["a1 concept", "b2 concept", "c3 concept"]'
        assert len(_parse_concepts(content, 2)) == 2

    def test_empty(self):
        assert _parse_concepts("", 10) == []


class TestRankDecay:
    def test_single(self):
        assert _rank_decay_scores(1) == [1.0]

    def test_descending(self):
        s = _rank_decay_scores(3)
        assert s[0] == 1.0 and s[-1] == 0.5 and s[0] > s[1] > s[2]


class _FakeClient:
    def __init__(self, content):
        self._content = content

    def chat(self, model, messages, options=None):
        return {"message": {"content": self._content}}


class _FailClient:
    def chat(self, *a, **k):
        raise RuntimeError("connection refused")


class TestLLMExtractor:
    def test_is_available_with_injected_client(self):
        ex = LLMExtractor(client=_FakeClient("[]"), use_cache=False)
        assert ex.is_available is True

    def test_extract_parses_and_scores(self):
        ex = LLMExtractor(client=_FakeClient('["merge sort", "quicksort"]'), use_cache=False)
        out = ex.extract("sorting algorithms module", top_n=10)
        assert [t for t, _ in out] == ["merge sort", "quicksort"]
        assert out[0][1] == 1.0 and out[1][1] == 0.5  # rank decay over 2 items

    def test_empty_text_returns_empty(self):
        ex = LLMExtractor(client=_FakeClient('["x"]'), use_cache=False)
        assert ex.extract("   ", top_n=10) == []

    def test_extract_handles_client_failure(self):
        ex = LLMExtractor(client=_FailClient(), use_cache=False)
        assert ex.extract("some text", top_n=10) == []

    @pytest.mark.parametrize("top_n", [1, 2, 3])
    def test_respects_top_n(self, top_n):
        ex = LLMExtractor(
            client=_FakeClient('["c1 one", "c2 two", "c3 three", "c4 four"]'),
            use_cache=False,
        )
        assert len(ex.extract("text", top_n=top_n)) == top_n


class TestLLMCache:
    def test_cache_round_trip(self, tmp_path, monkeypatch):
        import curriculum_mapper.nlp.extractors.llm_extractor as mod
        monkeypatch.setattr(mod, "LLM_CACHE", tmp_path)

        class _CountingClient:
            calls = 0

            def chat(self, model, messages, options=None):
                _CountingClient.calls += 1
                return {"message": {"content": '["hash table", "b tree"]'}}

        client = _CountingClient()
        ex = mod.LLMExtractor(client=client, use_cache=True)
        out1 = ex.extract("data structures module text", top_n=10)
        out2 = ex.extract("data structures module text", top_n=10)  # cache hit
        assert [t for t, _ in out1] == ["hash table", "b tree"]
        assert out1 == out2
        assert client.calls == 1  # second call served from cache


class _PingClient:
    def __init__(self, ok=True):
        self._ok = ok

    def list(self):
        if not self._ok:
            raise RuntimeError("server down")
        return {"models": []}

    def chat(self, *a, **k):
        return {"message": {"content": "[]"}}


class _ObjResp:
    """Mimics ollama's object-style response (resp.message.content)."""
    class _M:
        content = '["b tree", "red black tree"]'
    message = _M()


class TestLLMExtractorBranches:
    def test_ping_true_and_false(self):
        assert LLMExtractor(client=_PingClient(ok=True)).ping() is True
        assert LLMExtractor(client=_PingClient(ok=False)).ping() is False

    def test_object_style_response(self):
        class _C:
            def chat(self, *a, **k):
                return _ObjResp()
        out = LLMExtractor(client=_C(), use_cache=False).extract("trees module", top_n=10)
        assert [t for t, _ in out] == ["b tree", "red black tree"]

    def test_corrupt_cache_falls_back(self, tmp_path, monkeypatch):
        import curriculum_mapper.nlp.extractors.llm_extractor as mod
        monkeypatch.setattr(mod, "LLM_CACHE", tmp_path)
        ex = mod.LLMExtractor(client=_FakeClient('["hashing"]'), use_cache=True)
        # Pre-write a corrupt cache file for this text → should ignore and re-query.
        ex._cache_path("xyz").write_text("{not json")
        assert [t for t, _ in ex.extract("xyz", top_n=5)] == ["hashing"]
