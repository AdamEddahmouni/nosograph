from __future__ import annotations

import io
from contextlib import redirect_stdout
from dataclasses import dataclass
from pathlib import Path

import pytest

from med_research.cli import _build_parser, cmd_biomed


@dataclass
class CliResult:
    exit_code: int
    output: str


def run_cli(*argv: str) -> CliResult:
    parser = _build_parser()
    stdout = io.StringIO()
    with redirect_stdout(stdout):
        args = parser.parse_args(list(argv))
        exit_code = cmd_biomed(args)
    return CliResult(exit_code=exit_code, output=stdout.getvalue())


def test_biomed_init_creates_store(tmp_path: Path) -> None:
    database = tmp_path / "biomedical.sqlite3"
    result = run_cli("biomed", "init", "--db", str(database))
    assert result.exit_code == 0
    assert database.exists()
    assert "schema version 1" in result.output.lower()


def test_biomed_parser_requires_action() -> None:
    with pytest.raises(SystemExit):
        _build_parser().parse_args(["biomed"])
