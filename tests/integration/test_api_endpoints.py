"""Integration tests for all API endpoints.

Uses httpx AsyncClient with ASGI transport — no live server needed.
Tests run against the real SQLite database populated by the pipeline,
so they require the pipeline to have been run first:
    python scripts/ingest_modules.py
    python scripts/run_nlp_pipeline.py --week2
    python scripts/run_alignment.py
    python scripts/build_graph.py
"""

from __future__ import annotations

import pytest
from httpx import ASGITransport, AsyncClient

from curriculum_mapper.api.main import app

BASE = "http://test"


@pytest.fixture
async def client():
    async with AsyncClient(transport=ASGITransport(app=app), base_url=BASE) as ac:
        yield ac


# ── Health ────────────────────────────────────────────────────────────────────

class TestHealth:
    async def test_health_returns_200(self, client):
        r = await client.get("/health")
        assert r.status_code == 200

    async def test_health_has_expected_keys(self, client):
        r = await client.get("/health")
        data = r.json()
        assert "status" in data
        assert "modules" in data
        assert "concepts" in data
        assert "alignments" in data

    async def test_health_modules_nonzero(self, client):
        r = await client.get("/health")
        assert r.json()["modules"] > 0

    async def test_health_concepts_nonzero(self, client):
        r = await client.get("/health")
        assert r.json()["concepts"] > 0


# ── Modules ───────────────────────────────────────────────────────────────────

class TestModulesEndpoints:
    async def test_list_modules_200(self, client):
        r = await client.get("/api/v1/modules/")
        assert r.status_code == 200

    async def test_list_modules_returns_list(self, client):
        r = await client.get("/api/v1/modules/")
        assert isinstance(r.json(), list)

    async def test_list_modules_count_matches_db(self, client):
        r = await client.get("/api/v1/modules/?limit=200")  # above the default page size
        assert len(r.json()) == 69  # 69 Imperial modules (BEng/MEng Years 1-4)

    async def test_list_modules_has_expected_fields(self, client):
        r = await client.get("/api/v1/modules/")
        m = r.json()[0]
        for key in ("code", "title", "level", "credits", "ilo_count"):
            assert key in m, f"Missing key: {key}"

    async def test_list_modules_filter_by_level(self, client):
        r = await client.get("/api/v1/modules/?level=2")
        assert r.status_code == 200
        for m in r.json():
            assert m["level"] == 2

    async def test_list_modules_search(self, client):
        r = await client.get("/api/v1/modules/?search=algorithm")
        assert r.status_code == 200
        results = r.json()
        # At least one module should match
        assert len(results) >= 1
        for m in results:
            assert "algorithm" in m["title"].lower() or "algorithm" in m["description"].lower()

    async def test_list_modules_pagination(self, client):
        r_all = await client.get("/api/v1/modules/")
        r_paged = await client.get("/api/v1/modules/?limit=5&offset=0")
        assert len(r_paged.json()) == 5
        assert r_paged.json()[0]["code"] == r_all.json()[0]["code"]

    async def test_get_module_detail(self, client):
        r = await client.get("/api/v1/modules/IC50001")
        assert r.status_code == 200
        data = r.json()
        assert data["code"] == "IC50001"
        assert "ilos" in data
        assert isinstance(data["ilos"], list)

    async def test_get_module_case_insensitive(self, client):
        r = await client.get("/api/v1/modules/ic50001")
        assert r.status_code == 200
        assert r.json()["code"] == "IC50001"

    async def test_get_module_not_found(self, client):
        r = await client.get("/api/v1/modules/XX99999")
        assert r.status_code == 404

    async def test_get_module_concepts(self, client):
        r = await client.get("/api/v1/modules/IC50001/concepts")
        assert r.status_code == 200
        concepts = r.json()
        assert isinstance(concepts, list)
        assert len(concepts) > 0
        assert "term" in concepts[0]
        assert "confidence" in concepts[0]

    async def test_get_module_concepts_sorted_by_confidence(self, client):
        r = await client.get("/api/v1/modules/IC50001/concepts")
        concepts = r.json()
        if len(concepts) > 1:
            confidences = [c["confidence"] for c in concepts]
            assert confidences == sorted(confidences, reverse=True)

    async def test_get_module_alignments(self, client):
        r = await client.get("/api/v1/modules/IC50001/alignments")
        assert r.status_code == 200
        alignments = r.json()
        assert isinstance(alignments, list)
        if alignments:
            a = alignments[0]
            assert "ka_code" in a
            assert "score" in a
            assert 0.0 <= a["score"] <= 1.0

    async def test_get_module_neighbors(self, client):
        r = await client.get("/api/v1/modules/IC50001/neighbors")
        assert r.status_code == 200
        neighbors = r.json()
        assert isinstance(neighbors, list)

    async def test_get_module_neighbors_not_found(self, client):
        r = await client.get("/api/v1/modules/ZZZZZ/neighbors")
        assert r.status_code == 404


