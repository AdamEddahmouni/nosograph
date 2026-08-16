"""Web API configuration — loaded from environment with sensible defaults."""

import os
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent
REPO_ROOT = Path(__file__).resolve().parent.parent.parent.parent

# ── Server ────────────────────────────────────────────────────────────────
HOST = os.environ.get("HOST", "0.0.0.0")
PORT = int(os.environ.get("PORT", "8000"))
DEBUG = os.environ.get("DEBUG", "false").lower() == "true"
OPENAPI_ENABLED = (
    os.environ.get(
        "OPENAPI_ENABLED",
        "true" if DEBUG else "false",
    ).lower()
    == "true"
)

# ── Researcher authentication ─────────────────────────────────────────────
# ``local`` uses signed HttpOnly sessions issued by /api/auth/login. ``proxy``
# accepts a principal header only from an address listed in AUTH_TRUSTED_PROXY_IPS.
AUTH_MODE = os.environ.get("AUTH_MODE", "local").lower()
AUTH_SESSION_SECRET = os.environ.get("AUTH_SESSION_SECRET", "")
AUTH_TRUSTED_PROXY_IPS = os.environ.get("AUTH_TRUSTED_PROXY_IPS", "")

# ── API Metadata ──────────────────────────────────────────────────────────
API_TITLE = "Medical Research Platform API"
API_VERSION = "2.0.0"
API_DESCRIPTION = (
    "REST API for the Medical Research & Drug Discovery Platform. "
    "Provides programmatic access to knowledge graph queries, drug repurposing "
    "scoring, bioinformatics analyses, literature mining, virtual screening, "
    "clinical trial tracking, and ML-driven target prediction across multiple diseases."
)

# Top-level OpenAPI tags — required for FastAPI to emit the "tags" array
# in the OpenAPI schema. APIRouter(tags=[...]) only tags individual routes;
# the FastAPI constructor's openapi_tags parameter creates the schema metadata.
API_TAGS = [
    {"name": "Authentication", "description": "Server-derived researcher login and session state."},
    {"name": "System", "description": "Health checks and platform-wide statistics."},
    {
        "name": "Knowledge Graph",
        "description": (
            "Explore disease knowledge graphs — nodes, edges, paths, neighbors, and search."
        ),
    },
    {
        "name": "Drug Repurposing",
        "description": (
            "Ranked drug repurposing candidates by composite score, filterable by gene."
        ),
    },
    {
        "name": "Bioinformatics",
        "description": (
            "GWAS catalog annotation, pathway enrichment (GO/KEGG/Reactome), "
            "and PPI network analysis."
        ),
    },
    {
        "name": "Analysis",
        "description": (
            "Literature mining (PubMed + NER), virtual drug screening, "
            "clinical trial tracking, and ML target prediction."
        ),
    },
    {
        "name": "Synergy",
        "description": (
            "Predict synergistic drug combinations from the 26-drug library "
            "using a 5-dimensional weighted scoring model."
        ),
    },
    {
        "name": "Safety",
        "description": (
            "Adverse event profiling and disease-aware safety scoring "
            "across 4 dimensions for knowledge graph drugs."
        ),
    },
    {
        "name": "Expression",
        "description": (
            "Gene expression correlation — Connectivity Map approach scoring "
            "drug mechanisms against curated disease transcriptomic signatures."
        ),
    },
    {
        "name": "CAR-T",
        "description": (
            "CAR-T Response Predictor — gene-level CD19 CAR-T therapy "
            "suitability scoring for disease-associated genes."
        ),
    },
    {
        "name": "Biomarker",
        "description": (
            "Biomarker Discovery — cross-module integration correlating gene "
            "signatures across all 5 scoring platforms for therapy selection."
        ),
    },
    {
        "name": "Semantic Search",
        "description": (
            "Embedding-based semantic literature search using sentence-transformers "
            "and ChromaDB to find PubMed articles by meaning, not keywords."
        ),
    },
    {
        "name": "Evidence Gathering",
        "description": (
            "Multi-source biomedical evidence aggregation — search PubMed, "
            "preprints (bioRxiv/medRxiv), ClinicalTrials.gov, FDA labels "
            "(DailyMed), and patents simultaneously."
        ),
    },
    {
        "name": "LLM Extraction",
        "description": (
            "LLM-powered structured data extraction from biomedical abstracts. "
            "Extracts evidence levels, model systems, key findings, drug mentions, "
            "sample sizes, and confidence scores using GPT-4o-mini or compatible models."
        ),
    },
    {
        "name": "Monitor",
        "description": (
            "Continuous evidence monitoring — take timestamped snapshots, compare "
            "over time, and receive alerts for new publications, clinical trial "
            "updates, and trackable changes across all platform entities."
        ),
    },
    {
        "name": "Cross-Disease Analysis",
        "description": (
            "Cross-disease shared biology, similarity, and multi-disease "
            "drug scoring across curated disease modules."
        ),
    },
    {
        "name": "Jobs",
        "description": (
            "Submit and track async analysis jobs with real-time WebSocket progress streaming."
        ),
    },
    {
        "name": "Universal Biomedical",
        "description": (
            "Versioned condition search, hierarchy, claims, and snapshot provenance "
            "from the canonical biomedical store."
        ),
    },
    {
        "name": "Biomedical Analytics",
        "description": (
            "Graph analytics, shortest path discovery, and target vulnerability "
            "prioritization from the canonical biomedical store."
        ),
    },
]

