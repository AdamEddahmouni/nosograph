"""CLI tests for ClinVar and openFDA biomed import."""

from __future__ import annotations

from pathlib import Path

from tests.biomed.imports.test_import_cli import run_cli


def test_biomed_import_clinvar_from_fixture(tmp_path: Path) -> None:
    db = tmp_path / "biomedical.sqlite3"
    run_cli("biomed", "init", "--db", str(db))
    artifact = Path("tests/fixtures/biomed/clinvar/minimal.json")
    result = run_cli("biomed", "import", "clinvar", "--artifact", str(artifact), "--db", str(db))
    assert result.exit_code == 0
    assert "clinvar" in result.output.lower()


def test_biomed_import_openfda_from_fixture(tmp_path: Path) -> None:
    db = tmp_path / "biomedical.sqlite3"
    run_cli("biomed", "init", "--db", str(db))
    artifact = Path("tests/fixtures/biomed/openfda/minimal.json")
    result = run_cli("biomed", "import", "openfda", "--artifact", str(artifact), "--db", str(db))
    assert result.exit_code == 0
    assert "openfda" in result.output.lower()
