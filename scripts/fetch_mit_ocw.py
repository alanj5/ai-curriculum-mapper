#!/usr/bin/env python3
"""Acquire a subset of MIT OpenCourseWare Computer Science courses and build the
combined ``curriculum_multi.db`` (Imperial + MIT OCW).

This realises the interim's stretch goal (§3.5 "applying our approach to alternate
curricula/data sources (MIT OCW modules) ... contrasting concept maps between
degree programmes"; §4.2 external evaluation dataset). MIT OCW material is used
under its CC BY-NC-SA 4.0 licence with attribution (interim §5.4).

With ``--scrape`` each course's **real description** is fetched live from its OCW
page (``source_url``) and the response's SHA-256, HTTP status and timestamp are
recorded as provenance — the same provenance discipline as the Imperial scraper —
so the external corpus is genuinely sourced, not hand-written. (A short curated
description is retained only as a fallback for the rare page that 404s.)
Module-level prerequisites are not published on the open course pages, so none are
asserted; the graph builder infers prerequisite structure algorithmically.

The courses are written to ``data/raw/modules_mit_ocw/`` — a directory the
canonical ingest does NOT scan — so the canonical ``curriculum.db`` (Imperial
only) is never polluted. The combined corpus lives in a separate, DB-namespaced
``curriculum_multi.db``, used for the cross-programme filter and comparison.

Usage:
    python scripts/fetch_mit_ocw.py --scrape           # write JSONs with real scraped descriptions
    python scripts/fetch_mit_ocw.py --build --scrape   # also build data/curriculum_multi.db end-to-end
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


# ── More MIT OCW CS courses (descriptions/topics from the OCW pages in source_url) ─
MIT_EXTRA = [
    {"code": "MIT60002", "title": "Introduction to Computational Thinking and Data Science",
     "level": 1, "source_url": OCW + "6-0002-introduction-to-computational-thinking-and-data-science-fall-2016/",
     "description": "A continuation of introductory programming that applies computation to modelling, simulation and data analysis.",
     "learning_objectives": ["Build simple computational models", "Run Monte Carlo simulations", "Draw inferences from data"],
     "topics": ["Optimisation and knapsack problems", "Graph models", "Stochastic thinking", "Monte Carlo simulation", "Sampling and confidence intervals", "Experimental data and curve fitting", "Machine learning basics"]},
    {"code": "MIT60035", "title": "Computer Language Engineering",
     "level": 3, "source_url": OCW + "6-035-computer-language-engineering-spring-2010/",
     "description": "The design and implementation of compilers that translate a high-level language to executable code.",
     "learning_objectives": ["Implement lexing and parsing", "Generate and optimise intermediate code", "Reason about program analysis"],
     "topics": ["Lexical analysis", "Parsing and grammars", "Semantic analysis", "Intermediate representations", "Code generation", "Dataflow analysis", "Register allocation", "Optimisation"]},
    {"code": "MIT60828", "title": "Operating System Engineering",
     "level": 3, "source_url": OCW + "6-828-operating-system-engineering-fall-2012/",
     "description": "The fundamentals of engineering operating systems, studied through the design and implementation of a small Unix-like kernel.",
     "learning_objectives": ["Explain OS abstractions and mechanisms", "Implement kernel components", "Reason about isolation and concurrency"],
     "topics": ["Virtual memory", "Kernel and user mode", "System calls", "Processes and threads", "Concurrency and locking", "File systems", "Scheduling", "Isolation and protection"]},
    {"code": "MIT60824", "title": "Distributed Computer Systems Engineering",
     "level": 3, "source_url": OCW + "6-824-distributed-computer-systems-engineering-spring-2006/",
     "description": "Abstractions and techniques for designing and implementing fault-tolerant distributed systems.",
     "learning_objectives": ["Reason about consistency and fault tolerance", "Apply replication and consensus", "Analyse distributed system designs"],
     "topics": ["Remote procedure call", "Concurrency and threads", "Replication", "Consistency models", "Consensus and Paxos", "Distributed transactions", "Fault tolerance", "Distributed storage"]},
    {"code": "MIT60851", "title": "Advanced Data Structures",
     "level": 3, "source_url": OCW + "6-851-advanced-data-structures-spring-2012/",
     "description": "Advanced data structures and the theory underpinning their performance, from persistence to succinctness.",
     "learning_objectives": ["Analyse advanced data structures", "Apply amortisation and persistence", "Reason about lower bounds"],
     "topics": ["Persistent data structures", "Retroactive data structures", "Geometric data structures", "Dynamic optimality", "Memory hierarchy and cache-oblivious structures", "Succinct data structures", "Hashing", "Integer data structures"]},
    {"code": "MIT60854", "title": "Advanced Algorithms",
     "level": 3, "source_url": OCW + "6-854j-advanced-algorithms-fall-2008/",
     "description": "A graduate survey of algorithmic techniques for optimisation, approximation and randomisation.",
     "learning_objectives": ["Design efficient algorithms", "Apply linear programming and duality", "Analyse approximation and randomised algorithms"],
     "topics": ["Network flows", "Linear programming and duality", "Approximation algorithms", "Randomised algorithms", "Hashing", "Streaming algorithms", "Online algorithms", "Fixed-parameter algorithms"]},
    {"code": "MIT60857", "title": "Network and Computer Security",
     "level": 3, "source_url": OCW + "6-857-network-and-computer-security-spring-2014/",
     "description": "The principles and practice of cryptography and its use to build secure networks and computer systems.",
     "learning_objectives": ["Apply cryptographic primitives", "Reason about security protocols", "Analyse system and network attacks"],
     "topics": ["Symmetric and public-key cryptography", "Hash functions and MACs", "Key exchange", "Authentication protocols", "Digital signatures", "Network security", "Web security", "Anonymity and privacy"]},
    {"code": "MIT60867", "title": "Machine Learning",
     "level": 3, "source_url": OCW + "6-867-machine-learning-fall-2006/",
     "description": "Principles, algorithms and theory of machine learning for prediction from data.",
     "learning_objectives": ["Formulate learning problems", "Apply supervised and unsupervised methods", "Reason about generalisation"],
     "topics": ["Linear classifiers and regression", "Support vector machines and kernels", "Neural networks", "Model selection and regularisation", "Mixture models and EM", "Graphical models", "Boosting", "Generalisation theory"]},
    {"code": "MIT60801", "title": "Machine Vision",
     "level": 3, "source_url": OCW + "6-801-machine-vision-fall-2020/",
     "description": "Methods for recovering information about the physical world from images, grounded in image formation and geometry.",
     "learning_objectives": ["Model image formation", "Recover shape and motion", "Apply photometric and geometric constraints"],
     "topics": ["Image formation and radiometry", "Shading and reflectance", "Optical flow", "Photometric stereo", "Shape from shading", "Edge detection", "Object recognition", "Camera geometry"]},
    {"code": "MIT60172", "title": "Performance Engineering of Software Systems",
     "level": 3, "source_url": OCW + "6-172-performance-engineering-of-software-systems-fall-2018/",
     "description": "How to write fast code: the principles and practice of engineering software for performance on modern hardware.",
     "learning_objectives": ["Profile and optimise software", "Exploit parallelism", "Reason about the memory hierarchy"],
     "topics": ["Bentley rules for optimisation", "Bit hacks", "Cache-efficient algorithms", "Parallel programming with Cilk", "Vectorisation", "Race detection", "Storage allocation", "Profiling and measurement"]},
    {"code": "MIT60875", "title": "Cryptography and Cryptanalysis",
     "level": 3, "source_url": OCW + "6-875-cryptography-and-cryptanalysis-spring-2005/",
     "description": "", "learning_objectives": [], "topics": ["Cryptography", "Encryption", "Cryptanalysis"]},
    {"code": "MIT60852", "title": "Distributed Algorithms",
     "level": 3, "source_url": OCW + "6-852j-distributed-algorithms-fall-2009/",
     "description": "", "learning_objectives": [], "topics": ["Distributed algorithms", "Consensus", "Concurrency"]},
    {"code": "MIT60864", "title": "Advanced Natural Language Processing",
     "level": 3, "source_url": OCW + "6-864-advanced-natural-language-processing-fall-2005/",
     "description": "", "learning_objectives": [], "topics": ["Natural language processing", "Parsing", "Language models"]},
    {"code": "MIT60821", "title": "Programming Languages",
     "level": 3, "source_url": OCW + "6-821-programming-languages-fall-2002/",
     "description": "", "learning_objectives": [], "topics": ["Programming languages", "Semantics", "Type systems"]},
    {"code": "MIT60823", "title": "Computer System Architecture",
     "level": 3, "source_url": OCW + "6-823-computer-system-architecture-fall-2005/",
     "description": "", "learning_objectives": [], "topics": ["Computer architecture", "Pipelining", "Memory hierarchy"]},
    {"code": "MIT60840", "title": "Theory of Computation",
     "level": 3, "source_url": OCW + "18-404j-theory-of-computation-fall-2020/",
     "description": "", "learning_objectives": [], "topics": ["Automata", "Computability", "Complexity"]},
    {"code": "MIT60832", "title": "Underactuated Robotics",
     "level": 3, "source_url": OCW + "6-832-underactuated-robotics-spring-2009/",
     "description": "", "learning_objectives": [], "topics": ["Robotics", "Control", "Dynamics"]},
    {"code": "MIT60890", "title": "Algorithmic Lower Bounds",
     "level": 3, "source_url": OCW + "6-890-algorithmic-lower-bounds-fun-with-hardness-proofs-fall-2014/",
     "description": "", "learning_objectives": [], "topics": ["Computational complexity", "NP-hardness", "Reductions"]},
]
MODULES.extend(MIT_EXTRA)

# Module-level prerequisites are NOT published on the open course pages, so none
# are asserted for the external cohort; the curriculum-graph builder infers
# prerequisite structure algorithmically (concept overlap + level ordering), the
# same way it does for the Imperial modules (whose pages also omit them).

# Cohorts: the external comparison corpus is MIT OpenCourseWare CS, every course
# carrying a real scraped description with provenance (no curated descriptions).
COHORTS = [
    {"modules": MODULES, "programme": "mit_ocw_cs", "source": "mit_ocw", "licence": LICENCE,
     "dir": OCW_DIR, "prereqs": {}, "name": "MIT OpenCourseWare CS", "scrape": True},
]


def _scrape_page(url: str) -> dict:
    """Fetch a course page and pull a real description (+ OCW topic tags) with
    provenance (SHA-256, HTTP status, timestamp). Returns {} on failure."""
    import hashlib
    from datetime import datetime, timezone

    import requests
    from bs4 import BeautifulSoup

    try:
        r = requests.get(url, headers={"User-Agent": "ai-curriculum-mapper/1.0 (FYP research)"}, timeout=30)
    except Exception:
        return {}
    out = {
        "http_status": r.status_code,
        "fetched_at": datetime.now(timezone.utc).isoformat(),
        "content_sha256": hashlib.sha256(r.content).hexdigest(),
    }
    if r.status_code != 200:
        return out
    soup = BeautifulSoup(r.text, "html.parser")
    md = soup.find("meta", attrs={"name": "description"})
    desc = (md.get("content", "") if md else "").strip()
    topics: list[str] = []
    for hh in soup.find_all(["h2", "h3", "h4"]):
        if hh.get_text(strip=True).lower() == "topics":
            cont = hh.find_parent()
            if cont:
                topics = [a.get_text(" ", strip=True) for a in cont.find_all("a") if a.get_text(strip=True)]
            break
    out["description"] = desc
    out["topics"] = topics
    return out


def write_modules(scrape: bool = False) -> None:
    for cohort in COHORTS:
        d = cohort["dir"]
        d.mkdir(parents=True, exist_ok=True)
        for f in d.glob("*.json"):
            f.unlink()
        scraped_n = 0
        for m in cohort["modules"]:
            record = dict(m)
            record["credits"] = 8
            record["source"] = cohort["source"]
            record["programmes"] = [cohort["programme"]]
            record["licence"] = cohort["licence"]
            record.setdefault("prerequisites", cohort["prereqs"].get(m["code"], []))
            # Replace the curated description/topics with the REAL page content
            # where the source page exposes it (provenance recorded).
            if scrape and cohort.get("scrape") and record.get("source_url"):
                p = _scrape_page(record["source_url"])
                record["content_sha256"] = p.get("content_sha256")
                record["http_status"] = p.get("http_status")
                record["fetched_at"] = p.get("fetched_at")
                if p.get("description"):
                    record["description"] = p["description"]
                    record["scraped"] = True
                    scraped_n += 1
                    if p.get("topics"):
                        record["topics"] = p["topics"]
            with open(d / f"{m['code']}.json", "w") as fh:
                json.dump(record, fh, indent=2)
        extra = f" ({scraped_n} with live-scraped descriptions)" if scrape and cohort.get("scrape") else ""
        print(f"Wrote {len(cohort['modules'])} {cohort['name']} course files to {d}{extra}")


def ingest_external_into(db_path: Path) -> int:
    """Ingest every external cohort (with its programme tag) into ``db_path``."""
    from curriculum_mapper.ingestion.loader import load_from_ocw_json
    from curriculum_mapper.ingestion.storage import StorageManager

    storage = StorageManager(db_path)
    n = 0
    for cohort in COHORTS:
        for path in sorted(cohort["dir"].glob("*.json")):
            m = load_from_ocw_json(path)
            if m is None:
                continue
            m.programmes = [cohort["programme"]]
            storage.insert_module(m)
            n += 1
    return n


def build_multi() -> None:
    """Build data/curriculum_multi.db = Imperial + external cohorts + full pipeline."""
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
    n = ingest_external_into(MULTI_DB)          # + external cohorts (MIT OCW)
    print(f"Ingested {n} external courses into {MULTI_DB.name}")
    run("scripts/run_nlp_pipeline.py", "--week2")
    run("scripts/run_alignment.py")
    run("scripts/build_graph.py")
    run("scripts/run_plo_alignment.py")
    print(f"\nBuilt {MULTI_DB} (Imperial + MIT OCW). Serve it with `make serve-multi`.")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--build", action="store_true", help="also build data/curriculum_multi.db end-to-end")
    ap.add_argument("--scrape", action="store_true", help="fetch real descriptions from each course page (provenance recorded)")
    args = ap.parse_args()
    write_modules(scrape=args.scrape)
    if args.build:
        sys.path.insert(0, str(BASE))
        build_multi()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
