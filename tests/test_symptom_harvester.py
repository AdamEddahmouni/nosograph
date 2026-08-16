"""Tests for HPO / OT symptom harvesting."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from med_research.diseases.bulk_store import OpenTargetsBulkStore, manifest_path
from med_research.diseases.symptom_harvester import harvest_symptoms_for_disease

FIXTURES = Path(__file__).resolve().parent / "fixtures" / "opentargets" / "25.03"


@pytest.fixture(scope="module")
def store(tmp_path_factory) -> OpenTargetsBulkStore:
    tmp = tmp_path_factory.mktemp("symptom_bulk")
    bulk_root = tmp / "opentargets"
    version_dir = bulk_root / "25.03"
    import shutil

    if not FIXTURES.is_dir():
        from tests.fixtures.opentargets.build_fixtures import main as build

        build()
    shutil.copytree(FIXTURES, version_dir)
    manifest_path(bulk_root).parent.mkdir(parents=True, exist_ok=True)
    manifest_path(bulk_root).write_text(json.dumps({"version": "25.03"}), encoding="utf-8")
    return OpenTargetsBulkStore(bulk_root=bulk_root, version="25.03")


def test_harvest_symptoms_from_ot(tmp_path: Path, store: OpenTargetsBulkStore, monkeypatch) -> None:
    from med_research.diseases import scaffold as scaffold_mod

    diseases_root = tmp_path / "diseases"
    disease_dir = diseases_root / "ra_sym"
    disease_dir.mkdir(parents=True)
    config = disease_dir / "config.py"
    config.write_text(
        'PIPELINE_LABEL = "RA"\nSYMPTOMS = []\nPUBMED_QUERIES = []\n',
        encoding="utf-8",
    )
    monkeypatch.setattr(scaffold_mod, "_diseases_root", lambda: diseases_root)
    monkeypatch.setattr(
        "med_research.diseases.symptom_harvester.load_disease_registry",
        lambda *a, **k: [{"id": "ra_sym", "name": "Rheumatoid Arthritis", "efo_id": "EFO_0001370"}],
    )
    monkeypatch.setattr(
        "med_research.diseases.symptom_harvester._diseases_root",
        lambda: diseases_root,
    )

    result = harvest_symptoms_for_disease("ra_sym", store=store, write=True)
    assert result["symptoms"]
    assert "Arthritis" in result["symptoms"]
    text = config.read_text(encoding="utf-8")
    assert "Arthritis" in text
    assert "SYMPTOMS = []" not in text
