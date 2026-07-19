"""
Shared test fixtures for the Lupus Research Platform test suite.
"""

import pytest
import json
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent
KG_DATA_DIR = PROJECT_ROOT / "knowledge_graph" / "data"
DR_DATA_DIR = PROJECT_ROOT / "drug_repurposing" / "data"


@pytest.fixture(scope="session")
def kg_data_dir():
    return KG_DATA_DIR


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
    data = json.loads((KG_DATA_DIR / "genes.json").read_text(encoding="utf-8"))
    return {g["id"]: g for g in data["genes"]}


@pytest.fixture(scope="session")
def sample_candidates():
    """Load repurposing candidates."""
    data = json.loads((DR_DATA_DIR / "candidates.json").read_text(encoding="utf-8"))
    return data["repurposing_candidates"]
