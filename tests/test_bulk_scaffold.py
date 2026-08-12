"""Tests for parallel bulk scaffolding."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from med_research.diseases.bulk_scaffold import collect_sources_from_bulk
from med_research.diseases.bulk_store import OpenTargetsBulkStore, manifest_path

FIXTURES = Path(__file__).resolve().parent / "fixtures" / "opentargets" / "25.03"


@pytest.fixture(scope="module")
def store(tmp_path_factory) -> OpenTargetsBulkStore:
  tmp = tmp_path_factory.mktemp("bulk_scaffold")
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


def test_collect_sources_from_bulk(store: OpenTargetsBulkStore) -> None:
  sources = collect_sources_from_bulk(
    store,
    disease_id="ra_test",
    name="Rheumatoid Arthritis",
    use_reactome=False,
  )
  assert sources["efo_id"] == "EFO_0001370"
  assert len(sources["genes"]["genes"]) >= 3
  assert len(sources["drugs"]["drugs"]) >= 1
  assert sources["ot_targets"]


def test_bulk_harvest_workers_one(tmp_path: Path, store: OpenTargetsBulkStore, monkeypatch) -> None:
  from med_research.diseases import scaffold as scaffold_mod
  from med_research.diseases.bulk_scaffold import bulk_harvest

  diseases_root = tmp_path / "diseases"
  diseases_root.mkdir()
  monkeypatch.setattr(scaffold_mod, "_diseases_root", lambda: diseases_root)

  registry = tmp_path / "registry.json"
  registry.write_text(
    json.dumps(
      {
        "diseases": [
          {"id": "ra_bulk", "name": "Rheumatoid Arthritis", "category": "autoimmune"},
        ]
      }
    ),
    encoding="utf-8",
  )

  monkeypatch.setattr(
    "med_research.diseases.bulk_scaffold.OpenTargetsBulkStore",
    lambda *a, **k: store,
  )

  report = bulk_harvest(
    workers=1,
    registry_path=registry,
    use_reactome=False,
  )
  assert report["total"] == 1
  assert len(report["succeeded"]) == 1
  module = diseases_root / "ra_bulk"
  assert (module / "data" / "genes.json").is_file()
