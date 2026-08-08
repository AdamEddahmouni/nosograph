"""Progress callback contract tests for pipeline adapters."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from med_research.diseases.coverage import module_coverage
from med_research.pipeline.dispatch import execute_module
from med_research.pipeline.registry import get_module, list_modules
from tests.test_pipeline_base import assert_monotonic_progress

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
PROGRESS_PENDING_MODULES = frozenset({"evidence_monitor"})


def _ml_deps_available() -> bool:
    try:
        import sklearn  # noqa: F401
        import xgboost  # noqa: F401
    except ImportError:
        return False
    return True


def _semantic_deps_available() -> bool:
    try:
        import chromadb  # noqa: F401
        from sentence_transformers import SentenceTransformer  # noqa: F401
    except ImportError:
        return False
    return True


def _optional_dep_skip_reason(module_id: str) -> str | None:
    if module_id in PROGRESS_PENDING_MODULES:
        return "progress callback not yet wired for this adapter"
    if module_id in ML_MODULES and not _ml_deps_available():
        return "xgboost/scikit-learn not installed"
    if module_id in SEMANTIC_MODULES and not _semantic_deps_available():
        return "chromadb/sentence-transformers not installed"
    return None


def _run_kwargs(module_id: str) -> dict:
    if module_id in ML_MODULES:
        return {"top": 10}
    if module_id in SEMANTIC_MODULES:
        return {"top": 5}
    return dict(MODULE_RUN_KWARGS.get(module_id, {}))


@pytest.mark.parametrize("module_id", list_modules())
def test_adapter_progress_callback_monotonic(module_id: str):
    """Each runnable adapter emits monotonic (step, current, total) progress ticks."""
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

    calls: list[tuple[str, int, int]] = []

    def progress(step: str, current: int, total: int) -> None:
        calls.append((step, current, total))

    module.run(disease_id, progress_callback=progress, **_run_kwargs(module_id))
    assert_monotonic_progress(calls)


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
