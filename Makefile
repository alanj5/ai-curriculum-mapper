.PHONY: setup install-nlp pipeline pipeline-llm evaluate serve serve-llm test lint format check

setup:
	python3 -m venv .venv
	.venv/bin/pip install --upgrade pip
	.venv/bin/pip install -r requirements.txt
	.venv/bin/pip install -r requirements-dev.txt
	.venv/bin/pip install -e .
	.venv/bin/python -m spacy download en_core_web_sm
	.venv/bin/python -c "import nltk; nltk.download(['stopwords','wordnet','punkt','averaged_perceptron_tagger','punkt_tab'])"

pipeline:
	.venv/bin/python scripts/ingest_modules.py
	.venv/bin/python scripts/run_nlp_pipeline.py --week2
	.venv/bin/python scripts/run_alignment.py
	.venv/bin/python scripts/build_graph.py

evaluate:
	.venv/bin/python scripts/run_evaluation.py

serve:
	.venv/bin/uvicorn curriculum_mapper.api.main:app --reload --host 127.0.0.1 --port 8000

# Build the LLM-augmented pipeline into a separate DB (canonical DB untouched).
pipeline-llm:
	CURRICULUM_DB_PATH=data/curriculum_llm.db LLM_EXTRACTOR_ENABLED=1 .venv/bin/python scripts/ingest_modules.py
	CURRICULUM_DB_PATH=data/curriculum_llm.db LLM_EXTRACTOR_ENABLED=1 .venv/bin/python scripts/run_nlp_pipeline.py --week2 --llm
	CURRICULUM_DB_PATH=data/curriculum_llm.db .venv/bin/python scripts/run_alignment.py
	CURRICULUM_DB_PATH=data/curriculum_llm.db .venv/bin/python scripts/build_graph.py

# Demo: serve the LLM-augmented data. Caches are DB-namespaced,
# so this does not affect the canonical `make serve`.
serve-llm:
	CURRICULUM_DB_PATH=data/curriculum_llm.db .venv/bin/uvicorn curriculum_mapper.api.main:app --host 127.0.0.1 --port 8000

# Build the combined Imperial + MIT OpenCourseWare corpus (curriculum_multi.db)
# for the cross-programme filter/comparison. Canonical curriculum.db untouched.
pipeline-multi:
	.venv/bin/python scripts/fetch_mit_ocw.py --build --scrape

# Demo: serve the combined corpus so the programme facet spans Imperial + MIT OCW.
serve-multi:
	CURRICULUM_DB_PATH=data/curriculum_multi.db .venv/bin/uvicorn curriculum_mapper.api.main:app --host 127.0.0.1 --port 8000

test:
	.venv/bin/pytest --cov=curriculum_mapper --cov-report=html --cov-report=term-missing -v

test-unit:
	.venv/bin/pytest tests/unit/ -v

test-integration:
	.venv/bin/pytest tests/integration/ -v

lint:
	.venv/bin/ruff check curriculum_mapper/ scripts/ tests/

format:
	.venv/bin/black curriculum_mapper/ scripts/ tests/

check: lint
	.venv/bin/mypy curriculum_mapper/ --ignore-missing-imports
