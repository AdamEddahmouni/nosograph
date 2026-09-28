"""Smoke tests for the fixture-backed local demo snapshot builder."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from med_research.demo.snapshot import (
    SUPPORTED_DISEASE_IDS,
    build_demo_snapshot,
    manifest_path_for,
)
from med_research.diseases.identifiers import CI_VALIDATED_DISEASES

pytestmark = pytest.mark.unit


def test_build_demo_snapshot_writes_db_and_manifest(tmp_path: Path) -> None:
    output = tmp_path / "biomedical.sqlite3"
    written = build_demo_snapshot(output)
    assert written == output
    assert output.is_file()
    manifest = manifest_path_for(output)
    assert manifest.is_file()
    payload = json.loads(manifest.read_text(encoding="utf-8"))
    assert set(payload["supported_disease_ids"]) == set(CI_VALIDATED_DISEASES)
    assert payload["supported_disease_ids"] == list(SUPPORTED_DISEASE_IDS)
    assert "legacy_disease_ids" in payload
    assert payload["label"]


def test_demo_cli_build_subprocess(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    import subprocess
    import sys

    output = tmp_path / "demo.sqlite3"
    cmd = [
        sys.executable,
        "-m",
        "med_research.cli",
        "demo",
        "build",
        "--output",
        str(output),
    ]
    completed = subprocess.run(cmd, check=False, capture_output=True, text=True)
    assert completed.returncode == 0, completed.stderr
    assert output.is_file()
