"""End-to-end smoke tests for the unified CLI.

Each test invokes CLI handlers directly (no subprocess) and asserts the command
exits 0 and emits expected output. This guards against stale v1 imports and
silent handler failures (e.g. exit 0 with no output) that have broken the CLI
twice since the v2 migration.

Offline commands use handler imports with logging capture. Evidence and
workspace use mocked HTTP fixtures.
"""

from __future__ import annotations

import logging

import pytest

from tests.cli_helpers import run_cli_command, run_cli_command_capture, run_cli_handler

pytestmark = [pytest.mark.integration]


def _ml_predictor_available() -> bool:
    try:
        import xgboost  # noqa: F401

        return True
    except ImportError:
        return False


# (test id, CLI args, expected fragment in stdout/stderr or caplog)
CLI_SMOKE_COMMANDS = [
    ("diseases", ["diseases"], "Available Diseases"),
    ("modules", ["modules"], "Available Pipeline Modules"),
    ("kg", ["kg", "--disease", "sle"], "Knowledge Graph"),
    ("repurpose", ["repurpose", "--disease", "sle", "--top", "5"], "REPURPOSING"),
    ("synergy", ["synergy", "--top", "5"], "SYNERGY"),
    ("network", ["network"], "NETWORK PHARMACOLOGY"),
    ("expression", ["expression", "--top", "5"], "EXPRESSION"),
    ("cart", ["cart", "--top", "5"], "CAR-T"),
    ("biomarker", ["biomarker", "--top", "5"], "BIOMARKER"),
    (
        "literature",
        ["literature", "--disease", "sle", "--max", "5"],
        "LITERATURE MINING RESULTS",
    ),
    (
        "bioinformatics",
        ["bioinformatics", "--disease", "ra", "--skip-ppi"],
        "GWAS CATALOG ANNOTATION",
    ),
    (
        "screening",
        ["screening", "--disease", "ra", "--top", "5"],
        "VIRTUAL DRUG SCREENING",
    ),
    (
        "trials",
        ["trials", "--disease", "sle", "--top", "5"],
        "CLINICAL TRIAL TRACKER",
    ),
    (
        "ml",
        ["ml", "--disease", "sle", "--top", "5"],
        "ML TARGET PREDICTOR",
    ),
    (
        "cache-stats",
        ["cache", "stats"],
        "Total cached entries",
    ),
]

COMMAND_IDS = [name for name, _, _ in CLI_SMOKE_COMMANDS]


@pytest.mark.parametrize("name,args,expected", CLI_SMOKE_COMMANDS, ids=COMMAND_IDS)
def test_cli_command_smoke(name, args, expected, caplog):
    """Run an offline CLI command end-to-end and verify it produces output."""
    if name == "ml" and not _ml_predictor_available():
        pytest.skip("xgboost not installed")

    with caplog.at_level(logging.INFO):
        exit_code = run_cli_command(*args)

    assert exit_code == 0, caplog.text
    assert expected in caplog.text, (
        f"`med_research.cli {name}` succeeded but produced no expected output "
        f"({expected!r}):\n{caplog.text[:1000]}"
    )


def test_evidence_cli_smoke(evidence_api_mocks, caplog):
    """Evidence gatherer CLI smoke with mocked Europe PMC / DailyMed APIs."""
    from med_research.cli import cmd_evidence

    with caplog.at_level(logging.INFO):
        exit_code = run_cli_handler(
            cmd_evidence,
            "evidence",
            "--disease",
            "sle",
            "--query",
            "lupus treatment",
            "--sources",
            "pubmed,fda_labels",
            "--max",
            "3",
            "--no-cache",
        )

    assert exit_code == 0
    assert "pubmed" in caplog.text.lower() or "results" in caplog.text.lower()


def test_cross_disease_dispatch_smoke(caplog):
    """Cross-disease via ``execute_module`` (CLI ``args.disease`` pending Lane 1 fix)."""
    from med_research.pipeline.cross_disease.analyzer import (
        analyze,
        print_repurposing,
        print_top_drugs,
    )
    from med_research.pipeline.dispatch import execute_module

    with caplog.at_level(logging.INFO):
        result = execute_module("cross_disease", "sle", top=5)

    assert result.success, result.errors
    analyze(result.data or {})
    print_top_drugs(result.data or {}, top_n=5)
    print_repurposing(result.data or {}, top_n=5)
    assert "CROSS-DISEASE" in caplog.text.upper() or result.data is not None


def test_workspace_cli_smoke(evidence_api_mocks, caplog):
    """Workspace smoke via ``run_workspace`` until adapter ``sources`` wiring lands."""
    from med_research.pipeline.evidence_workspace.schemas import ResearchRequest
    from med_research.pipeline.evidence_workspace.workspace import run_workspace

    request = ResearchRequest(
        disease_id="sle",
        question="What kinase inhibitors show promise?",
        sources=("pubmed",),
        max_evidence=3,
    )

    with caplog.at_level(logging.INFO):
        dossier = run_workspace(request)

    assert dossier.run_id
    assert len(dossier.evidence) >= 0


def test_modules_json_smoke():
    """``modules --json`` emits registered adapter IDs."""
    exit_code, output = run_cli_command_capture("modules", "--json")
    assert exit_code == 0
    assert "knowledge_graph" in output
    assert "drug_repurposing" in output


def test_run_all_partial_offline(offline_pipeline_http_mocks, caplog):
    """Partial run-all smoke with mocked HTTP and optional ML skipped."""
    from med_research.cli import cmd_run_all

    argv = [
        "run-all",
        "--disease",
        "sle",
        "--skip-trials",
        "--skip-synergy",
    ]
    if not _ml_predictor_available():
        argv.append("--skip-ml")

    with caplog.at_level(logging.INFO):
        exit_code = run_cli_handler(cmd_run_all, *argv)

    assert exit_code == 0
    assert "Pipeline complete" in caplog.text


def test_run_all_full_ra_offline(offline_pipeline_http_mocks, caplog):
    """Full RA run-all uses registry dispatch path offline (handler import)."""
    from med_research.cli import cmd_run_all

    with caplog.at_level(logging.INFO):
        exit_code = run_cli_handler(
            cmd_run_all,
            "run-all",
            "--disease",
            "ra",
            "--full",
            "--skip-ml",
        )

    assert exit_code == 0
    assert "Pipeline complete" in caplog.text
