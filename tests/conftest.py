"""
Shared test fixtures for the Lupus Research Platform test suite.
"""

import json
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).parent.parent
DR_DATA_DIR = PROJECT_ROOT / "src" / "med_research" / "pipeline" / "drug_repurposing" / "data"

from med_research.pipeline.knowledge_graph.config import load_genes


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
