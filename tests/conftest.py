"""
Shared test fixtures for the Lupus Research Platform test suite.
"""

import ctypes
import json
import logging
import os
import sys
from pathlib import Path

import pytest

from med_research.pipeline.knowledge_graph.config import load_genes
from med_research.pipeline.reporting import REPORT_DIR_ENV_VAR

pytest_plugins = [
    "tests.evidence_http_fixtures",
    "tests.integration.http_fixtures",
    "tests.biomed.comparison.conftest",
]

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


@pytest.fixture(scope="session", autouse=True)
def _isolated_report_dir(tmp_path_factory):
    """Point every generated pipeline report at a private, per-worker directory.

    Report generators otherwise default to a fixed path beside the module that
    produces them. Under pytest-xdist two workers can run different modules that
    resolve to the *same* path, so one test can overwrite or delete the file
    another has just written — a report read-back then fails depending on timing,
    and every run litters the source tree with generated HTML.

    ``tmp_path_factory`` is already unique per worker, and the directory name
    records the worker id so the isolation is visible when debugging. The
    redirect is session-wide because the writers are plain functions called
    from dozens of modules, not fixtures with access to ``tmp_path``.
    """
    worker = os.environ.get("PYTEST_XDIST_WORKER", "main")
    directory = tmp_path_factory.mktemp(f"reports-{worker}")
    previous = os.environ.get(REPORT_DIR_ENV_VAR)
    os.environ[REPORT_DIR_ENV_VAR] = str(directory)
    yield directory
    if previous is None:
        os.environ.pop(REPORT_DIR_ENV_VAR, None)
    else:
        os.environ[REPORT_DIR_ENV_VAR] = previous


@pytest.fixture
def report_dir(_isolated_report_dir):
    """The session's private report directory, for tests that assert on paths."""
    return _isolated_report_dir


# ``-n auto`` sizes the worker pool from CPU count alone. Each xdist worker is a
# separate interpreter that imports the full scientific stack, so it holds several
# hundred MB before running a single test (Windows spawns rather than forks, so
# nothing is shared). A many-core machine with little free RAM therefore
# oversubscribes memory, the OS kills a worker mid-test, and only the test it was
# running is reported — which is why the failure set moves between runs instead of
# reproducing. Bound the pool by what memory can actually hold.
_WORKER_MEMORY_MB = 600
_MASTER_RESERVE_MB = 1024


def _available_memory_mb() -> int | None:
    """Best-effort free physical memory in MiB, or None if it cannot be read."""
    try:
        if sys.platform == "win32":

            class _MemoryStatusEx(ctypes.Structure):
                _fields_ = [
                    ("dwLength", ctypes.c_ulong),
                    ("dwMemoryLoad", ctypes.c_ulong),
                    ("ullTotalPhys", ctypes.c_ulonglong),
                    ("ullAvailPhys", ctypes.c_ulonglong),
                    ("ullTotalPageFile", ctypes.c_ulonglong),
                    ("ullAvailPageFile", ctypes.c_ulonglong),
                    ("ullTotalVirtual", ctypes.c_ulonglong),
                    ("ullAvailVirtual", ctypes.c_ulonglong),
                    ("ullAvailExtendedVirtual", ctypes.c_ulonglong),
                ]

            status = _MemoryStatusEx()
            status.dwLength = ctypes.sizeof(_MemoryStatusEx)
            if not ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(status)):
                return None
            return int(status.ullAvailPhys) // (1024 * 1024)

        if sys.platform == "darwin":
            pages = os.sysconf("SC_AVPHYS_PAGES")
            return int(pages) * os.sysconf("SC_PAGE_SIZE") // (1024 * 1024)

        with open("/proc/meminfo", encoding="utf-8") as meminfo:
            for line in meminfo:
                if line.startswith("MemAvailable:"):
                    return int(line.split()[1]) // 1024
    except (AttributeError, OSError, ValueError):
        return None
    return None


def _xdist_worker_budget_workers() -> int | None:
    """Workers that available memory can hold, or None when it is unknown."""
    available_mb = _available_memory_mb()
    if available_mb is None:
        return None
    return max(1, (available_mb - _MASTER_RESERVE_MB) // _WORKER_MEMORY_MB)


@pytest.hookimpl(tryfirst=True)
def pytest_xdist_auto_num_workers(config) -> int | None:
    """Cap ``-n auto`` at what the machine's free memory can hold.

    Returning None defers to xdist's own detection, so the pool only ever shrinks
    relative to normal behaviour and CI keeps full parallelism when it has the RAM.
    ``PYTEST_XDIST_AUTO_NUM_WORKERS`` (xdist's documented override) wins outright,
    and an explicit ``-n`` is never second-guessed because this hook only runs for
    ``auto``/``logical``.
    """
    if os.environ.get("PYTEST_XDIST_AUTO_NUM_WORKERS"):
        return None

    budget = _xdist_worker_budget_workers()
    cpu_workers = os.cpu_count() or 1
    if budget is None or budget >= cpu_workers:
        return None
    return budget


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
def _stable_test_disease_default(monkeypatch):
    """Optional API disease params default to sle in tests (not first CI slug)."""
    monkeypatch.setattr(
        "med_research.web.disease_params.default_disease_for_selection",
        lambda **kwargs: "sle",
    )


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
def enrichment_result():
    """Deterministic enrichment result for offline API contract tests."""
    genes = ["HLA-DRB1", "IRF5", "STAT4", "BLK", "TNFAIP3"]
    return {
        "coverage": {"level": "full"},
        "status": "ready",
        "gene_list": [{"symbol": symbol} for symbol in genes],
        "enrichment_results": {
            "GO_Biological_Process_2023": {
                "library": "GO_Biological_Process_2023",
                "terms": [
                    {
                        "term": "immune system process",
                        "overlap": "3/100",
                        "p_value": 0.001,
                        "adj_p_value": 0.01,
                        "odds_ratio": 2.5,
                        "combined_score": 30.0,
                        "genes": genes[:3],
                    }
                ],
                "total_significant": 1,
            }
        },
        "kg_pathway_matches": {},
    }


@pytest.fixture(scope="session")
def literature_result():
    """Deterministic literature-mining result for offline API contract tests."""
    return {
        "article_matches": [
            {
                "pmid": "99001001",
                "title": "Kinase inhibition in autoimmune disease",
                "abstract": "BTK inhibition modulates autoreactive B cells.",
            }
        ],
        "gene_coverage": {
            "BTK": {
                "articles": 1,
                "supporting_count": 1,
                "coverage_score": 100.0,
            }
        },
        "candidate_support": {},
    }


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