# ── Celery / Redis ────────────────────────────────────────────────────────
CELERY_BROKER_URL = os.environ.get("CELERY_BROKER_URL", "redis://localhost:6379/0")
CELERY_RESULT_BACKEND = os.environ.get("CELERY_RESULT_BACKEND", "redis://localhost:6379/0")

# ── CORS ──────────────────────────────────────────────────────────────────
CORS_ORIGINS = os.environ.get("CORS_ORIGINS", "http://localhost:3000").split(",")

# ── Dashboard security ────────────────────────────────────────────────────
# The dashboard has no inline event handlers or scripts. Opt into an enforcing
# or report-only policy at the reverse-proxy boundary without changing the UI.
# ``DASHBOARD_CSP=true`` is retained as a concise opt-in for local deployments;
# ``DASHBOARD_CSP_MODE`` also accepts ``off``, ``report-only``, or ``enforce``.
DASHBOARD_CSP_MODE = os.environ.get(
    "DASHBOARD_CSP_MODE",
    "enforce" if os.environ.get("DASHBOARD_CSP", "false").lower() == "true" else "off",
).lower()
DASHBOARD_CSP_POLICY = (
    "default-src 'self'; "
    "base-uri 'self'; "
    "object-src 'none'; "
    "frame-ancestors 'self'; "
    "form-action 'self'; "
    "script-src 'self'; "
    "script-src-attr 'none'; "
    "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; "
    "font-src 'self' https://fonts.gstatic.com; "
    "img-src 'self' data: blob:; "
    "connect-src 'self' ws: wss:"
)

# ── Cache ─────────────────────────────────────────────────────────────────
USE_CACHE = os.environ.get("USE_CACHE", "true").lower() == "true"

# ── Workspace run history ──────────────────────────────────────────────────
WORKSPACE_DB_PATH = Path(
    os.environ.get("WORKSPACE_DB_PATH", str(REPO_ROOT / "data" / "evidence_workspace.sqlite3"))
)

# ── Biomedical canonical store ─────────────────────────────────────────────
BIOMEDICAL_DB_PATH = Path(
    os.environ.get("BIOMEDICAL_DB_PATH", str(REPO_ROOT / "data" / "biomedical.sqlite3"))
)

# ── Module Data Paths ─────────────────────────────────────────────────────
PIPELINE_DIR = PROJECT_ROOT / "pipeline"
DR_DATA_DIR = PIPELINE_DIR / "drug_repurposing" / "data"
BIO_DATA_DIR = PIPELINE_DIR / "bioinformatics" / "data"
LIT_DATA_DIR = PIPELINE_DIR / "literature_mining" / "data"
VS_DATA_DIR = PIPELINE_DIR / "virtual_screening" / "data"
CT_DATA_DIR = PIPELINE_DIR / "clinical_trials" / "data"
ML_DATA_DIR = PIPELINE_DIR / "ml_predictor" / "data"