# ── Concepts ──────────────────────────────────────────────────────────────────

class TestConceptsEndpoints:
    async def test_list_concepts_200(self, client):
        r = await client.get("/api/v1/concepts/")
        assert r.status_code == 200

    async def test_list_concepts_returns_list(self, client):
        r = await client.get("/api/v1/concepts/")
        assert isinstance(r.json(), list)

    async def test_list_concepts_has_fields(self, client):
        r = await client.get("/api/v1/concepts/?limit=1")
        concepts = r.json()
        assert len(concepts) == 1
        c = concepts[0]
        for key in ("id", "term", "confidence", "extractors", "module_codes"):
            assert key in c

    async def test_list_concepts_filter_by_module(self, client):
        r = await client.get("/api/v1/concepts/?module=IC50001")
        concepts = r.json()
        for c in concepts:
            assert "IC50001" in c["module_codes"]

    async def test_list_concepts_search(self, client):
        r = await client.get("/api/v1/concepts/?search=sort")
        concepts = r.json()
        for c in concepts:
            assert "sort" in c["term"].lower()

    async def test_list_concepts_min_confidence(self, client):
        r = await client.get("/api/v1/concepts/?min_confidence=0.9")
        for c in r.json():
            assert c["confidence"] >= 0.9

    async def test_get_concept_by_id(self, client):
        # Get a concept ID from the list first
        r_list = await client.get("/api/v1/concepts/?limit=1")
        cid = r_list.json()[0]["id"]
        r = await client.get(f"/api/v1/concepts/{cid}")
        assert r.status_code == 200
        assert r.json()["id"] == cid

    async def test_get_concept_not_found(self, client):
        r = await client.get("/api/v1/concepts/nonexistent-id-12345")
        assert r.status_code == 404

    async def test_get_concept_alignments(self, client):
        r_list = await client.get("/api/v1/concepts/?limit=1")
        cid = r_list.json()[0]["id"]
        r = await client.get(f"/api/v1/concepts/{cid}/alignments")
        assert r.status_code == 200
        assert isinstance(r.json(), list)


# ── Alignments ────────────────────────────────────────────────────────────────

