#!/usr/bin/env python3
"""Acquire a curated subset of MIT OpenCourseWare Computer Science courses and
build the combined ``curriculum_multi.db`` (Imperial + MIT OCW).

This realises the interim's stretch goal (§3.5 "applying our approach to alternate
curricula/data sources (MIT OCW modules) ... contrasting concept maps between
degree programmes"; §4.2 external evaluation dataset). MIT OCW material is used
under its CC BY-NC-SA 4.0 licence with attribution (interim §5.4); each course
records its OCW ``source_url``.

The courses are written to ``data/raw/modules_mit_ocw/`` — a directory that the
canonical ingest does NOT scan — so the canonical ``curriculum.db`` (Imperial
only) is never polluted. The combined corpus lives in a separate, DB-namespaced
``curriculum_multi.db``, used for the cross-programme filter and comparison.

Course descriptions and syllabus topics are curated from the MIT OpenCourseWare
course pages (linked via ``source_url``); they are reduced subsets as the interim
sanctioned ("conducted on a reduced subset of modules").

Usage:
    python scripts/fetch_mit_ocw.py            # write the curated MIT OCW JSONs
    python scripts/fetch_mit_ocw.py --build    # also build data/curriculum_multi.db end-to-end
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path

BASE = Path(__file__).parent.parent
OCW_DIR = BASE / "data" / "raw" / "modules_mit_ocw"
MULTI_DB = BASE / "data" / "curriculum_multi.db"
OCW = "https://ocw.mit.edu/courses/"
LICENCE = "CC BY-NC-SA 4.0 (MIT OpenCourseWare)"

# Curated MIT OCW CS courses (description + key syllabus topics from the OCW
# course pages linked in source_url). Level: 1 = introductory, 2 = core, 3 = advanced.
MODULES = [
    {
        "code": "MIT60001", "title": "Introduction to Computer Science and Programming in Python",
        "level": 1, "source_url": OCW + "6-0001-introduction-to-computer-science-and-programming-in-python-fall-2016/",
        "description": "An introduction to computer science as a tool to solve real-world analytical problems using Python, covering computational thinking, algorithms and basic data structures.",
        "learning_objectives": ["Write, debug and reason about small Python programs", "Use core data structures and recursion", "Analyse simple algorithmic complexity"],
        "topics": ["Python programming", "Branching and iteration", "Functions and recursion", "Tuples, lists and dictionaries", "Object-oriented programming", "Algorithmic complexity", "Searching and sorting", "Plotting and simple simulations"],
    },
    {
        "code": "MIT60042", "title": "Mathematics for Computer Science",
        "level": 1, "source_url": OCW + "6-042j-mathematics-for-computer-science-spring-2015/",
        "description": "Discrete mathematics and probability for computer science: logical reasoning, proof techniques, fundamental structures and probabilistic analysis.",
        "learning_objectives": ["Construct rigorous mathematical proofs", "Reason about discrete structures and graphs", "Apply counting and probability to computing problems"],
        "topics": ["Mathematical proofs and induction", "Propositional and predicate logic", "Number theory", "Graph theory", "Relations and partial orders", "Counting and combinatorics", "Discrete probability", "Random variables and expectation"],
    },
    {
        "code": "MIT60006", "title": "Introduction to Algorithms",
        "level": 2, "source_url": OCW + "6-006-introduction-to-algorithms-spring-2020/",
        "description": "Mathematical modelling of computational problems and the common algorithms, algorithmic paradigms and data structures used to solve them, with an emphasis on performance analysis.",
        "learning_objectives": ["Analyse the time and space complexity of algorithms", "Select appropriate data structures", "Design algorithms using standard paradigms"],
        "topics": ["Asymptotic complexity analysis", "Sorting algorithms", "Hashing and hash tables", "Binary search trees", "Graph search (BFS, DFS)", "Shortest paths (Dijkstra, Bellman-Ford)", "Dynamic programming", "Greedy algorithms"],
    },
    {
        "code": "MIT60004", "title": "Computation Structures",
        "level": 2, "source_url": OCW + "6-004-computation-structures-spring-2017/",
        "description": "The design of digital systems and computer architecture, from MOS transistors and Boolean logic up to pipelined processors, memory hierarchy and operating-system support.",
        "learning_objectives": ["Design combinational and sequential digital circuits", "Explain processor datapath and control", "Reason about memory hierarchy and performance"],
        "topics": ["Boolean algebra and digital logic", "Combinational and sequential circuits", "Instruction set architecture", "Assembly language", "Processor datapath and control", "Pipelining", "Caches and memory hierarchy", "Virtual memory"],
    },
    {
        "code": "MIT60005", "title": "Elements of Software Construction",
        "level": 2, "source_url": OCW + "6-005-elements-of-software-construction-fall-2011/",
        "description": "Fundamental principles and techniques for building correct, robust and maintainable software, including specification, abstraction, testing and concurrency.",
        "learning_objectives": ["Write specifications and abstract data types", "Design and test robust software", "Reason about concurrency"],
        "topics": ["Specifications and abstraction", "Abstract data types", "Test-driven development", "Immutability and design patterns", "Version control", "Concurrency and synchronisation", "Event-driven programming", "Software design"],
    },
    {
        "code": "MIT60046", "title": "Design and Analysis of Algorithms",
        "level": 2, "source_url": OCW + "6-046j-design-and-analysis-of-algorithms-spring-2015/",
        "description": "Techniques for the design and analysis of efficient algorithms, emphasising paradigms, amortised analysis, network flow, intractability and approximation.",
        "learning_objectives": ["Apply algorithm-design paradigms to new problems", "Prove correctness and complexity", "Recognise NP-hard problems and design approximations"],
        "topics": ["Divide and conquer", "Dynamic programming", "Greedy algorithms", "Amortised analysis", "Network flow", "Linear programming", "NP-completeness", "Approximation algorithms"],
    },
    {
        "code": "MIT60041", "title": "Probabilistic Systems Analysis and Applied Probability",
        "level": 2, "source_url": OCW + "6-041-probabilistic-systems-analysis-and-applied-probability-fall-2010/",
        "description": "The fundamentals of probability and its applications to modelling uncertainty and analysing stochastic systems.",
        "learning_objectives": ["Model uncertainty with probability", "Compute with random variables", "Apply Bayesian inference and Markov chains"],
        "topics": ["Probability models", "Conditional probability and Bayes' rule", "Discrete and continuous random variables", "Expectation and variance", "Bayesian inference", "Limit theorems", "Markov chains", "Bernoulli and Poisson processes"],
    },
    {
        "code": "MIT60033", "title": "Computer System Engineering",
        "level": 3, "source_url": OCW + "6-033-computer-system-engineering-spring-2018/",
        "description": "Principles and abstractions for engineering computer systems, spanning operating systems, networking, distributed systems, fault tolerance and security.",
        "learning_objectives": ["Apply modularity and abstraction to systems", "Reason about networking and distributed protocols", "Analyse fault tolerance and security"],
        "topics": ["Operating system structure", "Naming and abstraction", "Client-server and networking", "Distributed systems", "Transactions and consistency", "Fault tolerance and recovery", "Computer security", "Performance and scalability"],
    },
    {
        "code": "MIT60034", "title": "Artificial Intelligence",
        "level": 3, "source_url": OCW + "6-034-artificial-intelligence-fall-2010/",
        "description": "The knowledge representation, problem solving and learning methods of artificial intelligence.",
        "learning_objectives": ["Formulate problems as search and constraint satisfaction", "Represent knowledge and reason with logic", "Apply core machine-learning methods"],
        "topics": ["State-space search", "Constraint satisfaction", "Adversarial search and games", "Knowledge representation and logic", "Rule-based systems", "Machine learning", "Neural networks", "Support vector machines"],
    },
    {
        "code": "MIT60036", "title": "Introduction to Machine Learning",
        "level": 3, "source_url": OCW + "6-036-introduction-to-machine-learning-fall-2020/",
        "description": "Principles, algorithms and applications of machine learning from the point of view of statistical inference, supervised and reinforcement learning.",
        "learning_objectives": ["Train and evaluate predictive models", "Reason about generalisation and regularisation", "Apply neural networks and reinforcement learning"],
        "topics": ["Linear classifiers and perceptrons", "Logistic and linear regression", "Feature representation", "Support vector machines", "Neural networks and back-propagation", "Regularisation and generalisation", "Clustering", "Reinforcement learning"],
    },
    {
        "code": "MIT60045", "title": "Automata, Computability, and Complexity",
        "level": 3, "source_url": OCW + "6-045j-automata-computability-and-complexity-spring-2011/",
        "description": "The theory of computation: what problems can be solved by computers, and at what cost, via automata, computability and complexity theory.",
        "learning_objectives": ["Classify languages by automata", "Prove problems undecidable", "Reason about complexity classes and reductions"],
        "topics": ["Finite automata and regular languages", "Context-free grammars", "Pushdown automata", "Turing machines", "Decidability and undecidability", "Reductions", "Time and space complexity", "P, NP and NP-completeness"],
    },
    {
        "code": "MIT60830", "title": "Database Systems",
        "level": 3, "source_url": OCW + "6-830-database-systems-fall-2010/",
        "description": "The architecture and internals of relational database management systems, including query processing, transactions and distributed data.",
        "learning_objectives": ["Design and query relational schemas", "Explain query optimisation", "Reason about transactions and concurrency"],
        "topics": ["Relational model and SQL", "Storage and indexing", "Query processing and optimisation", "Transactions and ACID", "Concurrency control", "Recovery and logging", "Distributed databases", "Column stores and modern systems"],
    },
    {
        "code": "MIT60837", "title": "Computer Graphics",
        "level": 3, "source_url": OCW + "6-837-computer-graphics-fall-2012/",
        "description": "The fundamentals of computer graphics: representing, rendering and animating three-dimensional scenes.",
        "learning_objectives": ["Implement ray tracing and rasterisation", "Apply geometric transformations", "Model curves, surfaces and animation"],
        "topics": ["Ray tracing", "Geometric transformations", "Rasterisation and the graphics pipeline", "Shading and illumination models", "Texture mapping", "Curves and surfaces", "Animation", "Sampling and anti-aliasing"],
    },
    {
        "code": "MIT60858", "title": "Computer Systems Security",
        "level": 3, "source_url": OCW + "6-858-computer-systems-security-fall-2014/",
        "description": "The design and implementation of secure computer systems, covering threats, attacks, cryptography and defensive techniques.",
        "learning_objectives": ["Analyse threat models and attacks", "Apply cryptographic primitives", "Design defences for systems and the web"],
        "topics": ["Threat models", "Buffer overflows and control-flow attacks", "Privilege separation", "Web security", "Cryptography and key exchange", "Authentication", "Network security", "Privacy and anonymity"],
    },
]


def write_modules() -> None:
    OCW_DIR.mkdir(parents=True, exist_ok=True)
    for f in OCW_DIR.glob("*.json"):
        f.unlink()
    for m in MODULES:
        record = dict(m)
        record["credits"] = 8
        record["source"] = "mit_ocw"
        record["programmes"] = ["mit_ocw_cs"]
        record["licence"] = LICENCE
        with open(OCW_DIR / f"{m['code']}.json", "w") as fh:
            json.dump(record, fh, indent=2)
    print(f"Wrote {len(MODULES)} MIT OCW course files to {OCW_DIR}")


def ingest_mit_into(db_path: Path) -> int:
    """Ingest the MIT OCW courses (programmes=mit_ocw_cs) into ``db_path``."""
    from curriculum_mapper.ingestion.loader import load_from_ocw_json
    from curriculum_mapper.ingestion.storage import StorageManager

    storage = StorageManager(db_path)
    n = 0
    for path in sorted(OCW_DIR.glob("*.json")):
        m = load_from_ocw_json(path)
        if m is None:
            continue
        m.programmes = ["mit_ocw_cs"]
        storage.insert_module(m)
        n += 1
    return n


def build_multi() -> None:
    """Build data/curriculum_multi.db = Imperial + MIT OCW, then the full pipeline."""
    env = {**os.environ, "CURRICULUM_DB_PATH": str(MULTI_DB)}
    py = sys.executable
    if MULTI_DB.exists():
        MULTI_DB.unlink()
    for suffix in ("-wal", "-shm"):
        p = MULTI_DB.with_name(MULTI_DB.name + suffix)
        if p.exists():
            p.unlink()

    def run(*args):
        print(f"\n$ CURRICULUM_DB_PATH={MULTI_DB.name} {' '.join(args)}")
        subprocess.run([py, *args], env=env, cwd=str(BASE), check=True)

    run("scripts/ingest_modules.py")            # Imperial → multi DB (with programmes)
    n = ingest_mit_into(MULTI_DB)               # + MIT OCW (mit_ocw_cs)
    print(f"Ingested {n} MIT OCW courses into {MULTI_DB.name}")
    run("scripts/run_nlp_pipeline.py", "--week2")
    run("scripts/run_alignment.py")
    run("scripts/build_graph.py")
    run("scripts/run_plo_alignment.py")
    print(f"\nBuilt {MULTI_DB} (Imperial + MIT OCW). Serve it with `make serve-multi`.")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--build", action="store_true", help="also build data/curriculum_multi.db end-to-end")
    args = ap.parse_args()
    write_modules()
    if args.build:
        sys.path.insert(0, str(BASE))
        build_multi()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
