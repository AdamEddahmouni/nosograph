"""
Shared test fixtures for the Lupus Research Platform test suite.
"""

import json
import logging
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
os.environ.setdefault("DEBUG", "true")

PROJECT_ROOT = Path(__file__).parent.parent
DR_DATA_DIR = PROJECT_ROOT / "src" / "med_research" / "pipeline" / "drug_repurposing" / "data"


@pytest.hookimpl(hookwrapper=True)
def pytest_runtest_makereport(item, call):
    """Expose phase reports to fixtures that need failure diagnostics."""
    outcome = yield
    report = outcome.get_result()
    setattr(item, f"rep_{report.when}", report)


def pytest_collection_modifyitems(items):
    """Auto-classify tests: every test that is not marked slow or integration
    is a unit test. This keeps `make test-unit` / `make test-integration`
    working without hand-tagging every test file.
    """
    for item in items:
        markers = {m.name for m in item.iter_markers()}
        if "slow" in markers or "integration" in markers:
            continue
        if "unit" not in markers:
            item.add_marker(pytest.mark.unit)


@pytest.fixture(autouse=True)
def _capture_pipeline_logging(caplog):
    """Pipeline CLI formatters log to the root logger; make output visible in caplog."""
    caplog.set_level(logging.INFO)
    yield


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
