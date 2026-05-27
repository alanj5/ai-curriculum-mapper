"""Shared pytest fixtures."""

from __future__ import annotations

import json
import tempfile
from pathlib import Path

import pytest

from curriculum_mapper.ingestion.schema import ILO, ModuleDescriptor
from curriculum_mapper.ingestion.storage import StorageManager


@pytest.fixture(scope="session")
def sample_module_data() -> dict:
    fixture = Path(__file__).parent / "fixtures" / "sample_module.json"
    with open(fixture) as f:
        return json.load(f)


@pytest.fixture(scope="session")
def sample_ka_data() -> dict:
    fixture = Path(__file__).parent / "fixtures" / "sample_ka_topics.json"
    with open(fixture) as f:
        return json.load(f)


@pytest.fixture(scope="session")
def algorithms_module() -> ModuleDescriptor:
    """A realistic algorithms module for NLP testing."""
    return ModuleDescriptor(
        code="TEST101",
        title="Introduction to Algorithms and Data Structures",
        level=2,
        credits=12,
        prerequisites=[],
        description=(
            "This module introduces fundamental algorithms and data structures. "
            "Topics include sorting algorithms such as merge sort, quicksort, and heapsort. "
            "Students study graph algorithms including breadth-first search, depth-first search, "
            "Dijkstra shortest path algorithm, and minimum spanning trees. "
            "Dynamic programming and greedy algorithms are covered with examples. "
            "Students analyse time and space complexity using asymptotic notation "
            "including Big-O, Big-Theta and Big-Omega. "
            "Data structures: hash tables, binary search trees, priority queues, heaps."
        ),
        ilos=[
            ILO(text="Implement and analyse sorting algorithms including merge sort and quicksort"),
            ILO(text="Apply graph algorithms to solve shortest path and spanning tree problems"),
            ILO(text="Use dynamic programming to solve optimisation problems"),
            ILO(text="Analyse the time and space complexity of algorithms using Big-O notation"),
            ILO(text="Design and implement hash tables, binary search trees and priority queues"),
        ],
        topics=["Sorting algorithms", "Graph algorithms", "Dynamic programming",
                "Complexity analysis", "Hash tables", "Binary search trees"],
        source="institutional",
        source_file="TEST101.json",
    )


@pytest.fixture(scope="session")
def os_module() -> ModuleDescriptor:
    """An operating systems module."""
    return ModuleDescriptor(
        code="TEST202",
        title="Operating Systems",
        level=2,
        credits=12,
        prerequisites=["TEST101"],
        description=(
            "Core concepts of operating system design and implementation. "
            "Topics include process management, threads, CPU scheduling algorithms "
            "(round-robin, priority scheduling, FCFS), virtual memory with paging and "
            "segmentation, deadlock detection and prevention, file systems, and "
            "inter-process communication via pipes, semaphores and shared memory. "
            "Students implement components of an operating system in C."
        ),
        ilos=[
            ILO(text="Explain the role and structure of operating system kernels"),
            ILO(text="Implement CPU scheduling algorithms and compare their performance"),
            ILO(text="Describe virtual memory using paging and page replacement algorithms"),
            ILO(text="Apply synchronisation primitives to avoid race conditions and deadlock"),
            ILO(text="Design a simple file system with directory structures"),
        ],
        topics=["Processes", "Threads", "Scheduling", "Virtual memory",
                "Deadlock", "File systems", "Inter-process communication"],
        source="institutional",
        source_file="TEST202.json",
    )


@pytest.fixture
def temp_db() -> StorageManager:
    """In-memory / temp SQLite DB for isolated unit tests."""
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        db_path = Path(f.name)
    storage = StorageManager(db_path=db_path)
    yield storage
    db_path.unlink(missing_ok=True)


@pytest.fixture(scope="session")
def small_corpus(algorithms_module, os_module) -> list[str]:
    """Small text corpus for testing TF-IDF fitting."""
    return [
        algorithms_module.full_text,
        os_module.full_text,
        (
            "Machine learning techniques including supervised and unsupervised learning. "
            "Neural networks, decision trees, support vector machines and clustering."
        ),
        (
            "Database systems: relational model, SQL, normalisation, "
            "transactions and ACID properties, indexing and query optimisation."
        ),
        (
            "Computer networks: TCP/IP model, routing protocols, "
            "congestion control, HTTP, DNS and network security."
        ),
    ]
