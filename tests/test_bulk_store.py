"""Tests for OpenTargetsBulkStore (offline fixture parquet)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from med_research.diseases.bulk_store import OpenTargetsBulkStore, manifest_path, normalize_efo

FIXTURES = Path(__file__).resolve().parent / "fixtures" / "opentargets"
FIXTURE_VERSION = FIXTURES / "25.03"


@pytest.fixture(scope="module")
def fixture_bulk_root(tmp_path_factory) -> Path:
    """Copy fixture parquet + manifest into an isolated temp bulk root."""
    tmp = tmp_path_factory.mktemp("bulk")
    bulk_root = tmp / "opentargets"
    version_dir = bulk_root / "25.03"
    import shutil

    if not FIXTURE_VERSION.is_dir():
        from tests.fixtures.opentargets.build_fixtures import main as build

        build()
    shutil.copytree(FIXTURE_VERSION, version_dir)
    manifest = {
        "version": "25.03",
        "source": "test_fixtures",
        "tables": ["disease", "association_overall_direct", "known_drug", "disease_phenotype"],
        "path": str(version_dir),
    }
    manifest_path(bulk_root).parent.mkdir(parents=True, exist_ok=True)
    manifest_path(bulk_root).write_text(json.dumps(manifest), encoding="utf-8")
    return bulk_root


@pytest.fixture
def store(fixture_bulk_root: Path) -> OpenTargetsBulkStore:
    return OpenTargetsBulkStore(bulk_root=fixture_bulk_root, version="25.03")


def test_is_available(store: OpenTargetsBulkStore) -> None:
    assert store.is_available()


def test_resolve_disease_by_name(store: OpenTargetsBulkStore) -> None:
    resolved = store.resolve_disease("Rheumatoid Arthritis")
    assert resolved is not None
    assert resolved.efo_id == "EFO_0001370"
    assert "Arthritis" in resolved.name


def test_get_targets(store: OpenTargetsBulkStore) -> None:
    targets = store.get_targets("EFO_0001370", limit=10)
    symbols = {t["symbol"] for t in targets}
    assert "TNF" in symbols
    assert "JAK2" in symbols
    assert all(t["score"] is not None for t in targets)


def test_get_drugs(store: OpenTargetsBulkStore) -> None:
    drugs = store.get_drugs("EFO_0001370", limit=10)
    names = {d["name"] for d in drugs}
    assert "Adalimumab" in names


def test_get_phenotypes(store: OpenTargetsBulkStore) -> None:
    phenotypes = store.get_phenotypes("EFO_0001370")
    assert "Arthritis" in phenotypes


def test_normalize_efo() -> None:
    assert normalize_efo("EFO:0001370") == "EFO_0001370"
    assert normalize_efo("EFO_0001370") == "EFO_0001370"
