"""
Shared test fixtures for the Lupus Research Platform test suite.
"""

import json
import logging
import os
from pathlib import Path

import pytest

from med_research.pipeline.knowledge_graph.config import load_genes

pytest_plugins = ["tests.evidence_http_fixtures", "tests.integration.http_fixtures"]

# Disable the in-memory API rate limiter during tests. The web API suite
# issues 100+ requests per session and would otherwise be throttled with
# 429 responses mid-run. This runs before any test module (including
# test_web_api.py, which imports med_research.web.main) is loaded, so the
# middleware picks it up at module import time.
os.environ["RATE_LIMIT_REQUESTS"] = "0"
os.environ["DEBUG"] = "true"
os.environ["OPENAPI_ENABLED"] = "true"

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


@pytest.fixture(scope="session")
def comparative_modules():
    """Cross-disease comparative module stack, computed once per process.

    ``compute_comparative_modules`` runs biomarker/expression/synergy for all
    seven diseases (~7.5s). Sharing it as a session fixture means the demoted
    score test and the two HTTP modules-endpoint tests each get the result
    from a single real engine run instead of recomputing it per call site.
    """
    from med_research.pipeline.cross_disease.analyzer import compute_comparative_modules

    return compute_comparative_modules()


class _FakeEmbedder:
    """SentenceTransformer stand-in returning zero vectors.

    Semantic-search empty paths (no indexed collection) return before any
    text is embedded, so the real all-MiniLM-L6-v2 model is never used there.
    Loading it costs ~2s per engine instance; sharing this stand-in avoids
    paying that load in tests that only exercise the empty path.
    """

    def encode(self, texts):
        if isinstance(texts, str):
            texts = [texts]
        return [[0.0] * 384 for _ in texts]


@pytest.fixture(scope="session")
def semantic_fake_embedder():
    """Shared embedder for semantic-search tests that exercise empty paths."""
    return _FakeEmbedder()


@pytest.fixture(scope="session")
def gwas_result():
    """GWAS engine result, computed once per process.

    ``run_gwas_analysis`` performs live GWAS Catalog searches plus per-term
    rate-limit sleeps (~7s). The four TestBioGWAS endpoint tests each used to
    trigger that compute independently; sharing the result as a session
    fixture runs the real engine once and lets the endpoint tests exercise
    routing/dispatch/serialization against the shared output.
    """
    from med_research.pipeline.bioinformatics.gwas import run_gwas_analysis

    return run_gwas_analysis(disease_id="sle", max_studies=5, use_cache=True)


@pytest.fixture(scope="session")
def synergy_pairs():
    """Drug-synergy pairs for RA, computed once per process."""
    from med_research.pipeline.drug_synergy.engine import compute_synergy

    return compute_synergy(disease_id="ra", save=False)


@pytest.fixture(scope="session")
def expression_results():
    """Gene-expression correlations for RA, computed once per process."""
    from med_research.pipeline.gene_expression.correlator import compute_all_correlations

    return compute_all_correlations(disease_id="ra", save=False)


@pytest.fixture(scope="session")
def cross_disease_analysis():
    """Cross-disease analysis result, computed once per process."""
    from med_research.pipeline.cross_disease.analyzer import compute_cross_disease_analysis

    return compute_cross_disease_analysis()