class TestAlignmentsEndpoints:
    async def test_list_alignments_200(self, client):
        r = await client.get("/api/v1/alignments/")
        assert r.status_code == 200

    async def test_list_alignments_returns_list(self, client):
        r = await client.get("/api/v1/alignments/")
        assert isinstance(r.json(), list)

    async def test_list_alignments_filter_by_ka(self, client):
        r = await client.get("/api/v1/alignments/?ka=AL")
        for a in r.json():
            assert a["ka_code"] == "AL"

    async def test_list_alignments_filter_ambiguous(self, client):
        r = await client.get("/api/v1/alignments/?ambiguous=true")
        for a in r.json():
            assert a["is_ambiguous"] is True

    async def test_list_alignments_filter_by_rank(self, client):
        r = await client.get("/api/v1/alignments/?rank=1")
        for a in r.json():
            assert a["rank"] == 1

    async def test_alignment_stats_200(self, client):
        r = await client.get("/api/v1/alignments/stats")
        assert r.status_code == 200

    async def test_alignment_stats_fields(self, client):
        r = await client.get("/api/v1/alignments/stats")
        data = r.json()
        for key in ("total", "by_ka", "by_method", "ambiguous_count"):
            assert key in data

    async def test_alignment_stats_total_nonzero(self, client):
        r = await client.get("/api/v1/alignments/stats")
        assert r.json()["total"] > 0

    async def test_validate_alignment_accept(self, client):
        # Get a real alignment ID
        r_list = await client.get("/api/v1/alignments/?limit=1&rank=1")
        alignment_id = r_list.json()[0]["id"]
        r = await client.patch(
            f"/api/v1/alignments/{alignment_id}/validate",
            json={"action": "accept"},
        )
        assert r.status_code == 200
        assert r.json()["action"] == "accept"

    async def test_validate_alignment_reject(self, client):
        r_list = await client.get("/api/v1/alignments/?limit=2&rank=1")
        alignment_id = r_list.json()[1]["id"]
        r = await client.patch(
            f"/api/v1/alignments/{alignment_id}/validate",
            json={"action": "reject", "comment": "Incorrect KA"},
        )
        assert r.status_code == 200
        assert r.json()["action"] == "reject"

    async def test_validate_alignment_reset_undoes_decision(self, client):
        # accept then reset returns the alignment to unvalidated — this backs the
        # one-click "undo" offered in the UI after a validation action.
        r_list = await client.get("/api/v1/alignments/?limit=3&rank=1")
        alignment_id = r_list.json()[2]["id"]
        await client.patch(
            f"/api/v1/alignments/{alignment_id}/validate", json={"action": "accept"}
        )
        after = await client.get("/api/v1/alignments/?rank=1&limit=1000")
        assert next(a["validated"] for a in after.json() if a["id"] == alignment_id) is True

        r = await client.patch(
            f"/api/v1/alignments/{alignment_id}/validate", json={"action": "reset"}
        )
        assert r.status_code == 200
        assert r.json()["action"] == "reset"
        after2 = await client.get("/api/v1/alignments/?rank=1&limit=1000")
        assert next(a["validated"] for a in after2.json() if a["id"] == alignment_id) is None

    async def test_validate_alignment_invalid_action(self, client):
        r_list = await client.get("/api/v1/alignments/?limit=1")
        alignment_id = r_list.json()[0]["id"]
        r = await client.patch(
            f"/api/v1/alignments/{alignment_id}/validate",
            json={"action": "banana"},
        )
        assert r.status_code == 422

    async def test_validate_alignment_not_found(self, client):
        r = await client.patch(
            "/api/v1/alignments/nonexistent-id/validate",
            json={"action": "accept"},
        )
        assert r.status_code == 404

    async def test_validate_alignment_reassign_requires_ka(self, client):
        r_list = await client.get("/api/v1/alignments/?limit=1")
        alignment_id = r_list.json()[0]["id"]
        r = await client.patch(
            f"/api/v1/alignments/{alignment_id}/validate",
            json={"action": "reassign"},  # missing new_ka_code
        )
        assert r.status_code == 422

    async def test_validate_alignment_reassign_updates_row(self, client):
        # Reassigning should change the alignment's KA and mark it accepted,
        # so the change is visible when the row is re-fetched.
        r_list = await client.get("/api/v1/alignments/?limit=5&rank=1")
        target = r_list.json()[0]
        new_ka = "GV" if target["ka_code"] != "GV" else "OS"
        r = await client.patch(
            f"/api/v1/alignments/{target['id']}/validate",
            json={"action": "reassign", "new_ka_code": new_ka},
        )
        assert r.status_code == 200
        refetched = await client.get(f"/api/v1/alignments/?ka={new_ka}&rank=1&limit=500")
        match = [a for a in refetched.json() if a["id"] == target["id"]]
        assert match, "reassigned alignment should now appear under the new KA"
        assert match[0]["ka_code"] == new_ka
        assert match[0]["validated"] is True


# ── Graph ─────────────────────────────────────────────────────────────────────

