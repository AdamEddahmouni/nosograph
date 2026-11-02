"""Offline demo snapshot builder, manifest integrity, and DEMO_SNAPSHOT_PATH configuration."""

from __future__ import annotations

import importlib
import json
import shutil
import sqlite3
import subprocess
import sys
from pathlib import Path

import pytest

from med_research.demo.snapshot import (
    SUPPORTED_DISEASE_IDS,
    build_demo_snapshot,
    manifest_path_for,
)
from med_research.diseases.identifiers import CI_VALIDATED_DISEASES

REPO_ROOT = Path(__file__).resolve().parents[1]
FIXTURE_ROOT = REPO_ROOT / "tests" / "fixtures" / "biomed"
REQUIRED_TABLES = {
    "resource_snapshots",
    "active_snapshots",
    "entities",
    "entity_revisions",
    "claims",
    "claim_evidence",
}
REQUIRED_RESOURCES = ("mondo", "hp", "hpoa")

pytestmark = pytest.mark.unit


def _copy_fixtures(dest: Path) -> Path:
    shutil.copytree(FIXTURE_ROOT, dest, dirs_exist_ok=True)
    return dest


def _logical_snapshots(db_path: Path) -> list[tuple[str, str]]:
    with sqlite3.connect(db_path) as connection:
        rows = connection.execute(
            """
            SELECT a.resource_name, s.checksum
            FROM active_snapshots AS a
            JOIN resource_snapshots AS s ON s.id = a.snapshot_id
            ORDER BY a.resource_name
            """
        ).fetchall()
    return [(str(row[0]), str(row[1])) for row in rows]


def _table_names(db_path: Path) -> set[str]:
    with sqlite3.connect(db_path) as connection:
        rows = connection.execute("SELECT name FROM sqlite_master WHERE type = 'table'").fetchall()
    return {str(row[0]) for row in rows}


def _logical_manifest(path: Path) -> dict:
    payload = json.loads(path.read_text(encoding="utf-8"))
    payload.pop("generated_at", None)
    return payload


def test_fresh_snapshot_contains_required_tables_and_active_snapshots(tmp_path):
    output = tmp_path / "demo" / "biomedical.sqlite3"
    result = build_demo_snapshot(output, fixture_root=FIXTURE_ROOT)

    assert result == output
    assert output.is_file()
    tables = _table_names(output)
    assert REQUIRED_TABLES.issubset(tables)
    resources = {name for name, _checksum in _logical_snapshots(output)}
    assert set(REQUIRED_RESOURCES) <= resources


def test_manifest_lists_ci_validated_supported_disease_ids(tmp_path):
    output = tmp_path / "biomedical.sqlite3"
    build_demo_snapshot(output, fixture_root=FIXTURE_ROOT)
    manifest = json.loads(manifest_path_for(output).read_text(encoding="utf-8"))

    assert set(manifest["supported_disease_ids"]) == set(CI_VALIDATED_DISEASES)
    assert manifest["supported_disease_ids"] == list(SUPPORTED_DISEASE_IDS)
    assert "legacy_disease_ids" in manifest
    assert manifest["label"]


def test_manifest_includes_fixture_checksums_and_snapshot_metadata(tmp_path):
    output = tmp_path / "biomedical.sqlite3"
    build_demo_snapshot(output, fixture_root=FIXTURE_ROOT)
    manifest = json.loads(manifest_path_for(output).read_text(encoding="utf-8"))

    assert manifest["snapshot_version"]
    assert manifest["generated_at"]
    assert manifest["schema_version"]
    fixtures = {item["resource"]: item for item in manifest["fixtures"]}
    for resource in REQUIRED_RESOURCES:
        assert resource in fixtures
        assert fixtures[resource]["name"]
        assert fixtures[resource]["checksum"].startswith("sha256:")
    resources = {item["resource_name"]: item for item in manifest["resources"]}
    for resource in REQUIRED_RESOURCES:
        assert resources[resource]["checksum"].startswith("sha256:")


def test_second_build_is_deterministic_at_logical_level(tmp_path):
    first = tmp_path / "a" / "biomedical.sqlite3"
    second = tmp_path / "b" / "biomedical.sqlite3"
    build_demo_snapshot(first, fixture_root=FIXTURE_ROOT)
    build_demo_snapshot(second, fixture_root=FIXTURE_ROOT)

    assert _logical_snapshots(first) == _logical_snapshots(second)
    assert _logical_manifest(manifest_path_for(first)) == _logical_manifest(
        manifest_path_for(second)
    )


