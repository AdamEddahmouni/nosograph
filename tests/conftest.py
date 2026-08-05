"""
Shared test fixtures for the Lupus Research Platform test suite.
"""

import json
import os
from pathlib import Path

import pytest

from med_research.pipeline.knowledge_graph.config import load_genes

# Disable the in-memory API rate limiter during tests. The web API suite
# issues 100+ requests per session and would otherwise be throttled with
# 429 responses mid-run. This runs before any test module (including
# test_web_api.py, which imports med_research.web.main) is loaded, so the
# middleware picks it up at module import time.
os.environ["RATE_LIMIT_REQUESTS"] = "0"

PROJECT_ROOT = Path(__file__).parent.parent
DR_DATA_DIR = PROJECT_ROOT / "src" / "med_research" / "pipeline" / "drug_repurposing" / "data"


@pytest.fixture(scope="session")
def kg_data_dir():
    from med_research.pipeline.knowledge_graph.config import _resolve
    return _resolve("sle")


@pytest.fixture(scope="session")
def dr_data_dir():
    return DR_DATA_DIR


@pytest.fixture(scope="session")
def sample_graph():
    """Build a fresh knowledge graph for testing."""
    from med_research.pipeline.knowledge_graph.builder import build_graph
    return build_graph()


@pytest.fixture(scope="session")
def sample_genes():
    """Load gene data indexed by gene ID."""
    data = load_genes()
    return {g["id"]: g for g in data["genes"]}


@pytest.fixture(scope="session")
def sample_candidates():
    """Load repurposing candidates."""
    data = json.loads((DR_DATA_DIR / "candidates.json").read_text(encoding="utf-8"))
    return data["repurposing_candidates"]