class TestGraphEndpoints:
    async def test_module_module_graph_200(self, client):
        r = await client.get("/api/v1/graph/module-module")
        assert r.status_code == 200

    async def test_module_module_graph_structure(self, client):
        r = await client.get("/api/v1/graph/module-module")
        data = r.json()
        assert "nodes" in data
        assert "edges" in data
        assert len(data["nodes"]) == 69
        assert len(data["edges"]) > 0

    async def test_module_module_graph_node_has_community(self, client):
        r = await client.get("/api/v1/graph/module-module?include_communities=true")
        nodes = r.json()["nodes"]
        for node in nodes:
            assert "community" in node["data"]

    async def test_module_module_graph_node_has_centrality(self, client):
        r = await client.get("/api/v1/graph/module-module?include_centrality=true")
        nodes = r.json()["nodes"]
        for node in nodes:
            assert "degree" in node["data"]

    async def test_bipartite_graph_200(self, client):
        r = await client.get("/api/v1/graph/module-concept")
        assert r.status_code == 200

    async def test_bipartite_graph_filtered_by_module(self, client):
        r = await client.get("/api/v1/graph/module-concept?module=IC50001")
        assert r.status_code == 200
        data = r.json()
        # Should have module node + concept nodes
        node_ids = [n["data"]["id"] for n in data["nodes"]]
        assert "IC50001" in node_ids

    async def test_bipartite_graph_unknown_module(self, client):
        r = await client.get("/api/v1/graph/module-concept?module=ZZZZ")
        assert r.status_code == 404

    async def test_concept_acm_graph_200(self, client):
        r = await client.get("/api/v1/graph/concept-acm")
        assert r.status_code == 200

    async def test_communities_endpoint(self, client):
        r = await client.get("/api/v1/graph/communities")
        assert r.status_code == 200
        data = r.json()
        assert "communities" in data
        assert isinstance(data["communities"], dict)
        assert len(data["communities"]) == 69

    async def test_centrality_endpoint(self, client):
        r = await client.get("/api/v1/graph/centrality")
        assert r.status_code == 200
        data = r.json()
        assert "centrality" in data
        # Each node should have degree, betweenness, eigenvector
        for node, vals in data["centrality"].items():
            assert "degree" in vals


# ── Reports ───────────────────────────────────────────────────────────────────

class TestReportsEndpoints:
    async def test_coverage_200(self, client):
        r = await client.get("/api/v1/reports/coverage")
        assert r.status_code == 200

    async def test_coverage_returns_18_kas(self, client):
        r = await client.get("/api/v1/reports/coverage")
        assert len(r.json()) == 18

    async def test_coverage_has_fields(self, client):
        r = await client.get("/api/v1/reports/coverage")
        item = r.json()[0]
        for key in ("ka_code", "ka_name", "coverage", "severity"):
            assert key in item

    async def test_coverage_sorted_descending(self, client):
        r = await client.get("/api/v1/reports/coverage")
        coverages = [item["coverage"] for item in r.json()]
        assert coverages == sorted(coverages, reverse=True)

    async def test_gaps_200(self, client):
        r = await client.get("/api/v1/reports/gaps")
        assert r.status_code == 200
        assert isinstance(r.json(), list)

    async def test_redundancies_200(self, client):
        r = await client.get("/api/v1/reports/redundancies")
        assert r.status_code == 200
        for item in r.json():
            assert "concept" in item
            assert "module_count" in item

    async def test_summary_200(self, client):
        r = await client.get("/api/v1/reports/summary")
        assert r.status_code == 200

    async def test_summary_fields(self, client):
        r = await client.get("/api/v1/reports/summary")
        data = r.json()
        for key in (
            "total_modules", "total_concepts", "total_alignments",
            "ka_coverage_fraction", "covered_kas", "total_kas",
        ):
            assert key in data

    async def test_summary_totals_correct(self, client):
        r = await client.get("/api/v1/reports/summary")
        data = r.json()
        assert data["total_modules"] == 69
        assert data["total_concepts"] > 0
        assert data["total_alignments"] > 0
        assert 0.0 <= data["ka_coverage_fraction"] <= 1.0

    async def test_export_200(self, client):
        r = await client.get("/api/v1/reports/export")
        assert r.status_code == 200

    async def test_export_top_level_keys(self, client):
        r = await client.get("/api/v1/reports/export")
        data = r.json()
        for key in ("generated_at", "summary", "modules", "concepts", "alignments",
                    "ka_coverage", "gaps", "redundancies"):
            assert key in data, f"Missing key: {key}"

    async def test_export_summary_counts(self, client):
        r = await client.get("/api/v1/reports/export")
        data = r.json()
        assert data["summary"]["total_modules"] == 69
        assert data["summary"]["total_concepts"] > 0
        assert data["summary"]["total_alignments"] > 0

    async def test_export_modules_list(self, client):
        r = await client.get("/api/v1/reports/export")
        data = r.json()
        assert len(data["modules"]) == 69
        assert all("code" in m and "title" in m and "level" in m for m in data["modules"])

    async def test_export_alignments_have_score(self, client):
        r = await client.get("/api/v1/reports/export")
        data = r.json()
        for a in data["alignments"][:10]:
            assert "score" in a
            assert 0.0 <= a["score"] <= 1.0

    async def test_export_ka_coverage_18_kas(self, client):
        r = await client.get("/api/v1/reports/export")
        data = r.json()
        assert len(data["ka_coverage"]) == 18
