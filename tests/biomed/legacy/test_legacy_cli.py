from __future__ import annotations

import io
import json
from contextlib import redirect_stdout
from dataclasses import dataclass
from pathlib import Path

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


def init_cli_db(db: Path) -> None:
    result = run_cli("biomed", "init", "--db", str(db))
    assert result.exit_code == 0


def import_mondo_fixture(db: Path) -> None:
    artifact = Path("tests/fixtures/biomed/mondo/minimal.json")
    result = run_cli("biomed", "import", "mondo", "--artifact", str(artifact), "--db", str(db))
    assert result.exit_code == 0


def test_biomed_migrate_legacy_imports_and_writes_report(tmp_path: Path) -> None:
    db = tmp_path / "biomedical.sqlite3"
    report = tmp_path / "parity.json"
    init_cli_db(db)
    import_mondo_fixture(db)
    result = run_cli("biomed", "migrate", "legacy", "--db", str(db), "--report", str(report))
    assert result.exit_code == 0
    assert report.exists()
    payload = json.loads(report.read_text(encoding="utf-8"))
    assert payload["resource_name"] == "legacy-curated"
    assert len(payload["diseases"]) == 7
