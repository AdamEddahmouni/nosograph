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
