"""Full offline ``run-all --full --export-html`` E2E for all known diseases.

Primary regression target: ``sle`` with network boundaries mocked via
``offline_pipeline_http_mocks`` — every runnable module must return structured
result data and an HTML (or KG JSON) artifact.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from med_research.diseases.coverage import module_coverage
from med_research.pipeline.dispatch import execute_module
from med_research.pipeline.registry import get_module
from tests.cli_helpers import run_cli_handler
from tests.integration.conftest import ALL_DISEASES

PROJECT_ROOT = Path(__file__).parent.parent.parent
PIPELINE_ROOT = PROJECT_ROOT / "src/med_research/pipeline"
DISEASES = ALL_DISEASES

pytestmark = [pytest.mark.integration]


def _run_all_module_ids(*, skip_ml: bool = True) -> list[str]:
    from med_research.cli import PIPELINE_STEPS, PIPELINE_STEPS_FULL, _steps_to_parallel_modules

    steps = list(PIPELINE_STEPS) + list(PIPELINE_STEPS_FULL)
    module_ids = _steps_to_parallel_modules(steps)
    if skip_ml:
        module_ids = [module_id for module_id in module_ids if module_id != "ml_predictor"]
    return module_ids


def _coverage_bucket(module_id: str) -> str:
    module = get_module(module_id)
    bucket = getattr(module, "_COVERAGE_MODULE", None)
    return bucket if isinstance(bucket, str) else module.module_id


def _run_all_opts(module_id: str) -> dict:
    opts: dict = {"use_cache": True}
    if module_id == "clinical_trials":
        opts["max_results"] = 20
    elif module_id == "literature_mining":
        opts["max_per_query"] = 20
    elif module_id in {"virtual_screening", "drug_synergy"}:
        opts["top"] = 10
    elif module_id == "adverse_events":
        opts["top"] = 15
    return opts


def _assert_module_outcome(module_id: str, disease_id: str, result) -> None:
    coverage = module_coverage(
        disease_id,
        _coverage_bucket(module_id),
        get_module(module_id).coverage_inputs(),
    )
    if coverage.is_runnable:
        assert result.success, f"{module_id}@{disease_id}: {result.errors}"
        if isinstance(result.data, dict) and "coverage" in result.data:
            assert result.data["coverage"]["module"]
            assert result.data["coverage"]["status"] in {
                "ready",
                "limited_coverage",
                "blocked",
            }
    else:
        assert not result.success, f"{module_id}@{disease_id} should be blocked"
        assert result.errors, f"{module_id}@{disease_id} missing blocked error detail"
        blocked = coverage.to_dict()
        assert blocked["status"] == "blocked"
        assert blocked["module"]


MODULE_REPORT_PATHS: dict[str, Path] = {
    "knowledge_graph": PIPELINE_ROOT / "knowledge_graph/web",
    "drug_repurposing": PIPELINE_ROOT / "drug_repurposing/report.html",
    "gwas": PIPELINE_ROOT / "bioinformatics/bioinformatics_report.html",
    "enrichment": PIPELINE_ROOT / "bioinformatics/bioinformatics_report.html",
    "ppi": PIPELINE_ROOT / "bioinformatics/bioinformatics_report.html",
    "literature_mining": PIPELINE_ROOT / "literature_mining/literature_report.html",
    "virtual_screening": PIPELINE_ROOT / "virtual_screening/screening_report.html",
    "clinical_trials": PIPELINE_ROOT / "clinical_trials/ct_report.html",
    "drug_synergy": PIPELINE_ROOT / "drug_synergy/report.html",
    "adverse_events": PIPELINE_ROOT / "adverse_events/report.html",
    "network_pharmacology": PIPELINE_ROOT / "network_pharmacology/report.html",
    "gene_expression": PIPELINE_ROOT / "gene_expression/report.html",
    "car_t_predictor": PIPELINE_ROOT / "car_t_predictor/report.html",
    "biomarker_discovery": PIPELINE_ROOT / "biomarker_discovery/report.html",
    "cross_disease": PIPELINE_ROOT / "cross_disease/report.html",
}


def _assert_report_path(module_id: str, disease_id: str, report_path: Path | None) -> None:
    expected = MODULE_REPORT_PATHS.get(module_id)
    assert expected is not None, f"No report mapping for {module_id}"
    if module_id == "knowledge_graph":
        assert (expected / f"graph_data_{disease_id}.json").exists()
        if report_path is not None:
            assert report_path == expected / f"graph_data_{disease_id}.json"
    else:
        assert expected.exists(), f"Missing report for {module_id}: {expected}"
        if report_path is not None:
            assert report_path == expected


@pytest.mark.parametrize("disease_id", DISEASES)
class TestFullPipelineExportHtml:
    """Exercise run-all --full --export-html and per-module dispatch offline."""

    def test_run_all_full_export_html_cli(self, offline_pipeline_http_mocks, disease_id, caplog):
        from med_research.cli import cmd_run_all

        with caplog.at_level("INFO"):
            exit_code = run_cli_handler(
                cmd_run_all,
                "run-all",
                "--disease",
                disease_id,
                "--full",
                "--export-html",
                "--skip-ml",
            )

        assert exit_code == 0, caplog.text
        assert "Pipeline complete" in caplog.text

    def test_each_run_all_module_dispatch(self, offline_pipeline_http_mocks, disease_id):
        for module_id in _run_all_module_ids():
            result = execute_module(
                module_id,
                disease_id,
                export_html=True,
                **_run_all_opts(module_id),
            )
            _assert_module_outcome(module_id, disease_id, result)
            if result.success:
                assert result.data is not None, f"{module_id}@{disease_id} missing result payload"
                if isinstance(result.data, (dict, list)):
                    assert len(result.data) > 0, f"{module_id}@{disease_id} returned empty result"
                _assert_report_path(module_id, disease_id, result.report_path)


class TestSleFullPipelineArtifacts:
    """Focused sle run-all artifact gate (network mocked at HTTP boundaries)."""

    def test_sle_run_all_modules_produce_results_and_reports(self, offline_pipeline_http_mocks):
        disease_id = "sle"
        for module_id in _run_all_module_ids():
            result = execute_module(
                module_id,
                disease_id,
                export_html=True,
                **_run_all_opts(module_id),
            )
            _assert_module_outcome(module_id, disease_id, result)
            if result.success:
                assert result.data is not None
                if isinstance(result.data, (dict, list)):
                    assert len(result.data) > 0
                _assert_report_path(module_id, disease_id, result.report_path)
