# AI Curriculum Mapper

[![Tests](https://github.com/alanj5/ai-curriculum-mapper/actions/workflows/test.yml/badge.svg)](https://github.com/alanj5/ai-curriculum-mapper/actions/workflows/test.yml)
[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Coverage](https://img.shields.io/badge/coverage-82%25-brightgreen.svg)](#test-coverage-summary-v100)

Automated extraction, alignment, and visualisation of Computing curriculum content against ACM/IEEE CS2023 Knowledge Areas.

**Author:** Alan Jiang — Imperial College London BEng Computing Final Year Project
**Version:** 1.0.0

---

## Overview

The system ingests 69 Imperial College Computing module descriptors (BEng + MEng, Years 1–4), extracts key concepts using five NLP methods (TF-IDF, RAKE, TextRank, KeyBERT, BERTopic), applies a concept-specificity filter and SBERT canonicalisation to yield ~1,885 unique concepts, and aligns each concept to the 18 ACM/IEEE CS2023 Knowledge Areas using a hybrid lexical+semantic aligner. It builds a heterogeneous, typed curriculum graph — **modules, concepts, CS2023 standards, and programme-level outcomes** — over four NetworkX graphs (module-module similarity, bipartite module-concept, concept-CS2023 hierarchy, and a directed **concept-prerequisite DAG**, from which module-level prerequisites are in turn inferred), tags each module with its degree programme(s) (BEng/MEng Computing, with an optional MIT OpenCourseWare comparison cohort), and maps modules to the programme-level outcomes they fulfil. Real ECTS credits and programme outcomes come from the official Imperial Programme Specifications. All results are exposed through an interactive web interface with a programme filter, click-a-concept prerequisite neighbourhoods, and one-click prerequisite-chain tracing.

### Architecture

```mermaid
flowchart LR
    A[Module JSON<br/>descriptors] --> B[Ingestion]
    B --> C[(SQLite<br/>curriculum.db)]
    C --> D[NLP pipeline<br/>5 extractors]
    D --> E[SBERT<br/>canonicaliser]
    E --> C
    F[CS2023 KAs<br/>18 × ~54 topics] --> G[Hybrid aligner<br/>35% lexical + 65% SBERT]
    C --> G
    G --> C
    C --> H[Graph builder<br/>NetworkX + Louvain]
    H --> I[(Graph<br/>pickles)]
    C --> J[FastAPI<br/>31 endpoints]
    I --> J
    J --> K[Vite + Cytoscape.js<br/>web interface]

    style C fill:#e1f5ff,stroke:#003e74
    style I fill:#e1f5ff,stroke:#003e74
    style K fill:#fff4e1,stroke:#A50000
```

**Numbers (canonical `curriculum.db`, BEng + MEng Years 1–4):** 69 modules → 1,885 canonical concepts (after the specificity filter and SBERT canonicalisation) → 2,450 alignment records (28.3% of primary alignments ambiguous) → a module graph of 245 edges (91 shared-concept + 154 inferred prerequisite) across 7 Louvain communities (modularity Q ≈ 0.60). The optional combined `curriculum_multi.db` adds 32 MIT OpenCourseWare CS courses for a 101-module cross-programme comparison. (The pipeline is stochastic — BERTopic UMAP — so these are one committed reference run.)

---

## Screenshots

> Start the app (`make serve` + `cd frontend && npm run dev`) and open
> **http://localhost:5173**. The interface is a five-page, router-based app:
>
> - **Overview** — headline numbers, the best-covered and thinnest Knowledge
>   Areas, and a one-click jump into the Curriculum Map.
> - **Curriculum Map** — the interactive graph (Cytoscape.js fcose) with four
>   views: *how modules relate* (nodes coloured by Louvain community, sized by
>   degree), *by year*, *a module's concepts*, and the directed
>   *concept-prerequisite* flow — plus programme/year filters and one-click
>   prerequisite-chain tracing.
> - **Explore** — search modules or concepts; open any one for its outcomes,
>   topics, prerequisites, CS2023 coverage, and where each concept is taught.
> - **Coverage** — per-KA coverage bar chart, gaps, cross-cutting concepts, and
>   programme-outcome coverage, each drillable to the modules behind it.
> - **Review** — sortable concept × KA table with inline accept / reject /
>   reassign controls and ambiguity highlights (educator workflow).

## Requirements

- Python 3.11+
- Node.js 18+ and npm
- ~2 GB free disk (SBERT model + embeddings cache)

---

## Setup

```bash
# 1. Clone / navigate to project
cd ai-curriculum-mapper

# 2. Create virtual environment
python3 -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate

# 3. Install Python dependencies
pip install -r requirements.txt
pip install -r requirements-dev.txt

# 4. Download NLP models
python -m spacy download en_core_web_sm
python -c "import nltk; nltk.download(['stopwords', 'wordnet', 'punkt', 'averaged_perceptron_tagger'])"

# 5. Install frontend dependencies
cd frontend && npm install && cd ..
```

---

## Running the Pipeline

These steps populate the SQLite database (`data/curriculum.db`) from scratch.  
**Run in order** — each step depends on the previous.

```bash
source .venv/bin/activate

# Step 0 (optional): refresh module JSONs from the live Imperial descriptor pages,
# recording provenance (source URL, fetch timestamp, content hash). Falls back to
# the committed curated data if a page is unavailable. Skip to use the shipped JSONs.
python scripts/fetch_imperial_modules.py

# Step 1: Ingest module descriptors → populates modules, ilos, prerequisites tables
python scripts/ingest_modules.py

# Step 2: Run NLP extraction → populates concepts table (~1,885 concepts, ~3–5 min)
python scripts/run_nlp_pipeline.py --week2

# Step 3: Align concepts to CS2023 KAs → populates alignments table (~1–2 min)
python scripts/run_alignment.py

# Step 4: Build graphs → 4 graphs incl. the directed concept-prerequisite DAG (~30 s)
python scripts/build_graph.py

# Step 5: Map modules to programme-level outcomes (PLOs)
python scripts/run_plo_alignment.py

# Step 6 (optional): Run evaluation against gold annotations
python scripts/run_evaluation.py
```

All steps are **idempotent** — safe to re-run. The DB uses `INSERT OR REPLACE`.

---

## Optional: LLM-augmented extraction

An optional sixth concept extractor uses a **local** LLM via [Ollama](https://ollama.com)
(no external API; preserves the project's privacy-local design). It is **off by
default**, so the standard pipeline, the reported figures, and CI are unchanged and
require no Ollama.

```bash
# 1. Install Ollama and a model (≈5 GB). qwen2.5:7b / llama3.1:8b suit a 16 GB Mac.
brew install ollama
ollama serve &                 # start the local server
ollama pull qwen2.5:7b

# 2. Install the Python client (deliberately not in requirements.txt)
.venv/bin/pip install ollama

# 3. Compare candidate LLM extractors against the ensemble on the gold set
#    (no DB writes; outputs are cached under data/cache/llm/ for reproducibility)
LLM_EXTRACTOR_ENABLED=1 .venv/bin/python scripts/run_evaluation.py --llm-compare

# 4. (Optional) End-to-end: add the LLM as a 6th extractor into a SEPARATE DB,
#    leaving the canonical curriculum.db untouched, then evaluate the augmented run
CURRICULUM_DB_PATH=data/curriculum_llm.db LLM_EXTRACTOR_ENABLED=1 \
  python scripts/run_nlp_pipeline.py --week2 --llm
CURRICULUM_DB_PATH=data/curriculum_llm.db python scripts/run_alignment.py
CURRICULUM_DB_PATH=data/curriculum_llm.db python scripts/build_graph.py
CURRICULUM_DB_PATH=data/curriculum_llm.db python scripts/run_evaluation.py
```

The model is queried at temperature 0 and responses are cached, so reported LLM
numbers reproduce without re-running the model. Configure via `LLM_MODEL`,
`LLM_ENDPOINT`, `LLM_TIMEOUT` (see `config.py`). Graph caches are namespaced by
database, so the augmented run never clobbers the canonical artefacts.

```bash
# Build the augmented pipeline + serve it (demo; canonical `make serve` unaffected)
make pipeline-llm        # build the LLM-augmented (6th-extractor) data/curriculum_llm.db
make serve-llm           # serves the augmented data at http://127.0.0.1:8000
```

---

## Optional: combined corpus + cross-programme comparison

A second, separate database (`curriculum_multi.db`) adds a curated subset of **MIT
OpenCourseWare** Computer Science courses (used under CC BY-NC-SA 4.0, with each
course's OCW URL recorded) to the 69 Imperial modules. This enables the
**programme filter** to span institutions and a cross-curriculum comparison (the
interim's §3.5 stretch goal). The canonical `curriculum.db` is never modified —
the MIT courses live in `data/raw/modules_mit_ocw/`, which the canonical ingest
does not scan.

```bash
make pipeline-multi   # build data/curriculum_multi.db (Imperial + MIT OCW, 101 modules)
make serve-multi      # serve it; the programme facet now offers an "MIT OpenCourseWare CS" cohort
```

---

## Starting the Web Application

### Option A — Development (hot-reload)

```bash
# Terminal 1: Backend API
source .venv/bin/activate
uvicorn curriculum_mapper.api.main:app --reload --host 127.0.0.1 --port 8000

# Terminal 2: Frontend dev server
cd frontend
npm run dev           # http://localhost:5173
```

Open **http://localhost:5173** in a browser.

### Option B — Production build

```bash
cd frontend
npm run build         # outputs to frontend/dist/

source ../.venv/bin/activate
uvicorn curriculum_mapper.api.main:app --host 127.0.0.1 --port 8000
```

Open **http://127.0.0.1:8000** — FastAPI serves `frontend/dist/` at `/`.

---

## API Reference

Interactive docs (Swagger UI): **http://127.0.0.1:8000/docs**

| Endpoint | Method | Description |
|---|---|---|
| `/health` | GET | System health + DB counts |
| `/api/v1/modules/` | GET | List modules (`?level=2&search=algorithm`) |
| `/api/v1/modules/{code}` | GET | Full module detail with ILOs |
| `/api/v1/modules/{code}/concepts` | GET | Extracted concepts for a module |
| `/api/v1/modules/{code}/alignments` | GET | KA alignments for a module |
| `/api/v1/modules/{code}/neighbors` | GET | Similar modules (by Jaccard) |
| `/api/v1/modules/{code}/plos` | GET | Programme-level outcomes a module fulfils |
| `/api/v1/modules/programmes` | GET | Degree programmes + module counts |
| `/api/v1/modules/programmes/{p}/outcomes` | GET | A programme's learning outcomes |
| `/api/v1/modules/plos/{id}/modules` | GET | Modules addressing a given outcome |
| `/api/v1/modules/plo-coverage` | GET | Modules fulfilling each outcome |
| `/api/v1/concepts/` | GET | List all concepts (`?ka=AL&search=sort`) |
| `/api/v1/concepts/{id}` | GET | A single concept (term, confidence, variants, modules) |
| `/api/v1/concepts/{id}/alignments` | GET | A concept's KA alignments |
| `/api/v1/alignments/` | GET | All alignments with filters |
| `/api/v1/alignments/stats` | GET | Counts by KA, method, validation status |
| `/api/v1/alignments/{id}/validate` | PATCH | Accept / reject / reassign an alignment |
| `/api/v1/graph/module-module` | GET | Cytoscape.js graph JSON (nodes + edges) |
| `/api/v1/graph/module-concept` | GET | Bipartite graph for one module |
| `/api/v1/graph/concept-acm` | GET | Concept → CS2023 hierarchy graph |
| `/api/v1/graph/concept-prerequisites` | GET | Directed concept-prerequisite DAG |
| `/api/v1/graph/concept-neighbourhood` | GET | A concept's prerequisite/subsequent neighbourhood |
| `/api/v1/graph/trace/module/{code}` | GET | A module's full prerequisite chain + dependents |
| `/api/v1/graph/trace/concept/{id}` | GET | A concept's full prerequisite chain |
| `/api/v1/graph/communities` | GET | Louvain community assignments |
| `/api/v1/graph/centrality` | GET | Degree, betweenness, eigenvector centrality |
| `/api/v1/reports/coverage` | GET | Per-KA coverage fractions |
| `/api/v1/reports/gaps` | GET | KAs below coverage threshold |
| `/api/v1/reports/redundancies` | GET | Concepts appearing in too many modules |
| `/api/v1/reports/summary` | GET | Full curriculum health summary |
| `/api/v1/reports/export` | GET | Complete JSON curriculum snapshot |

### Example requests

```bash
# 1. Check the system is up
curl http://127.0.0.1:8000/health
# → {"status":"ok","modules":69,"concepts":1885,"alignments":2450}   (canonical curriculum.db)

# 2. List all Year 2 modules
curl 'http://127.0.0.1:8000/api/v1/modules/?level=2'

# 3. Fetch alignments for IC50001, filtered by KA = Algorithms and only ambiguous
curl 'http://127.0.0.1:8000/api/v1/modules/IC50001/alignments?ka=AL&ambiguous_only=true'

# 4. Get the Cytoscape-formatted module-module graph
curl http://127.0.0.1:8000/api/v1/graph/module-module | jq '.nodes | length'
# → 69

# 5. Validate an alignment (accept) — writes to user_feedback audit table
curl -X PATCH 'http://127.0.0.1:8000/api/v1/alignments/42/validate' \
     -H 'Content-Type: application/json' \
     -d '{"action":"accept","comment":"verified by reviewer"}'

# 6. KA coverage report
curl http://127.0.0.1:8000/api/v1/reports/coverage | jq '.coverage'
```

---

## Deployment

### Docker (recommended for a single-command setup)

```bash
# Build the image and start the API + frontend on http://localhost:8000
docker compose up --build

# First boot runs the full pipeline inside the container; subsequent boots reuse the
# SQLite database via the ./data volume mount.
```

Override configuration at runtime via environment variables (see `.env.example` for the
full list — `API_HOST`, `API_PORT`, `CORS_ORIGINS`, `CURRICULUM_DB_PATH`).

### Manual (without Docker)

Follow the **Setup** and **Running the Pipeline** sections above, then run the production
build path described in **Starting the Web Application → Option B**.

---

## Running Tests

### Full test suite

```bash
source .venv/bin/activate
python -m pytest tests/ -q
# Expected: 463 passed in ~14 s
```

### With coverage report

```bash
python -m pytest --cov=curriculum_mapper --cov-report=html -q
# Opens htmlcov/index.html for line-level coverage details
# Current coverage: 82% (full suite)
```

### Unit tests only (fast, no DB required for most)

```bash
python -m pytest tests/unit/ -q
# ~395 tests, ~12 s
```

### Integration tests only (requires populated DB)

```bash
python -m pytest tests/integration/ -v
# 68 tests against real SQLite DB via ASGI transport
```

### By test module

```bash
python -m pytest tests/unit/test_aligners.py -v        # Alignment logic
python -m pytest tests/unit/test_metrics.py -v         # Evaluation metrics
python -m pytest tests/unit/test_graph.py -v           # Graph construction
python -m pytest tests/unit/test_benchmarks.py -v      # Benchmark runner
python -m pytest tests/unit/test_reports.py -v         # Report generation
python -m pytest tests/unit/test_canonicalizer.py -v   # Concept deduplication
python -m pytest tests/unit/test_keybert_extractor.py -v  # KeyBERT
```

### Code quality

```bash
python -m ruff check curriculum_mapper/ tests/     # Linting (all checks pass)
python -m black --check curriculum_mapper/ tests/  # Formatting check
```

---

## Test Coverage Summary (v1.0.0)

| Module | Coverage |
|---|---|
| `evaluation/metrics.py` | 100% |
| `evaluation/reports.py` | 90% |
| `evaluation/benchmarks.py` | 78%\* |
| `alignment/ambiguity.py` | 100% |
| `alignment/hybrid.py` | 100% |
| `alignment/aligner.py` | 100% |
| `graph/prerequisite.py`, `graph/tracer.py` | 100% |
| `graph/concept_prerequisite.py` | 94% |
| `nlp/canonicalizer.py` | 92% |
| `nlp/extractors/keybert_extractor.py` | 100% |
| `nlp/extractors/tfidf_extractor.py` | 100% |
| `ingestion/storage.py` | 82% |
| `api/schemas.py` | 100% |
| **TOTAL** | **82%** |

\*`benchmarks.py` includes CLI-only extended ablations (aligner weight sweep, per-extractor comparison) that are exercised end-to-end by `scripts/run_evaluation.py` rather than in unit tests.

---

## Project Structure

```
ai-curriculum-mapper/
├── curriculum_mapper/          # Main Python package
│   ├── config.py               # All thresholds and constants
│   ├── ingestion/              # Module loading, normalisation, SQLite storage
│   ├── nlp/                    # 5 extractors, embeddings, canonicalizer, pipeline
│   ├── alignment/              # Lexical, semantic, hybrid aligners + ambiguity detection
│   ├── graph/                  # NetworkX graph builder, analytics, gap detector
│   ├── evaluation/             # Metrics, benchmark runner, report generation
│   └── api/                    # FastAPI app, routers, schemas
├── frontend/                   # Vite + vanilla JS (multi-page, hash-routed)
│   ├── index.html
│   └── src/
│       ├── main.js             # bootstrap + routing + health badge
│       ├── router.js, state.js # hash router + shared data cache
│       ├── api.js              # thin fetch wrapper
│       ├── pages/              # Overview, Map, Explore, Coverage, Review
│       ├── components/         # GraphView, ModulePanel, AlignmentTable, GapReport, ValidationWidget, Toast
│       ├── util/               # shared helpers (concept cleanup)
│       └── styles/main.css
├── scripts/                    # Pipeline entry points
│   ├── fetch_imperial_modules.py  # live descriptor fetch + provenance (re-runnable)
│   ├── create_imperial_modules.py # curated module data (offline fallback)
│   ├── fetch_mit_ocw.py           # MIT OCW courses + build curriculum_multi.db
│   ├── ingest_modules.py
│   ├── run_nlp_pipeline.py
│   ├── run_alignment.py
│   ├── build_graph.py             # 4 graphs incl. concept-prerequisite DAG
│   ├── run_plo_alignment.py       # map modules → programme-level outcomes
│   └── run_evaluation.py
├── tests/
│   ├── unit/                   # 395 unit tests (fast, mock-based)
│   └── integration/            # 68 integration tests (real DB, ASGI transport)
├── data/
│   ├── raw/modules/            # Imperial College JSON module descriptors
│   ├── raw/standards/          # cs2023_ka.json (18 KAs, 974 topic strings)
│   ├── annotations/            # Gold-annotated concepts (5 modules, 77 concepts)
│   ├── cache/                  # Embedding cache (.npy) + graph pickles (.pkl)
│   └── processed/              # Evaluation outputs + figures
└── requirements.txt
```

---

## Key Configuration (`curriculum_mapper/config.py`)

| Parameter | Value | Effect |
|---|---|---|
| `SBERT_MODEL` | `all-MiniLM-L6-v2` | 384-dim, 80 MB, 6× faster than mpnet |
| `SIMILARITY_THRESHOLD` | 0.35 | Minimum hybrid score to store an alignment |
| `SBERT_MATCH_THRESHOLD` | 0.75 | Partial credit threshold for evaluation |
| `LEXICAL_WEIGHT` | 0.35 | Weight of lexical score in hybrid aligner |
| `SEMANTIC_WEIGHT` | 0.65 | Weight of SBERT score in hybrid aligner |
| `SHARED_CONCEPT_EDGE_MIN` | 3 | Minimum shared concepts for a module-module edge |
| `AMBIGUITY_MARGIN` | 0.08 | Score gap below which top-2 alignments are ambiguous |
| `GAP_COVERAGE_THRESHOLD` | 0.10 | KAs below 10% module coverage are flagged |
| `REDUNDANCY_THRESHOLD` | 5 | Concepts in >5 modules flagged as redundant |
| `CONCEPT_PREREQ_RELATEDNESS_FLOOR` | 0.55 | Min relatedness to keep a concept→concept prerequisite |
| `CONCEPT_PREREQ_TOP_K` | 3 | Max prerequisites kept per dependent concept |

---

## Reproducibility

All random seeds are fixed:
- BERTopic UMAP: `random_state=42`
- Louvain community detection: `random_state=42`
- HDBSCAN: deterministic with fixed UMAP seed

The embedding cache (`data/cache/embeddings/`) uses SHA-256 content keys, so repeated runs with the same text produce identical results without re-encoding.

The full pipeline is reproducible from a clean clone:
```bash
make setup && make pipeline && make evaluate && make test
```

---

## Citing this work

If you use this software in research or teaching, please cite it via the
[`CITATION.cff`](CITATION.cff) file in this repository (GitHub renders a one-click
"Cite this repository" widget on the repo home page), or use the BibTeX entry below:

```bibtex
@thesis{jiang2026curriculum,
  title  = {AI-Driven Curriculum Mapping for Computing Education},
  author = {Jiang, Alan},
  school = {Imperial College London, Department of Computing},
  year   = {2026},
  month  = {5},
  type   = {BEng dissertation},
  url    = {https://github.com/alanj5/ai-curriculum-mapper}
}
```

---

## License

Released under the [MIT License](LICENSE). See `LICENSE` for the full text.
