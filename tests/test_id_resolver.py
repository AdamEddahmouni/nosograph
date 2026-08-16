"""Tests for disease ID resolution cascade."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from med_research.diseases.bulk_store import OpenTargetsBulkStore, manifest_path
from med_research.diseases.id_resolver import DiseaseIdResolver, ResolutionResult

FIXTURES = Path(__file__).resolve().parent / "fixtures" / "opentargets" / "25.03"


@pytest.fixture(scope="module")
def resolver(tmp_path_factory) -> DiseaseIdResolver:
    tmp = tmp_path_factory.mktemp("bulk_resolver")
    bulk_root = tmp / "opentargets"
    version_dir = bulk_root / "25.03"
    import shutil

    if not FIXTURES.is_dir():
        from tests.fixtures.opentargets.build_fixtures import main as build

        build()
    shutil.copytree(FIXTURES, version_dir)
    manifest_path(bulk_root).parent.mkdir(parents=True, exist_ok=True)
    manifest_path(bulk_root).write_text(
        json.dumps({"version": "25.03", "source": "test"}),
        encoding="utf-8",
    )
    store = OpenTargetsBulkStore(bulk_root=bulk_root, version="25.03")
    return DiseaseIdResolver(bulk_store=store, biomed_db=tmp / "missing.sqlite")


def test_registry_efo_passthrough(resolver: DiseaseIdResolver) -> None:
    result = resolver.resolve_entry(
        {"id": "ra", "name": "Rheumatoid Arthritis", "efo_id": "EFO_0001370"}
    )
    assert result.efo_id == "EFO_0001370"
    assert result.resolution_source == "registry_efo"
    assert not result.needs_review


def test_ot_disease_exact_match(resolver: DiseaseIdResolver) -> None:
    result = resolver.resolve_entry({"id": "crohns", "name": "Crohn disease"})
    assert result.efo_id == "EFO_0000384"
    assert result.resolution_confidence >= 0.9
    assert result.resolution_source == "ot_disease_exact"


def test_failed_resolution(resolver: DiseaseIdResolver) -> None:
    result = resolver.resolve_entry(
        {"id": "unknown_xyz", "name": "Completely Unknown Syndrome XYZ"}
    )
    assert result.efo_id is None
    assert result.resolution_source == "failed"


def test_mondo_ot_id_fallback(tmp_path) -> None:
    """Diseases without EFO xrefs should resolve to MONDO OT ids."""
    store = OpenTargetsBulkStore(bulk_root=tmp_path / "missing")
    resolver = DiseaseIdResolver(bulk_store=store, biomed_db=tmp_path / "missing.sqlite")
    resolver._mondo_labels = [("MONDO:0021722", "vulvodynia")]
    result = resolver.resolve_entry({"id": "vulvodynia", "name": "Vulvodynia"})
    assert result.efo_id == "MONDO_0021722"
    assert result.mondo_id == "MONDO:0021722"
    assert result.resolution_source == "mondo_ot_id"
    assert not result.needs_review


def test_build_report(resolver: DiseaseIdResolver) -> None:
    results = [
        ResolutionResult(
            "a", "A", efo_id="EFO_0001370", resolution_confidence=1.0, needs_review=False
        ),
        ResolutionResult("b", "B"),
    ]
    report = resolver.build_report(results)
    assert report["total"] == 2
    assert report["resolved"] == 1
    assert report["failed"] == 1
