"""Unit tests for CLI behavior that should not require subprocesses."""

from __future__ import annotations

import json
from types import SimpleNamespace
from unittest.mock import patch

import pytest


def test_modules_json_lists_registry_modules(capsys):
    """``modules --json`` must list every registry adapter."""
    from med_research.cli import cmd_modules
    from med_research.pipeline.registry import list_modules

    registered = list_modules()
    assert registered, "registry should have pilot adapters from Wave 1A"

    exit_code = cmd_modules(SimpleNamespace(json=True))
    captured = capsys.readouterr()

    assert exit_code == 0
    payload = json.loads(captured.out)
    assert payload == registered
    for module_id in registered:
        assert module_id in payload


def test_modules_output_includes_registered_modules(caplog):
    """Human-readable ``modules`` output must mention registry adapters."""
    import logging

    from med_research.cli import cmd_modules
    from med_research.pipeline.registry import list_modules

    registered = list_modules()
    assert registered

    with caplog.at_level(logging.INFO):
        exit_code = cmd_modules(SimpleNamespace(json=False))

    assert exit_code == 0
    combined = caplog.text
    assert "Registered adapters" in combined
    for module_id in registered:
        assert module_id in combined


def test_serve_reload_disabled_when_debug_false(monkeypatch):
    """--reload must not enable uvicorn reload unless DEBUG=true."""
    monkeypatch.setenv("DEBUG", "false")

    from med_research.cli import cmd_serve

    args = SimpleNamespace(host="127.0.0.1", port=8000, reload=True)

    with (
        patch("med_research.web.config.DEBUG", False),
        patch("uvicorn.run") as mock_run,
    ):
        cmd_serve(args)

    mock_run.assert_called_once()
    assert mock_run.call_args.kwargs["reload"] is False


def test_serve_reload_enabled_when_debug_true(monkeypatch):
    """--reload is honored when DEBUG=true."""
    monkeypatch.setenv("DEBUG", "true")

    from med_research.cli import cmd_serve

    args = SimpleNamespace(host="127.0.0.1", port=8000, reload=True)

    with (
        patch("med_research.web.config.DEBUG", True),
        patch("uvicorn.run") as mock_run,
    ):
        cmd_serve(args)

    mock_run.assert_called_once()
    assert mock_run.call_args.kwargs["reload"] is True


@pytest.mark.parametrize(
    ("debug", "reload_flag", "expected_reload"),
    [
        (True, False, False),
        (True, True, True),
        (False, True, False),
        (False, False, False),
    ],
)
def test_serve_reload_guard(debug, reload_flag, expected_reload):
    """Reload follows both the --reload flag and DEBUG guard."""
    from med_research.cli import cmd_serve

    args = SimpleNamespace(host="127.0.0.1", port=8000, reload=reload_flag)

    with (
        patch("med_research.web.config.DEBUG", debug),
        patch("uvicorn.run") as mock_run,
    ):
        cmd_serve(args)

    assert mock_run.call_args.kwargs["reload"] is expected_reload


def test_run_all_parser_accepts_parallel_and_full_flags():
    """run-all exposes --parallel, --sequential, and --full flags."""
    from tests.cli_helpers import parse_cli_args

    args = parse_cli_args("run-all", "--disease", "ra", "--parallel", "--full")
    assert args.parallel is True
    assert args.sequential is False
    assert args.full is True
    assert args.disease == "ra"


def test_get_pipeline_steps_core_only_by_default():
    from med_research.cli import PIPELINE_STEPS, _get_pipeline_steps

    args = SimpleNamespace(full=False, skip_trials=False, skip_ml=False, skip_synergy=False)
    steps = _get_pipeline_steps(args)
    assert steps == PIPELINE_STEPS
    assert len(steps) == 8


def test_get_pipeline_steps_full_adds_advanced_modules():
    from med_research.cli import PIPELINE_STEPS, PIPELINE_STEPS_FULL, _get_pipeline_steps

    args = SimpleNamespace(full=True, skip_trials=False, skip_ml=False, skip_synergy=False)
    steps = _get_pipeline_steps(args)
    assert len(steps) == len(PIPELINE_STEPS) + len(PIPELINE_STEPS_FULL)
    full_module_ids = {step[1] for step in PIPELINE_STEPS_FULL}
    assert full_module_ids.issubset({step[1] for step in steps})


def test_get_pipeline_steps_honors_skip_flags():
    from med_research.cli import _get_pipeline_steps

    args = SimpleNamespace(full=False, skip_trials=True, skip_ml=True, skip_synergy=True)
    module_ids = {step[1] for step in _get_pipeline_steps(args)}
    assert "clinical_trials" not in module_ids
    assert "ml_predictor" not in module_ids
    assert "drug_synergy" not in module_ids


def test_steps_to_parallel_modules_expands_bioinformatics():
    from med_research.cli import PIPELINE_STEPS, _steps_to_parallel_modules

    modules = _steps_to_parallel_modules(PIPELINE_STEPS)
    assert modules[0] == "knowledge_graph"
    assert "gwas" in modules
    assert "enrichment" in modules
    assert "ppi" in modules


def test_run_all_parallel_uses_scheduler(monkeypatch):
    """Parallel run-all dispatches through the DAG scheduler."""
    import med_research.cli as cli_mod
    from med_research.cli import cmd_run_all

    captured: dict[str, object] = {"parallel": None, "levels": None, "modules": []}

    def fake_validate(module_ids):
        captured["levels"] = [["knowledge_graph"], module_ids[1:]]
        return captured["levels"]

    def fake_run_levels(levels, runner, *, parallel, max_workers=None):
        captured["parallel"] = parallel
        for level in levels:
            for module_id in level:
                runner(module_id)
        return 0

    def fake_run_all_module(module_id, _args):
        captured["modules"].append(module_id)
        return 0

    monkeypatch.setattr(cli_mod, "_warn_config_gaps", lambda _d: False)
    monkeypatch.setattr(cli_mod, "_run_all_module", fake_run_all_module)
    monkeypatch.setattr("med_research.pipeline.scheduler.validate_dag", fake_validate)
    monkeypatch.setattr("med_research.pipeline.scheduler.run_levels", fake_run_levels)

    args = SimpleNamespace(
        disease="sle",
        parallel=True,
        sequential=False,
        full=False,
        skip_trials=False,
        skip_ml=False,
        skip_synergy=False,
        no_cache=False,
        export_html=False,
    )
    assert cmd_run_all(args) == 0
    assert captured["parallel"] is True
    assert captured["levels"] is not None
    assert "knowledge_graph" in captured["modules"]

