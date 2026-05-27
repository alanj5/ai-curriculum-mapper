# Multi-stage build: builds the frontend, then bundles it with the Python API.

# ---- Stage 1: build frontend ----
FROM node:20-alpine AS frontend-build

WORKDIR /app/frontend
COPY frontend/package.json frontend/package-lock.json* ./
RUN npm install --no-audit --no-fund
COPY frontend/ ./
RUN npm run build


# ---- Stage 2: Python runtime ----
FROM python:3.11-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

# System packages required by spaCy / NLTK builds
RUN apt-get update && apt-get install -y --no-install-recommends \
        build-essential \
    && rm -rf /var/lib/apt/lists/*

# Python dependencies first (cache-friendly)
COPY requirements.txt requirements-dev.txt ./
RUN pip install -r requirements.txt

# Application source
COPY curriculum_mapper/ ./curriculum_mapper/
COPY scripts/ ./scripts/
COPY data/raw/ ./data/raw/
COPY data/annotations/ ./data/annotations/
COPY pyproject.toml README.md ./
RUN pip install -e .

# Pre-download spaCy + NLTK models so the container can run offline
RUN python -m spacy download en_core_web_sm \
 && python -c "import nltk; nltk.download(['stopwords','wordnet','punkt','averaged_perceptron_tagger','punkt_tab'])"

# Built frontend from stage 1
COPY --from=frontend-build /app/frontend/dist ./frontend/dist

EXPOSE 8000

# Default command serves the API + built frontend at /
CMD ["uvicorn", "curriculum_mapper.api.main:app", "--host", "0.0.0.0", "--port", "8000"]
