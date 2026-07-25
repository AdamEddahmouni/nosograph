"""Web API configuration — loaded from environment with sensible defaults."""

import os
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent

# ── Server ────────────────────────────────────────────────────────────────
HOST = os.environ.get("HOST", "0.0.0.0")
PORT = int(os.environ.get("PORT", "8000"))
DEBUG = os.environ.get("DEBUG", "false").lower() == "true"

# ── API Metadata ──────────────────────────────────────────────────────────
API_TITLE = "Lupus Research Platform API"
API_VERSION = "1.0.0"
API_DESCRIPTION = (
    "REST API for the Lupus Research & Drug Discovery Platform. "
    "Provides programmatic access to knowledge graph queries, drug repurposing "
    "scoring, bioinformatics analyses, literature mining, virtual screening, "
    "clinical trial tracking, and ML-driven target prediction."
)

# Top-level OpenAPI tags — required for FastAPI to emit the "tags" array
# in the OpenAPI schema. APIRouter(tags=[...]) only tags individual routes;
# the FastAPI constructor's openapi_tags parameter creates the schema metadata.
API_TAGS = [
    {"name": "System",
     "description": "Health checks and platform-wide statistics."},
    {"name": "Knowledge Graph",
     "description": (
         "Explore the SLE knowledge graph — nodes, edges, paths, neighbors, "
         "and search."
     )},
    {"name": "Drug Repurposing",
     "description": (
         "Ranked drug repurposing candidates by composite score, filterable "
         "by gene."
     )},
    {"name": "Bioinformatics",
     "description": (
         "GWAS catalog annotation, pathway enrichment (GO/KEGG/Reactome), "
         "and PPI network analysis."
     )},
    {"name": "Analysis",
     "description": (
         "Literature mining (PubMed + NER), virtual drug screening, "
         "clinical trial tracking, and ML target prediction."
     )},
    {"name": "Synergy",
     "description": (
         "Predict synergistic drug combinations from the 26-drug library "
         "using a 5-dimensional weighted scoring model."
     )},
    {"name": "Safety",
     "description": (
         "Adverse event profiling and lupus-specific safety scoring "
         "across 4 dimensions for all 26 knowledge graph drugs."
     )},
    {"name": "Expression",
     "description": (
         "Gene expression correlation — Connectivity Map approach scoring "
         "drug mechanisms against curated SLE transcriptomic signatures."
     )},
    {"name": "CAR-T",
     "description": (
         "CAR-T Response Predictor — gene-level CD19 CAR-T therapy "
         "suitability scoring for all 35 lupus-associated genes."
     )},
    {"name": "Biomarker",
     "description": (
         "Biomarker Discovery — cross-module integration correlating gene "
         "signatures across all 5 scoring platforms for therapy selection."
     )},
    {"name": "Semantic Search",
     "description": (
         "Embedding-based semantic literature search using sentence-transformers "
         "and ChromaDB to find PubMed articles by meaning, not keywords."
     )},
    {"name": "Evidence Gathering",
     "description": (
         "Multi-source biomedical evidence aggregation — search PubMed, "
         "preprints (bioRxiv/medRxiv), ClinicalTrials.gov, FDA labels "
         "(DailyMed), and patents simultaneously."
     )},
    {"name": "LLM Extraction",
     "description": (
         "LLM-powered structured data extraction from biomedical abstracts. "
         "Extracts evidence levels, model systems, key findings, drug mentions, "
         "sample sizes, and confidence scores using GPT-4o-mini or compatible models."
     )},
    {"name": "Jobs",
     "description": (
         "Submit and track async analysis jobs with real-time WebSocket "
         "progress streaming."
     )},
]

# ── Celery / Redis ────────────────────────────────────────────────────────
CELERY_BROKER_URL = os.environ.get("CELERY_BROKER_URL", "redis://localhost:6379/0")
CELERY_RESULT_BACKEND = os.environ.get("CELERY_RESULT_BACKEND", "redis://localhost:6379/0")

# ── CORS ──────────────────────────────────────────────────────────────────
CORS_ORIGINS = os.environ.get("CORS_ORIGINS", "*").split(",")

# ── Cache ─────────────────────────────────────────────────────────────────
USE_CACHE = os.environ.get("USE_CACHE", "true").lower() == "true"

# ── Module Data Paths ─────────────────────────────────────────────────────
KG_DATA_DIR = PROJECT_ROOT / "knowledge_graph" / "data"
DR_DATA_DIR = PROJECT_ROOT / "drug_repurposing" / "data"
BIO_DATA_DIR = PROJECT_ROOT / "bioinformatics" / "data"
LIT_DATA_DIR = PROJECT_ROOT / "literature_mining" / "data"
VS_DATA_DIR = PROJECT_ROOT / "virtual_screening" / "data"
CT_DATA_DIR = PROJECT_ROOT / "clinical_trials" / "data"
ML_DATA_DIR = PROJECT_ROOT / "ml_predictor" / "data"