def test_missing_mondo_fixture_fails_clearly(tmp_path):
    fixtures = _copy_fixtures(tmp_path / "fixtures")
    (fixtures / "mondo" / "minimal.json").unlink()
    with pytest.raises(Exception, match=r"(?i)mondo") as excinfo:
        build_demo_snapshot(tmp_path / "biomedical.sqlite3", fixture_root=fixtures)
    assert "missing" in str(excinfo.value).lower()


def test_missing_hpo_fixture_fails_clearly(tmp_path):
    fixtures = _copy_fixtures(tmp_path / "fixtures")
    (fixtures / "hpo" / "minimal.json").unlink()
    with pytest.raises(Exception, match=r"(?i)(hpo|\bhp\b)") as excinfo:
        build_demo_snapshot(tmp_path / "biomedical.sqlite3", fixture_root=fixtures)
    assert "missing" in str(excinfo.value).lower()


def test_missing_hpoa_fixture_fails_clearly(tmp_path):
    fixtures = _copy_fixtures(tmp_path / "fixtures")
    (fixtures / "hpoa" / "minimal.tsv").unlink()
    with pytest.raises(Exception, match=r"(?i)hpoa") as excinfo:
        build_demo_snapshot(tmp_path / "biomedical.sqlite3", fixture_root=fixtures)
    assert "missing" in str(excinfo.value).lower()


def test_malformed_mondo_fixture_fails_clearly(tmp_path):
    fixtures = _copy_fixtures(tmp_path / "fixtures")
    (fixtures / "mondo" / "minimal.json").write_text("{not-json", encoding="utf-8")
    with pytest.raises(Exception, match=r"(?i)(invalid|malformed|json|mondo)"):
        build_demo_snapshot(tmp_path / "biomedical.sqlite3", fixture_root=fixtures)


def test_no_network_connector_is_invoked(tmp_path, monkeypatch):
    def boom(*_args, **_kwargs):
        raise AssertionError("network connector invoked")

    monkeypatch.setattr("urllib.request.urlopen", boom)
    monkeypatch.setattr("urllib.request.urlretrieve", boom)
    monkeypatch.setattr("med_research.pipeline.external.client.fetch_json", boom)

    build_demo_snapshot(tmp_path / "biomedical.sqlite3", fixture_root=FIXTURE_ROOT)


def test_demo_snapshot_path_default(monkeypatch):
    monkeypatch.delenv("DEMO_SNAPSHOT_PATH", raising=False)
    from med_research.web import config

    importlib.reload(config)
    try:
        assert Path("/app/demo-data/biomedical.sqlite3") == config.DEMO_SNAPSHOT_PATH
        assert Path("/app/demo-data/biomedical.sqlite3") == config.parse_demo_snapshot_path()
    finally:
        importlib.reload(config)


def test_demo_snapshot_path_parses_environment(monkeypatch):
    monkeypatch.setenv("DEMO_SNAPSHOT_PATH", "/tmp/custom-demo.sqlite3")
    from med_research.web import config

    importlib.reload(config)
    try:
        assert Path("/tmp/custom-demo.sqlite3") == config.DEMO_SNAPSHOT_PATH
        assert Path("/var/demo/biomedical.sqlite3") == config.parse_demo_snapshot_path(
            "/var/demo/biomedical.sqlite3"
        )
    finally:
        importlib.reload(config)


def test_output_is_limited_to_database_and_manifest(tmp_path):
    out_dir = tmp_path / "out"
    output = out_dir / "biomedical.sqlite3"
    build_demo_snapshot(output, fixture_root=FIXTURE_ROOT)
    created = sorted(path.name for path in out_dir.iterdir())
    assert created == ["biomedical.manifest.json", "biomedical.sqlite3"]


def test_demo_build_cli_subprocess(tmp_path: Path) -> None:
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


def test_demo_build_script_subprocess(tmp_path: Path) -> None:
    output = tmp_path / "script-demo.sqlite3"
    cmd = [
        sys.executable,
        str(REPO_ROOT / "scripts" / "build_demo_snapshot.py"),
        "--output",
        str(output),
        "--fixture-root",
        str(FIXTURE_ROOT),
    ]
    completed = subprocess.run(cmd, check=False, capture_output=True, text=True)
    assert completed.returncode == 0, completed.stderr
    assert output.is_file()
    assert manifest_path_for(output).is_file()
