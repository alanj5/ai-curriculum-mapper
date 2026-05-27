"""FastAPI application entry point.

Start the server:
    uvicorn curriculum_mapper.api.main:app --reload --host 127.0.0.1 --port 8000

API docs (Swagger UI): http://127.0.0.1:8000/docs
"""

from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from curriculum_mapper.api.routers import (
    alignments,
    concepts,
    graph,
    modules,
    reports,
)
from curriculum_mapper.config import BASE_DIR, CORS_ORIGINS

FRONTEND_DIR = BASE_DIR / "frontend"


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Pre-warm caches on startup so first request is fast
    from curriculum_mapper.api.dependencies import get_ka_data, get_storage
    get_storage()
    get_ka_data()
    yield


app = FastAPI(
    title="AI Curriculum Mapper",
    description=(
        "API for mapping Imperial College Computing modules to ACM/IEEE CS2023 "
        "Knowledge Areas via NLP-based concept extraction and hybrid alignment."
    ),
    version="2.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# API routers
app.include_router(modules.router,    prefix="/api/v1/modules",    tags=["modules"])
app.include_router(concepts.router,   prefix="/api/v1/concepts",   tags=["concepts"])
app.include_router(alignments.router, prefix="/api/v1/alignments", tags=["alignments"])
app.include_router(graph.router,      prefix="/api/v1/graph",      tags=["graph"])
app.include_router(reports.router,    prefix="/api/v1/reports",    tags=["reports"])


@app.get("/health")
def health() -> dict:
    """Health check endpoint."""
    from curriculum_mapper.api.dependencies import get_storage
    storage = get_storage()
    return {
        "status": "ok",
        "modules": storage.count_modules(),
        "concepts": storage.count_concepts(),
        "alignments": storage.count_alignments(),
    }


# Serve frontend static files if built (production mode)
_frontend_dist = FRONTEND_DIR / "dist"
if _frontend_dist.exists():
    app.mount("/", StaticFiles(directory=str(_frontend_dist), html=True), name="frontend")
