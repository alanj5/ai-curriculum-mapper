"""FastAPI dependency injection — shared resources loaded once at startup."""

from __future__ import annotations

import json
from functools import lru_cache

from curriculum_mapper.config import GRAPH_STATS_PATH, STANDARDS_DIR
from curriculum_mapper.graph.builder import load_graph
from curriculum_mapper.ingestion.storage import StorageManager


@lru_cache(maxsize=1)
def get_storage() -> StorageManager:
    return StorageManager()


@lru_cache(maxsize=1)
def get_ka_data() -> dict:
    ka_path = STANDARDS_DIR / "cs2023_ka.json"
    with open(ka_path) as f:
        return json.load(f)


def get_graph_module_module():
    """Load cached module-module NetworkX graph (None if not built yet).

    Uses the DB-namespaced cache via ``builder.load_graph`` so the API and the
    build step always agree on the location.
    """
    return load_graph("module_module")


def get_graph_bipartite():
    return load_graph("bipartite")


def get_graph_concept_acm():
    return load_graph("concept_acm")


def get_graph_concept_prerequisite():
    """Load the cached directed concept→concept prerequisite graph (DAG)."""
    return load_graph("concept_prerequisites")


def get_graph_stats() -> dict | None:
    """Load pre-computed graph stats (built by build_graph.py)."""
    p = GRAPH_STATS_PATH
    if not p.exists():
        return None
    with open(p) as f:
        return json.load(f)
