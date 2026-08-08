"""Helpers for invoking CLI handlers without subprocesses."""

from __future__ import annotations

import io
from contextlib import redirect_stdout
from typing import Any

import pytest

from med_research.cli import _build_parser


def parse_cli_args(*argv: str) -> Any:
    """Parse CLI arguments using the real argparse tree."""
    return _build_parser().parse_args(list(argv))


def cli_help_output(*argv: str) -> str:
    """Capture ``--help`` output from argparse."""
    parser = _build_parser()
    buf = io.StringIO()
    with pytest.raises(SystemExit) as exc, redirect_stdout(buf):
        parser.parse_args(list(argv))
    assert exc.value.code == 0
    return buf.getvalue()


def run_cli_handler(handler, *argv: str) -> int:
    """Invoke a ``cmd_*`` handler with parsed CLI arguments."""
    return handler(parse_cli_args(*argv))


def run_run_all_cli(*argv: str) -> int:
    """Invoke ``cmd_run_all`` with parsed ``run-all`` arguments."""
    from med_research.cli import cmd_run_all

    return run_cli_handler(cmd_run_all, "run-all", *argv)


def run_cli_command(*argv: str) -> int:
    """Dispatch a top-level CLI command through registered handlers."""
    from med_research.cli import (
        cmd_bioinformatics,
        cmd_biomarker,
        cmd_cache,
        cmd_cart,
        cmd_cross_disease,
        cmd_disease,
        cmd_diseases,
        cmd_evidence,
        cmd_expression,
        cmd_extractor,
        cmd_kg,
        cmd_literature,
        cmd_ml,
        cmd_modules,
        cmd_monitor,
        cmd_network,
        cmd_repurpose,
        cmd_run_all,
        cmd_safety,
        cmd_screening,
        cmd_semantic,
        cmd_serve,
        cmd_synergy,
        cmd_test,
        cmd_trials,
        cmd_workspace,
    )

    args = parse_cli_args(*argv)
    handlers = {
        "diseases": cmd_diseases,
        "modules": cmd_modules,
        "disease": cmd_disease,
        "kg": cmd_kg,
        "repurpose": cmd_repurpose,
        "bioinformatics": cmd_bioinformatics,
        "literature": cmd_literature,
        "screening": cmd_screening,
        "trials": cmd_trials,
        "ml": cmd_ml,
        "synergy": cmd_synergy,
        "safety": cmd_safety,
        "network": cmd_network,
        "expression": cmd_expression,
        "cart": cmd_cart,
        "biomarker": cmd_biomarker,
        "workspace": cmd_workspace,
        "semantic": cmd_semantic,
        "evidence": cmd_evidence,
        "extractor": cmd_extractor,
        "monitor": cmd_monitor,
        "cross-disease": cmd_cross_disease,
        "run-all": cmd_run_all,
        "serve": cmd_serve,
        "test": cmd_test,
        "cache": cmd_cache,
    }
    handler = handlers.get(args.command)
    if handler is None:
        raise ValueError(f"Unsupported CLI command for tests: {args.command}")
    return handler(args)


def run_cli_command_capture(*argv: str) -> tuple[int, str]:
    """Dispatch a CLI command and return ``(exit_code, combined_output)``."""
    stdout = io.StringIO()
    with redirect_stdout(stdout):
        exit_code = run_cli_command(*argv)
    return exit_code, stdout.getvalue()
