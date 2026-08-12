"""Full offline ``run-all --full`` end-to-end test for RA.

Exercises the CLI and DAG scheduler through ``pipeline.dispatch.execute_module``.

Note: ``test_run_all_full_parallel_cli`` expects per-disease atomic module outputs
and a corrected biomarker ``depends_on`` DAG (Track 3). If parallel run-all still
fails with JSON parse errors in biomarker_discovery, that is a known Track 3 gap —
the sequential path and ``execute_module`` DAG runner remain the contract tests here.
"""

from __future__ import annotations

import pytest

from tests.cli_helpers import run_cli_handler

DISEASE = "ra"

pytestmark = [pytest.mark.integration]




def _run_all_steps(*, skip_ml: bool = True):
    """Return ordered registry module IDs for ``run-all --full`` (mirrors cli.py)."""
    from med_research.cli import PIPELINE_STEPS, PIPELINE_STEPS_FULL, _steps_to_parallel_modules

    steps = list(PIPELINE_STEPS) + list(PIPELINE_STEPS_FULL)
    module_ids = _steps_to_parallel_modules(steps)
    if skip_ml:
        module_ids = [module_id for module_id in module_ids if module_id != "ml_predictor"]
    return module_ids


class TestRunAllFullOfflineRA:
    """Exercise the complete RA pipeline offline with mocked external HTTP."""

    def test_registry_modules_cover_run_all_full(self):
        from med_research.pipeline.registry import list_modules

        module_ids = _run_all_steps()
        registered = set(list_modules())
        missing = sorted(set(module_ids) - registered)
        assert not missing, f"run-all --full references unregistered modules: {missing}"

    def test_run_all_full_sequential_cli(self, offline_pipeline_http_mocks, caplog):
        from med_research.cli import cmd_run_all

        with caplog.at_level("INFO"):
            exit_code = run_cli_handler(
                cmd_run_all,
                "run-all",
                "--disease",
                DISEASE,
                "--full",
                "--skip-ml",
            )

        assert exit_code == 0, caplog.text
        assert "Pipeline complete" in caplog.text

    def test_run_all_full_parallel_cli(self, offline_pipeline_http_mocks, caplog):
        from med_research.cli import cmd_run_all

        with caplog.at_level("INFO"):
            exit_code = run_cli_handler(
                cmd_run_all,
                "run-all",
                "--disease",
                DISEASE,
                "--full",
                "--parallel",
                "--skip-ml",
            )

        assert exit_code == 0, caplog.text
        assert "Parallel DAG execution" in caplog.text
        assert "Pipeline complete" in caplog.text

    def test_biomarker_not_parallel_with_upstream_writers(self):
        """Biomarker must not share a DAG level with modules it reads from."""
        from med_research.pipeline.scheduler import topological_levels
        from tests.integration.test_run_all_e2e import _run_all_steps

        module_ids = _run_all_steps()
        levels = topological_levels(module_ids)
        level_by_module = {
            module_id: index for index, level in enumerate(levels) for module_id in level
        }
        biomarker_level = level_by_module["biomarker_discovery"]
        for upstream in (
            "gene_expression",
            "car_t_predictor",
            "drug_repurposing",
            "adverse_events",
            "drug_synergy",
        ):
            assert level_by_module[upstream] < biomarker_level, (
                f"{upstream} must finish before biomarker_discovery"
            )

    def test_run_all_full_via_execute_module(self, offline_pipeline_http_mocks):
        """DAG scheduler dispatches each module through ``execute_module``."""
        from med_research.pipeline.dispatch import execute_module
        from med_research.pipeline.scheduler import run_levels, validate_dag

        module_ids = _run_all_steps()
        levels = validate_dag(module_ids)
        executed: list[str] = []

        def runner(module_id: str) -> None:
            result = execute_module(module_id, DISEASE, use_cache=True)
            assert result.success, f"{module_id} failed: {result.errors}"
            executed.append(module_id)

        errors = 0
        for level in levels:
            errors += run_levels([level], runner, parallel=False)

        assert errors == 0
        assert set(executed) == set(module_ids)
