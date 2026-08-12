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


def test_biomed_import_mondo_from_fixture(tmp_path: Path) -> None:
    db = tmp_path / "biomedical.sqlite3"
    artifact = Path("tests/fixtures/biomed/mondo/minimal.json")
    result = run_cli("biomed", "import", "mondo", "--artifact", str(artifact), "--db", str(db))
    assert result.exit_code == 0
    assert "MONDO:0007915" in result.output


def test_biomed_snapshots_list_after_import(tmp_path: Path) -> None:
    db = tmp_path / "biomedical.sqlite3"
    artifact = Path("tests/fixtures/biomed/mondo/minimal.json")
    run_cli("biomed", "import", "mondo", "--artifact", str(artifact), "--db", str(db))
    result = run_cli("biomed", "snapshots", "list", "--db", str(db))
    assert result.exit_code == 0
    assert "mondo" in result.output
    assert "active" in result.output


def test_biomed_parser_requires_action() -> None:
    with pytest.raises(SystemExit):
        _build_parser().parse_args(["biomed"])
