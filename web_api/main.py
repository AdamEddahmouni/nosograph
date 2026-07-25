"""FastAPI application entry point for the Lupus Research Platform API."""

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

from web_api.config import (
    API_DESCRIPTION,
    API_TAGS,
    API_TITLE,
    API_VERSION,
    CORS_ORIGINS,
    DEBUG,
    HOST,
    PORT,
)
from web_api.routers import routers
from web_api.routers.jobs import router as jobs_router

PROJECT_ROOT = Path(__file__).parent.parent


# ── Lifespan (startup / shutdown) ─────────────────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Pre-load the knowledge graph on startup for faster first request."""
    print("🔄 Pre-loading knowledge graph...")
    from web_api.dependencies import get_knowledge_graph

    G = get_knowledge_graph()
    print(f"✅ Knowledge graph loaded: {G.number_of_nodes()} nodes, {G.number_of_edges()} edges")

    yield

    # Shutdown: nothing to clean up currently
    print("🔄 Shutting down...")


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

# ── Register Routers ────────────────────────────────────────────────────────

for router in routers:
    app.include_router(router)

app.include_router(jobs_router)

# ── Static Files ──────────────────────────────────────────────────────────

# Existing module HTML reports (mounted under their original paths)
static_dirs = {
    "/knowledge_graph/web": PROJECT_ROOT / "knowledge_graph" / "web",
    "/drug_repurposing": PROJECT_ROOT / "drug_repurposing",
    "/bioinformatics": PROJECT_ROOT / "bioinformatics",
    "/literature_mining": PROJECT_ROOT / "literature_mining",
    "/virtual_screening": PROJECT_ROOT / "virtual_screening",
    "/clinical_trials": PROJECT_ROOT / "clinical_trials",
    "/ml_predictor": PROJECT_ROOT / "ml_predictor",
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
        "web_api.main:app",
        host=HOST,
        port=PORT,
        reload=DEBUG,
        log_level="info",
    )
