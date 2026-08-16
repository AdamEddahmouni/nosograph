"""Progress callback contract tests for pipeline adapters."""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from med_research.diseases.coverage import module_coverage
from med_research.pipeline.dispatch import execute_module
from med_research.pipeline.registry import get_module, list_modules
from tests.test_pipeline_base import assert_monotonic_progress

pytestmark = pytest.mark.unit


MODULE_RUN_KWARGS: dict[str, dict] = {
    "clinical_trials": {"use_cache": True},
    "cross_disease": {},
    "enrichment": {"use_cache": True},
    "evidence_gather": {"sources": ["pubmed"], "max_per_source": 3, "use_cache": True},
    "evidence_monitor": {"sources": ["pubmed"], "max_per_query": 3},
    "evidence_workspace": {
        "max_evidence": 5,
        "enable_llm": False,
    },
    "gwas": {"use_cache": True},
    "literature_mining": {"use_cache": True},
    "llm_extractor": {
        "use_cache": True,
        "max_articles": 1,
        "sources": ["pubmed"],
    },
    "ppi": {"use_cache": True},
    "virtual_screening": {"gene": "PTPN22", "top_n": 3},
}

ML_MODULES = frozenset({"ml_predictor"})
SEMANTIC_MODULES = frozenset({"semantic_search"})


def _ml_deps_available() -> bool:
    try:
        import sklearn  # noqa: F401
        import xgboost  # noqa: F401
    except ImportError:
        return False
    return True


def _optional_dep_skip_reason(module_id: str) -> str | None:
    if module_id in ML_MODULES and not _ml_deps_available():
        return "xgboost/scikit-learn not installed"
    return None


def _run_kwargs(module_id: str) -> dict:
    if module_id in ML_MODULES:
        return {"top": 10}
    if module_id in SEMANTIC_MODULES:
        return {"top": 5}
    return dict(MODULE_RUN_KWARGS.get(module_id, {}))


def _stub_semantic_search_empty_path(monkeypatch: pytest.MonkeyPatch) -> None:
    """Let semantic_search execute its real no-index path without optional deps.

    CI lacks chromadb/sentence-transformers, so the engine must be pushed past
    the dependency gates to reach the empty (no indexed collection) result path
    and still emit its ``semantic search`` progress tick. The fake chromadb
    client makes every collection lookup fail, which is exactly the early-return
    regression that used to skip the tick.
    """

    import med_research.pipeline.semantic_search.engine as engine_mod

    class _FakeEmbedder:
        def encode(self, texts: Any) -> list[list[float]]:
            if isinstance(texts, str):
                texts = [texts]
            return [[0.0] * 384 for _ in texts]

    def _stub_load_model(self: Any) -> None:
        self.model = _FakeEmbedder()

    def _raise_no_collection(name: str) -> Any:
        raise ValueError(f"no indexed collection for {name}")

    monkeypatch.setattr(engine_mod, "_check_deps", lambda: True)
    monkeypatch.setattr(engine_mod.SemanticSearchEngine, "_load_model", _stub_load_model)
    monkeypatch.setattr(
        engine_mod,
        "chromadb",
        SimpleNamespace(
            PersistentClient=lambda path: SimpleNamespace(get_collection=_raise_no_collection)
        ),
    )


def _stub_evidence_monitor_empty_gather(monkeypatch: pytest.MonkeyPatch) -> None:
    """Make monitor snapshotting run offline against empty evidence."""
    monkeypatch.setattr(
        "med_research.pipeline.evidence.monitor.gather_evidence",
        lambda *args, **kwargs: {"all_results": [], "total_results": 0},
    )


_EMPTY_PATH_STUBS = {
    "semantic_search": _stub_semantic_search_empty_path,
    "evidence_monitor": _stub_evidence_monitor_empty_gather,
}


def _apply_empty_path_stubs(module_id: str, monkeypatch: pytest.MonkeyPatch) -> None:
    """Force empty-result data seams for modules that need them to run offline."""
    stub = _EMPTY_PATH_STUBS.get(module_id)
    if stub is not None:
        stub(monkeypatch)


@pytest.mark.parametrize("module_id", list_modules())
def test_adapter_progress_contract(module_id: str, monkeypatch: pytest.MonkeyPatch):
    """Registry-level progress contract for every runnable adapter.

    Each adapter must emit at least one monotonic ``(step, current, total)``
    progress tick, even on empty-result paths and without optional
    dependencies installed. The semantic_search no-index path is stubbed so it
    executes (and must tick) even in CI, and evidence_monitor's evidence
    fetching is stubbed to empty. This guards the regression where an engine
    returned ``[]`` from its empty-result path before emitting any progress
    tick, which previously went unnoticed because the test skipped in CI.
    """
    skip_reason = _optional_dep_skip_reason(module_id)
    if skip_reason:
        pytest.skip(skip_reason)

    module = get_module(module_id)
    disease_id = "ra"
    coverage = module_coverage(
        disease_id,
        getattr(module, "_COVERAGE_MODULE", module_id),
        module.coverage_inputs(),
    )
    if not coverage.is_runnable:
        pytest.skip(f"{module_id} not runnable for {disease_id}")

    _apply_empty_path_stubs(module_id, monkeypatch)

    calls: list[tuple[str, int, int]] = []

    def progress(step: str, current: int, total: int) -> None:
        calls.append((step, current, total))

    module.run(disease_id, progress_callback=progress, **_run_kwargs(module_id))
    assert_monotonic_progress(calls)
    if module_id == "semantic_search":
        assert any(step == "semantic search" for step, _, _ in calls), (
            "semantic_search must emit a 'semantic search' tick even when no "
            "indexed collection exists"
        )


def test_dispatch_progress_callback_wired():
    """execute_module passes a callable progress_callback into module.run."""
    module = get_module("gwas")
    disease_id = "ra"
    coverage = module_coverage(
        disease_id,
        module._COVERAGE_MODULE,
        module.coverage_inputs(),
    )
    if not coverage.is_runnable:
        pytest.skip("gwas not runnable for ra")

    mock_run = MagicMock(return_value={"status": "ready"})

    with (
        patch.object(module, "run", mock_run),
        patch("med_research.pipeline.dispatch.get_module", return_value=module),
    ):
        result = execute_module(
            "gwas",
            disease_id,
            use_cache=True,
            progress_callback=lambda s, c, t: None,
        )

    assert result.success is True
    mock_run.assert_called_once()
    _, kwargs = mock_run.call_args
    assert callable(kwargs["progress_callback"])
