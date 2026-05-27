.PHONY: setup install-nlp pipeline evaluate serve test lint format check

setup:
	python3 -m venv .venv
	.venv/bin/pip install --upgrade pip
	.venv/bin/pip install -r requirements.txt
	.venv/bin/pip install -r requirements-dev.txt
	.venv/bin/pip install -e .
	.venv/bin/python -m spacy download en_core_web_sm
	.venv/bin/python -c "import nltk; nltk.download(['stopwords','wordnet','punkt','averaged_perceptron_tagger','punkt_tab'])"

pipeline:
	.venv/bin/python scripts/download_mit_ocw.py
	.venv/bin/python scripts/ingest_modules.py
	.venv/bin/python scripts/run_nlp_pipeline.py

evaluate:
	.venv/bin/python scripts/run_evaluation.py

serve:
	.venv/bin/uvicorn curriculum_mapper.api.main:app --reload --host 127.0.0.1 --port 8000

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
