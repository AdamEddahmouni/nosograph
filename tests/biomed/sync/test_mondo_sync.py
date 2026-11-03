"""Fixture-backed tests for the MONDO sync source.

No network, no live APIs: every case either uses the checked-in minimal OBO-JSON
fixture or builds a small artifact in ``tmp_path`` and exercises the sync
lifecycle directly.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from med_research.biomed.errors import BiomedicalValidationError
from med_research.biomed.models import MappingKind, Predicate
from med_research.biomed.sync import get_sync_source, list_sources
from med_research.biomed.sync.contracts import SyncSource
from med_research.biomed.sync.registry import (
    SOURCE_MATRIX,
    SYNCABLE_SOURCES,
    list_syncable_sources,
)
from med_research.biomed.sync.sources.mondo import MondoSyncSource

pytestmark = pytest.mark.unit

REPO_ROOT = Path(__file__).resolve().parents[3]
MONDO_FIXTURE = REPO_ROOT / "tests" / "fixtures" / "biomed" / "mondo" / "minimal.json"


def _minimal_payload(*, version: str = "2024-06-01") -> dict[str, Any]:
    """Small synthetic artifact; never a claim about real MONDO content."""
    return {
        "meta": {"version": version},
        "graphs": [
            {
                "nodes": [
                    {
                        "id": "http://purl.obolibrary.org/obo/MONDO_0000001",
                        "lbl": "synthetic disease",
                        "meta": {
                            "definition": {"val": "Synthetic fixture concept."},
                            "synonyms": [{"pred": "hasExactSynonym", "val": "SD"}],
                            "xrefs": [{"val": "OMIM:000001"}],
                        },
                    },
                    {
                        "id": "http://purl.obolibrary.org/obo/MONDO_0009001",
                        "lbl": "obsolete synthetic term",
                        "meta": {
                            "basicPropertyValues": [
                                {
                                    "pred": "http://www.geneontology.org/formats/oboInOwl#termReplacedBy",
                                    "val": "MONDO:0000001",
                                }
                            ]
                        },
                    },
                    {
                        "id": "http://purl.obolibrary.org/obo/MONDO_0000100",
                        "lbl": "synthetic parent disease",
                        "meta": {},
                    },
                ],
                "edges": [
                    {
                        "sub": "http://purl.obolibrary.org/obo/MONDO_0000001",
                        "pred": "is_a",
                        "obj": "http://purl.obolibrary.org/obo/MONDO_0000100",
                    }
                ],
                "meta": {"xrefs": []},
            }
        ],
    }


def _write_artifact(root: Path, payload: dict[str, Any], *, name: str = "mondo.json") -> Path:
    path = root / name
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return path


@pytest.fixture
def artifact(tmp_path: Path) -> Path:
    return _write_artifact(tmp_path, _minimal_payload())


# ---------------------------------------------------------------- protocol


def test_source_satisfies_sync_protocol(artifact: Path) -> None:
    source = MondoSyncSource(artifact_path=artifact)
    assert isinstance(source, SyncSource)
    assert source.source_id == "mondo"
    assert source.policy.resource_name == "mondo"
    assert source.policy.license_id == "CC-BY-4.0"
    assert source.policy.redistribution_policy != "restricted"


# ---------------------------------------------------------------- discovery


def test_discover_version_reads_artifact_meta_version() -> None:
    source = MondoSyncSource(artifact_path=MONDO_FIXTURE)
    assert source.discover_version(staging_root=MONDO_FIXTURE.parent) == "2024-01-01"


def test_discover_version_prefers_artifact_meta_over_operator_pin(artifact: Path) -> None:
    (artifact.parent / "VERSION").write_text("1999-01-01\n", encoding="utf-8")
    source = MondoSyncSource(artifact_path=artifact)
    # The artifact is the only source that can name a real upstream release.
    assert source.discover_version(staging_root=artifact.parent) == "2024-06-01"


def test_discover_version_falls_back_to_operator_pin(tmp_path: Path) -> None:
    payload = _minimal_payload()
    payload["meta"] = {}
    artifact = _write_artifact(tmp_path, payload)
    (tmp_path / "VERSION").write_text("2026-08-04\n", encoding="utf-8")
    source = MondoSyncSource(artifact_path=artifact)
    assert source.discover_version(staging_root=tmp_path) == "2026-08-04"


def test_discover_version_never_invents_a_release(tmp_path: Path) -> None:
    payload = _minimal_payload()
    payload["meta"] = {}
    artifact = _write_artifact(tmp_path, payload)
    source = MondoSyncSource(artifact_path=artifact)
    with pytest.raises(BiomedicalValidationError, match="no meta.version"):
        source.discover_version(staging_root=tmp_path)


def test_discover_version_without_artifact_names_expected_path(tmp_path: Path) -> None:
    missing = tmp_path / "missing.json"
    source = MondoSyncSource(artifact_path=missing)
    with pytest.raises(FileNotFoundError, match="MONDO artifact not found"):
        source.discover_version(staging_root=tmp_path)


# ------------------------------------------------------------------ staging


def test_dry_run_fetch_copies_nothing(artifact: Path, tmp_path: Path) -> None:
    staging = tmp_path / "staging"
    source = MondoSyncSource(artifact_path=artifact)
    root = source.fetch(staging_root=staging, version="v1", dry_run=True)
    assert root == artifact.parent
    assert not (staging / "v1").exists()


def test_publish_fetch_stages_artifact_and_pin(artifact: Path, tmp_path: Path) -> None:
    (artifact.parent / "VERSION").write_text("2024-06-01\n", encoding="utf-8")
    staging = tmp_path / "staging"
    source = MondoSyncSource(artifact_path=artifact)
    root = source.fetch(staging_root=staging, version="2024-06-01", dry_run=False)
    assert (root / "2024-06-01" / "mondo.json").is_file()
    pin = root / "2024-06-01" / "VERSION"
    assert pin.read_text(encoding="utf-8").strip() == "2024-06-01"


def test_missing_artifact_raises_file_not_found(tmp_path: Path) -> None:
    source = MondoSyncSource(artifact_path=tmp_path / "absent.json")
    with pytest.raises(FileNotFoundError, match="MONDO artifact not found"):
        source.fetch(staging_root=tmp_path / "staging", version="v1", dry_run=False)


# ------------------------------------------------------------- verification


def test_verify_returns_sha256_checksum(artifact: Path) -> None:
    source = MondoSyncSource(artifact_path=artifact)
    checksums = source.verify(artifact.parent)
    assert checksums["mondo.json"].startswith("sha256:")


def test_verify_accepts_a_matching_pinned_checksum(artifact: Path) -> None:
    checksum = MondoSyncSource(artifact_path=artifact).verify(artifact.parent)["mondo.json"]
    pinned = MondoSyncSource(artifact_path=artifact, expected_checksums=[checksum])
    assert pinned.verify(artifact.parent)["mondo.json"] == checksum


def test_verify_rejects_an_unpinned_checksum(artifact: Path) -> None:
    pinned = MondoSyncSource(artifact_path=artifact, expected_checksums=["sha256:" + "0" * 64])
    with pytest.raises(ValueError, match="does not match any pinned checksum"):
        pinned.verify(artifact.parent)


def test_verify_rejects_empty_root(tmp_path: Path) -> None:
    source = MondoSyncSource(artifact_path=tmp_path / "absent.json")
    with pytest.raises(ValueError, match="No MONDO artifact"):
        source.verify(tmp_path)


# ------------------------------------------------------------ normalization


def test_normalize_uses_published_xrefs_only() -> None:
    source = MondoSyncSource(artifact_path=MONDO_FIXTURE)
    bundle = source.normalize(MONDO_FIXTURE.parent, version="2024-01-01")

    assert bundle.entities
    assert all(entity.primary_curie.startswith("MONDO:") for entity in bundle.entities)
    assert all(len(entity.primary_curie) == len("MONDO:0007915") for entity in bundle.entities)

    objects = {mapping.object_curie for mapping in bundle.mappings}
    # Exactly the cross-references the artifact publishes — nothing inferred.
    # ``MONDO:0007915`` is published by the artifact too: it is the ``consider``
    # replacement target of the obsolete term, carried as a CLOSE mapping rather
    # than by collapsing the obsolete concept onto it.
    assert objects <= {"OMIM:152700", "DOID:9074", "OMIM:999999", "MONDO:0007915"}
    replacement = next(
        mapping for mapping in bundle.mappings if mapping.object_curie == "MONDO:0007915"
    )
    assert replacement.relation is MappingKind.CLOSE
    assert replacement.subject_curie == "MONDO:0000002"
    omim = next(mapping for mapping in bundle.mappings if mapping.object_curie == "OMIM:152700")
    assert omim.relation is MappingKind.EXACT
    doid = next(mapping for mapping in bundle.mappings if mapping.object_curie == "DOID:9074")
    assert doid.relation is MappingKind.CLOSE


def test_normalize_keeps_obsolete_concepts_without_collapsing_them() -> None:
    source = MondoSyncSource(artifact_path=MONDO_FIXTURE)
    bundle = source.normalize(MONDO_FIXTURE.parent, version="2024-01-01")

    curie_by_id = {entity.id: entity.primary_curie for entity in bundle.entities}
    obsolete = {
        curie_by_id[revision.entity_id]: revision
        for revision in bundle.revisions
        if revision.obsolete
    }
    assert "MONDO:0000002" in obsolete
    record = obsolete["MONDO:0000002"]
    assert record.replaced_by == "MONDO:0007915"
    assert record.consider == ["MONDO:0007915"]

    # The obsolete identifier is preserved as its own entity: no silent rewrite.
    assert "MONDO:0000002" in set(curie_by_id.values())

    summary = bundle.metadata
    assert summary["active_concepts"] == len(bundle.entities) - 1
    assert summary["obsolete_concepts"] == 1
    assert summary["obsolete_replacement_targets_missing"] == []


def test_normalize_summary_metadata_is_deterministic() -> None:
    source = MondoSyncSource(artifact_path=MONDO_FIXTURE)
    first = source.normalize(MONDO_FIXTURE.parent, version="2024-01-01")
    second = source.normalize(MONDO_FIXTURE.parent, version="2024-01-01")

    assert first.snapshot.checksum == second.snapshot.checksum
    assert first.metadata == second.metadata
    assert [claim.id for claim in first.claims] == [claim.id for claim in second.claims]
    assert [item.id for item in first.mappings] == [item.id for item in second.mappings]

    counts = first.metadata["xref_mapping_counts"]
    assert list(counts) == sorted(counts)
    assert sum(counts.values()) > 0


def test_normalize_flags_a_replacement_target_absent_from_the_artifact(tmp_path: Path) -> None:
    payload = _minimal_payload()
    payload["graphs"][0]["nodes"][1]["meta"]["basicPropertyValues"][0]["val"] = "MONDO:0099999"
    artifact = _write_artifact(tmp_path, payload)
    bundle = MondoSyncSource(artifact_path=artifact).normalize(tmp_path, version="2024-06-01")
    assert bundle.metadata["obsolete_replacement_targets_missing"] == ["MONDO:0099999"]


def test_normalize_records_obsolete_concepts_without_any_replacement(tmp_path: Path) -> None:
    payload = _minimal_payload()
    payload["graphs"][0]["nodes"][1]["meta"] = {}
    artifact = _write_artifact(tmp_path, payload)
    bundle = MondoSyncSource(artifact_path=artifact).normalize(tmp_path, version="2024-06-01")
    assert bundle.metadata["obsolete_concepts"] == 1
    assert bundle.metadata["obsolete_without_replacement"] == ["MONDO:0009001"]


def test_normalize_emits_is_a_claims_for_published_edges() -> None:
    source = MondoSyncSource(artifact_path=MONDO_FIXTURE)
    bundle = source.normalize(MONDO_FIXTURE.parent, version="2024-01-01")
    assert bundle.claims
    assert {claim.predicate for claim in bundle.claims} == {Predicate.IS_A}
    assert all(claim.subject_curie.startswith("MONDO:") for claim in bundle.claims)


def test_normalize_raises_on_artifact_without_nodes(tmp_path: Path) -> None:
    payload = _minimal_payload()
    payload["graphs"][0]["nodes"] = []
    payload["graphs"][0]["edges"] = []
    artifact = _write_artifact(tmp_path, payload)
    source = MondoSyncSource(artifact_path=artifact)
    with pytest.raises(BiomedicalValidationError, match="produced no condition entities"):
        source.normalize(tmp_path, version="2024-06-01")


def test_normalize_raises_on_artifact_without_graphs(tmp_path: Path) -> None:
    artifact = _write_artifact(tmp_path, {"meta": {"version": "2024-06-01"}, "graphs": []})
    source = MondoSyncSource(artifact_path=artifact)
    with pytest.raises(BiomedicalValidationError, match="contains no graphs"):
        source.normalize(tmp_path, version="2024-06-01")


def test_normalize_raises_when_no_artifact_is_present(tmp_path: Path) -> None:
    source = MondoSyncSource(artifact_path=tmp_path / "absent.json")
    with pytest.raises(FileNotFoundError, match="No MONDO artifact"):
        source.normalize(tmp_path, version="2024-06-01")


def test_normalize_accepts_mondo_mappings_without_consuming_them(tmp_path: Path) -> None:
    # MONDO is the source of these mappings; passing them must not change output.
    source = MondoSyncSource(artifact_path=MONDO_FIXTURE)
    plain = source.normalize(MONDO_FIXTURE.parent, version="2024-01-01")
    with_mappings = source.normalize(
        MONDO_FIXTURE.parent,
        version="2024-01-01",
        mondo_mappings={"EFO_0000001": "MONDO:0000001"},
    )
    assert plain.snapshot.checksum == with_mappings.snapshot.checksum
    assert plain.metadata == with_mappings.metadata


# ------------------------------------------------------------------- diff


def test_diff_is_byte_identical_across_runs() -> None:
    source = MondoSyncSource(artifact_path=MONDO_FIXTURE)
    bundle = source.normalize(MONDO_FIXTURE.parent, version="2024-01-01")
    first = source.diff(bundle, previous_checksum="sha256:older", previous_counts={"claims": 1})
    second = source.diff(bundle, previous_checksum="sha256:older", previous_counts={"claims": 1})
    assert json.dumps(first.model_dump(mode="json"), sort_keys=True) == json.dumps(
        second.model_dump(mode="json"), sort_keys=True
    )


def test_diff_detects_an_unchanged_artifact() -> None:
    source = MondoSyncSource(artifact_path=MONDO_FIXTURE)
    bundle = source.normalize(MONDO_FIXTURE.parent, version="2024-01-01")
    unchanged = source.diff(
        bundle, previous_checksum=bundle.snapshot.checksum, previous_counts=None
    )
    assert unchanged.changed is False
    assert unchanged.counts_delta == {}


def test_diff_reports_sorted_counts_delta() -> None:
    source = MondoSyncSource(artifact_path=MONDO_FIXTURE)
    bundle = source.normalize(MONDO_FIXTURE.parent, version="2024-01-01")
    diff = source.diff(bundle, previous_checksum="sha256:older", previous_counts={"claims": 0})
    assert diff.changed is True
    assert list(diff.counts_delta) == sorted(diff.counts_delta)
    assert diff.counts_delta["claims"] == bundle.counts.claims


# ------------------------------------------------------------- provenance


def test_provenance_records_source_identity() -> None:
    source = MondoSyncSource(artifact_path=MONDO_FIXTURE)
    bundle = source.normalize(MONDO_FIXTURE.parent, version="2024-01-01")
    provenance = source.build_provenance(
        bundle, stages_completed=["discover_version", "verify", "normalize"]
    )
    assert provenance.source_id == "mondo"
    assert provenance.resource_name == "mondo"
    assert provenance.importer_name == "MondoSyncSource"
    assert provenance.importer_version == MondoSyncSource.IMPORTER_VERSION
    assert provenance.upstream_version == "2024-01-01"
    assert provenance.checksum == bundle.snapshot.checksum
    assert provenance.snapshot_id == bundle.snapshot.id
    assert provenance.manifest_fingerprint


# ----------------------------------------------------------- registration


def test_sync_registration_includes_mondo() -> None:
    assert "mondo" in SYNCABLE_SOURCES
    assert list_syncable_sources() == sorted(SYNCABLE_SOURCES)
    assert "mondo" in list_sources()
    assert get_sync_source("mondo").source_id == "mondo"

    row = next(entry for entry in SOURCE_MATRIX if entry.source == "mondo")
    assert "MondoSyncSource" in row.adapter
    assert row.tests == "tests/biomed/sync/test_mondo_sync.py"


def test_declared_inventory_matches_registered_sources() -> None:
    from med_research.biomed.sync.lifecycle import _SYNC_SOURCES

    assert set(SYNCABLE_SOURCES) == set(_SYNC_SOURCES)


# --------------------------------------------------------------- service


def test_sync_service_dry_run_completes_for_mondo(repository, tmp_path: Path) -> None:
    from med_research.biomed.sync.lifecycle import SyncService
    from med_research.biomed.sync.models import SyncStage

    service = SyncService(repository, staging_root=tmp_path / "staging")
    report = service.run("mondo", dry_run=True, publish=False)

    assert report.succeeded, report.error
    stages = [item.stage for item in report.stages]
    assert SyncStage.DISCOVER_VERSION in stages
    assert SyncStage.VERIFY in stages
    assert SyncStage.NORMALIZE in stages
    assert SyncStage.DIFF in stages
    assert report.provenance is not None
    assert report.provenance.source_id == "mondo"
