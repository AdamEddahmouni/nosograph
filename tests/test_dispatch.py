"""Unit tests for pipeline dispatch (``execute_module``)."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from med_research.diseases.coverage import ModuleCoverage
from med_research.exceptions import (
    APIQuotaError,
    APITimeoutError,
    ConfigurationError,
    DataValidationError,
    ExternalAPIError,
    ModuleNotAvailableError,
)
from med_research.pipeline.base import PipelineRunResult
from med_research.pipeline.dispatch import (
    ProgressReporter,
    _accepts_legacy,
    execute_module,
    render_module_report,
    standard_to_legacy,
)
from med_research.pipeline.registry import get_module

pytestmark = pytest.mark.unit


class TestProgressBridging:
    def test_standard_to_legacy_percent(self):
        calls: list[tuple[int, str]] = []

        def sink(percent: int, message: str) -> None:
            calls.append((percent, message))

        standard_to_legacy("fetching", 1, 4, sink)
        assert calls == [(25, "fetching")]

    def test_progress_reporter_forwards_to_legacy_sink(self):
        sink = MagicMock()
        reporter = ProgressReporter(sink)
        reporter("enrichment", 2, 5)
        sink.assert_called_once_with(40, "enrichment")

    def test_accepts_legacy_two_arg_callback(self):
        def legacy(percent: int, message: str) -> None:
            pass

        assert _accepts_legacy(legacy) is True

    def test_accepts_standard_three_arg_callback(self):
        def standard(step: str, current: int, total: int) -> None:
            pass

        assert _accepts_legacy(standard) is False


class TestExecuteModule:
    def _mock_module(self) -> MagicMock:
        module = MagicMock()
        module.module_id = "gwas"
        module._COVERAGE_MODULE = "gwas"
        module.coverage_inputs.return_value = ("gwas_search_terms",)
        return module

    def test_successful_run_returns_pipeline_result(self):
        mock_module = self._mock_module()
        mock_module.run.return_value = {"hits": [1, 2]}

        runnable = ModuleCoverage(
            disease_id="ra",
            module="gwas",
            level="full",
            status="ready",
            curated_inputs=["gwas_search_terms"],
        )

        with (
            patch("med_research.pipeline.dispatch.get_module", return_value=mock_module),
            patch(
                "med_research.pipeline.dispatch.module_coverage",
                return_value=runnable,
            ),
        ):
            result = execute_module("gwas", "ra", max_studies=5)

        assert isinstance(result, PipelineRunResult)
        assert result.success is True
        assert result.data == {"hits": [1, 2]}
        assert result.report_path is None
        assert result.provenance is None
        assert result.errors == []
        mock_module.run.assert_called_once_with("ra", max_studies=5)

    def test_blocked_coverage_returns_failure_without_run(self):
        mock_module = self._mock_module()
        blocked = ModuleCoverage(
            disease_id="ra",
            module="gwas",
            level="unsupported",
            status="blocked",
            missing_inputs=["gwas_search_terms"],
            limitations=["Required curated inputs are missing: gwas_search_terms."],
        )

        with (
            patch("med_research.pipeline.dispatch.get_module", return_value=mock_module),
            patch(
                "med_research.pipeline.dispatch.module_coverage",
                return_value=blocked,
            ),
        ):
            result = execute_module("gwas", "ra")

        assert result.success is False
        assert result.data is None
        assert len(result.errors) == 1
        assert "gwas_search_terms" in result.errors[0]
        mock_module.run.assert_not_called()

    def test_unknown_module_returns_failure(self):
        with patch(
            "med_research.pipeline.dispatch.get_module",
            side_effect=KeyError("Unknown pipeline module 'missing'"),
        ):
            result = execute_module("missing", "ra")

        assert result.success is False
        assert result.data is None
        assert len(result.errors) == 1
        assert "missing" in result.errors[0]

    def test_module_not_available_error_from_run_is_caught(self):
        mock_module = self._mock_module()
        mock_module.run.side_effect = ModuleNotAvailableError("dependency offline")

        runnable = ModuleCoverage(
            disease_id="ra",
            module="gwas",
            level="full",
            status="ready",
        )

        with (
            patch("med_research.pipeline.dispatch.get_module", return_value=mock_module),
            patch(
                "med_research.pipeline.dispatch.module_coverage",
                return_value=runnable,
            ),
        ):
            result = execute_module("gwas", "ra")

        assert result.success is False
        assert result.data is None
        assert result.errors == ["dependency offline"]

    @pytest.mark.parametrize(
        ("exc_type", "message"),
        [
            (ExternalAPIError, "GWAS API unavailable"),
            (APITimeoutError, "request timed out"),
            (APIQuotaError, "rate limited"),
            (DataValidationError, "invalid gene payload"),
            (ConfigurationError, "missing API key"),
        ],
    )
    def test_typed_errors_from_run_are_caught(self, exc_type, message):
        mock_module = self._mock_module()
        mock_module.run.side_effect = exc_type(message)

        runnable = ModuleCoverage(
            disease_id="ra",
            module="gwas",
            level="full",
            status="ready",
        )

        with (
            patch("med_research.pipeline.dispatch.get_module", return_value=mock_module),
            patch(
                "med_research.pipeline.dispatch.module_coverage",
                return_value=runnable,
            ),
        ):
            result = execute_module("gwas", "ra")

        assert result.success is False
        assert result.data is None
        assert result.errors == [message]

    def test_render_module_report_uses_registry_adapter(self, tmp_path: Path) -> None:
        mock_module = self._mock_module()
        mock_module.build_provenance.return_value = {"module": "gwas"}
        mock_module.report.return_value = tmp_path / "report.html"

        with patch("med_research.pipeline.dispatch.get_module", return_value=mock_module):
            path = render_module_report("gwas", {"hits": []}, "ra", run_id="test")

        mock_module.build_provenance.assert_called_once_with("ra", run_id="test")
        mock_module.report.assert_called_once_with(
            {"hits": []}, "ra", provenance={"module": "gwas"}
        )
        assert path == tmp_path / "report.html"

    def test_export_html_builds_provenance_and_report(self, tmp_path: Path):
        mock_module = self._mock_module()
        mock_module.run.return_value = {"hits": []}
        mock_module.build_provenance.return_value = {"module": "gwas", "disease_id": "ra"}
        mock_module.report.return_value = tmp_path / "report.html"

        runnable = ModuleCoverage(
            disease_id="ra",
            module="gwas",
            level="full",
            status="ready",
        )

        with (
            patch("med_research.pipeline.dispatch.get_module", return_value=mock_module),
            patch(
                "med_research.pipeline.dispatch.module_coverage",
                return_value=runnable,
            ),
        ):
            result = execute_module("gwas", "ra", export_html=True, cache_or_live="live")

        assert result.success is True
        assert result.report_path == tmp_path / "report.html"
        assert result.provenance == {"module": "gwas", "disease_id": "ra"}
        mock_module.build_provenance.assert_called_once_with("ra", cache_or_live="live")
        mock_module.report.assert_called_once_with(
            {"hits": []},
            "ra",
            provenance={"module": "gwas", "disease_id": "ra"},
        )

    def test_legacy_progress_callback_passed_through(self):
        mock_module = self._mock_module()
        mock_module.run.return_value = {}
        progress = MagicMock()

        runnable = ModuleCoverage(
            disease_id="ra",
            module="gwas",
            level="full",
            status="ready",
        )

        with (
            patch("med_research.pipeline.dispatch.get_module", return_value=mock_module),
            patch(
                "med_research.pipeline.dispatch.module_coverage",
                return_value=runnable,
            ),
        ):
            execute_module("gwas", "ra", progress_callback=progress)

        _, kwargs = mock_module.run.call_args
        assert kwargs["progress_callback"] is progress

    def test_standard_progress_callback_passed_to_engine(self):
        mock_module = self._mock_module()
        mock_module.run.return_value = {}
        standard_calls: list[tuple[str, int, int]] = []

        def standard_sink(step: str, current: int, total: int) -> None:
            standard_calls.append((step, current, total))

        runnable = ModuleCoverage(
            disease_id="ra",
            module="gwas",
            level="full",
            status="ready",
        )

        with (
            patch("med_research.pipeline.dispatch.get_module", return_value=mock_module),
            patch(
                "med_research.pipeline.dispatch.module_coverage",
                return_value=runnable,
            ),
        ):
            execute_module("gwas", "ra", progress_callback=standard_sink)

        _, kwargs = mock_module.run.call_args
        engine_cb = kwargs["progress_callback"]
        engine_cb("step label", 2, 5)
        assert standard_calls == [("step label", 2, 5)]

    def test_integration_with_real_registry_adapter(self):
        """Smoke: real adapter + real coverage gate for RA GWAS."""


        from med_research.diseases.coverage import module_coverage

        module = get_module("gwas")
        coverage = module_coverage("ra", "gwas", module.coverage_inputs())
        assert coverage.status == "ready", coverage.to_dict()

        with (
            patch.object(module, "run", return_value={"status": "ready"}) as mock_run,
            patch(
                "med_research.pipeline.dispatch.get_module",
                return_value=module,
            ),
        ):
            result = execute_module("gwas", "ra")

        assert result.success is True
        mock_run.assert_called_once()
