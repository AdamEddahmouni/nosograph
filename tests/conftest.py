"""
Shared test fixtures for the Lupus Research Platform test suite.
"""

import json
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).parent.parent
DR_DATA_DIR = PROJECT_ROOT / "drug_repurposing" / "data"

from knowledge_graph.config import load_genes


@pytest.fixture(scope="session")
def kg_data_dir():
    from knowledge_graph.config import DATA_ROOT
    return DATA_ROOT / "sle"


@pytest.fixture(scope="session")
def dr_data_dir():
    return DR_DATA_DIR


@pytest.fixture(scope="session")
def sample_graph():
    """Build a fresh knowledge graph for testing."""
    from knowledge_graph.build_graph import build_graph
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
