"""Integration tests for ``execute_module`` error and blocked-module contracts."""

from __future__ import annotations

from unittest.mock import patch

import pytest

from med_research.diseases.coverage import module_coverage
from med_research.exceptions import (
    DataValidationError,
    ExternalAPIError,
    ModuleNotAvailableError,
)
from med_research.pipeline.dispatch import execute_module
from med_research.pipeline.registry import get_module

pytestmark = [pytest.mark.integration]


def _expect_typed_dispatch_failure(result, *, substring: str) -> None:
    """Assert Track 6 contract: typed failures populate ``PipelineRunResult.errors``."""
    assert result.success is False
    assert result.data is None
    assert result.errors, "expected non-empty errors list"
    assert any(substring in error for error in result.errors)


def _run_or_fail_contract(fn):
    """Run dispatch and fail clearly when typed errors escape uncaught (Track 6 gap)."""
    try:
        return fn()
    except (ExternalAPIError, DataValidationError, ModuleNotAvailableError) as exc:
        pytest.fail(
            "execute_module should catch "
            f"{type(exc).__name__} and populate result.errors (Track 6 contract): {exc}"
        )


class TestExecuteModuleBlockedContract:
    """Coverage gate blocks modules before ``run()`` is invoked."""

    def test_unknown_disease_is_blocked_without_run(self):
        result = execute_module("gwas", "not-a-disease")
        _expect_typed_dispatch_failure(result, substring="disease")

        module = get_module("gwas")
        # Coverage gate should stop before engine invocation for unknown diseases.
        coverage = module_coverage("not-a-disease", "gwas", module.coverage_inputs())
        assert coverage.status == "blocked"

    def test_blocked_module_matches_coverage_metadata(self):
        module_id = "gwas"
        disease_id = "not-a-disease"
        module = get_module(module_id)
        coverage = module_coverage(disease_id, "gwas", module.coverage_inputs())

        result = execute_module(module_id, disease_id)
        assert not result.success
        assert coverage.status == "blocked"
        assert result.errors


class TestExecuteModuleTypedErrorContract:
    """External and validation failures should surface in ``result.errors``."""

    def test_external_api_error_populates_errors(self, offline_pipeline_http_mocks):
        module = get_module("gwas")
        coverage = module_coverage("ra", "gwas", module.coverage_inputs())
        assert coverage.status == "ready", coverage.to_dict()

        def _raise_api_error(_disease_id: str, **_opts):
            raise ExternalAPIError("GWAS Catalog unavailable (contract test)")

        with (
            patch.object(module, "run", side_effect=_raise_api_error),
            patch("med_research.pipeline.dispatch.get_module", return_value=module),
        ):
            result = _run_or_fail_contract(
                lambda: execute_module("gwas", "ra", use_cache=True, max_studies=1)
            )

        _expect_typed_dispatch_failure(result, substring="GWAS Catalog unavailable")

    def test_validation_error_populates_errors(self, offline_pipeline_http_mocks):
        module = get_module("literature_mining")
        coverage = module_coverage(
            "ra",
            module._COVERAGE_MODULE or module.module_id,
            module.coverage_inputs(),
        )
        assert coverage.status == "ready", coverage.to_dict()

        def _raise_validation_error(_disease_id: str, **_opts):
            raise DataValidationError("curated gene table failed schema check")

        with (
            patch.object(module, "run", side_effect=_raise_validation_error),
            patch("med_research.pipeline.dispatch.get_module", return_value=module),
        ):
            result = _run_or_fail_contract(
                lambda: execute_module(
                    "literature_mining",
                    "ra",
                    use_cache=True,
                    max_per_query=5,
                )
            )

        _expect_typed_dispatch_failure(result, substring="schema check")
