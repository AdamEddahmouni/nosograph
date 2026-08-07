"""FastAPI application entry point for the Medical Research Platform API."""

import logging
import sys
from contextlib import asynccontextmanager
from pathlib import Path

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

# Ensure project root is importable
sys.path.insert(0, str(Path(__file__).parent.parent))

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from med_research.logging_config import setup_logging
from med_research.web.config import (
    API_DESCRIPTION,
    API_TAGS,
    API_TITLE,
    API_VERSION,
    CORS_ORIGINS,
    DEBUG,
    HOST,
    PORT,
)
from med_research.web.middleware import AuthMiddleware, RateLimitMiddleware
from med_research.web.routers import routers
from med_research.web.routers.jobs import router as jobs_router

REPO_ROOT = Path(__file__).parent.parent.parent.parent
PIPELINE_DIR = Path(__file__).parent.parent / "pipeline"
logger = logging.getLogger(__name__)


# ── Lifespan (startup / shutdown) ─────────────────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Pre-load the knowledge graph on startup for faster first request."""
    setup_logging(level=logging.DEBUG if DEBUG else logging.INFO)
    import os

    if not DEBUG and not os.environ.get("API_KEY"):
        logger.warning(
            "API_KEY is not set while DEBUG=false. "
            "Protected write endpoints are open; set API_KEY in production deployments."
        )
    logger.info("Pre-loading knowledge graph...")
    from med_research.web.dependencies import get_knowledge_graph

    G = get_knowledge_graph()
    logger.info(
        "Knowledge graph loaded: %s nodes, %s edges",
        G.number_of_nodes(),
        G.number_of_edges(),
    )

    yield

    # Shutdown: nothing to clean up currently
    logger.info("Shutting down...")


# ── App Creation ────────────────────────────────────────────────────────────

app = FastAPI(
    title=API_TITLE,
    version=API_VERSION,
    description=API_DESCRIPTION,
    openapi_tags=API_TAGS,
    lifespan=lifespan,
    docs_url="/api/docs",
    redoc_url="/api/redoc",
    openapi_url="/api/openapi.json",
)

# ── CORS ────────────────────────────────────────────────────────────────────

app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Auth & Rate Limiting ─────────────────────────────────────────────────────

app.add_middleware(AuthMiddleware)
app.add_middleware(RateLimitMiddleware)

# ── Register Routers ────────────────────────────────────────────────────────

for router in routers:
    app.include_router(router)

app.include_router(jobs_router)

# ── Static Files ──────────────────────────────────────────────────────────

# Module HTML reports from v2 pipeline data directories
static_dirs = {
    "/static/kg": PIPELINE_DIR / "knowledge_graph" / "data",
    "/static/drug_repurposing": PIPELINE_DIR / "drug_repurposing" / "data",
    "/static/bioinformatics": PIPELINE_DIR / "bioinformatics" / "data",
    "/static/literature_mining": PIPELINE_DIR / "literature_mining" / "data",
    "/static/virtual_screening": PIPELINE_DIR / "virtual_screening" / "data",
    "/static/clinical_trials": PIPELINE_DIR / "clinical_trials" / "data",
    "/static/ml_predictor": PIPELINE_DIR / "ml_predictor" / "data",
    "/static/drug_synergy": PIPELINE_DIR / "drug_synergy" / "data",
    "/static/adverse_events": PIPELINE_DIR / "adverse_events" / "data",
    "/static/gene_expression": PIPELINE_DIR / "gene_expression" / "data",
    "/static/car_t_predictor": PIPELINE_DIR / "car_t_predictor" / "data",
    "/static/biomarker_discovery": PIPELINE_DIR / "biomarker_discovery" / "data",
    "/static/evidence": PIPELINE_DIR / "evidence" / "data",
    "/static/semantic_search": PIPELINE_DIR / "semantic_search" / "data",
    "/static/network_pharmacology": PIPELINE_DIR / "network_pharmacology" / "data",
}

for path_prefix, directory in static_dirs.items():
    if directory.exists():
        name = f"static_{path_prefix.replace('/', '_')}"
        app.mount(path_prefix, StaticFiles(directory=str(directory), html=True), name=name)

# Live dashboard (mounted last so it catches root "/")
static_dir = Path(__file__).parent / "static"
if static_dir.exists():
    app.mount("/", StaticFiles(directory=str(static_dir), html=True), name="static_root")


# ── Main ────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "med_research.web.main:app",
        host=HOST,
        port=PORT,
        reload=DEBUG,
        log_level="info",
    )
