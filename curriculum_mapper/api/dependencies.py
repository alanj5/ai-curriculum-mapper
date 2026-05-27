"""FastAPI dependency injection — shared resources loaded once at startup."""

from __future__ import annotations

import json
import pickle
from functools import lru_cache

from curriculum_mapper.config import GRAPH_CACHE, PROCESSED_DIR, STANDARDS_DIR
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
    """Load cached module-module NetworkX graph (None if not built yet)."""
    p = GRAPH_CACHE / "module_module.pkl"
    if not p.exists():
        return None
    with open(p, "rb") as f:
        return pickle.load(f)


def get_graph_bipartite():
    p = GRAPH_CACHE / "bipartite.pkl"
    if not p.exists():
        return None
    with open(p, "rb") as f:
        return pickle.load(f)


def get_graph_concept_acm():
    p = GRAPH_CACHE / "concept_acm.pkl"
    if not p.exists():
        return None
    with open(p, "rb") as f:
        return pickle.load(f)


def get_graph_stats() -> dict | None:
    """Load pre-computed graph stats (built by build_graph.py)."""
    p = PROCESSED_DIR / "graph_stats.json"
    if not p.exists():
        return None
    with open(p) as f:
        return json.load(f)
