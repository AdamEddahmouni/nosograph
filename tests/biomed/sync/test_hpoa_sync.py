"""Fixture-backed tests for the HPOA sync source.

No network, no live APIs: every case builds a small operator-supplied TSV in a
temporary directory and exercises the sync lifecycle directly.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from med_research.biomed.models import EvidenceDirection, Predicate
from med_research.biomed.sync import get_sync_source, list_sources
from med_research.biomed.sync.contracts import SyncSource
from med_research.biomed.sync.registry import SOURCE_MATRIX, list_syncable_sources
from med_research.biomed.sync.sources.hpoa import HpoaSyncSource

pytestmark = pytest.mark.unit

HEADER = (
    "ncbi_taxon_id\tdisease_id\tdisease_name\tqualifier\thp_id\thp_name\t"
    "frequency\tonset\tmodifier\tevidence\tsex\tbiocuration\n"
)

# Row 1: mapped, positive. Row 2: mapped, NOT-qualified. Row 3: unmapped disease.
# Row 4: missing hp_id (skipped with a warning, never silently dropped).
ROWS = [
    (
        "9606\tOMIM:152700\tSystemic lupus erythematosus\t\tHP:0001945\tFever\t"
        "Very frequent\tAdult\t\tIEA\t\tORCID:0000-0001-2345-6789"
    ),
    (
        "9606\tOMIM:152700\tSystemic lupus erythematosus\tNOT\tHP:0001873\t"
        "Thrombocytopenia\tOccasional\tAdult\t\tIEA\t\tORCID:0000-0001-2345-6789"
    ),
    (
        "9606\tOMIM:999999\tUnknown disease\t\tHP:0001945\tFever\t"
        "Frequent\t\tIEA\t\tORCID:0000-0001-2345-6789"
    ),
    (
        "9606\tOMIM:152700\tSystemic lupus erythematosus\t\t\tMissing phenotype\t"
        "Frequent\t\tIEA\t\tORCID:0000-0001-2345-6789"
    ),
]

MONDO_MAPPINGS = {"OMIM:152700": "MONDO:0007915"}


@pytest.fixture
def artifact(tmp_path: Path) -> Path:
    path = tmp_path / "hpoa.tsv"
    path.write_text(HEADER + "\n".join(ROWS) + "\n", encoding="utf-8")
    return path


def test_source_satisfies_sync_protocol(artifact: Path) -> None:
    source = HpoaSyncSource(artifact_path=artifact)
    assert isinstance(source, SyncSource)
    assert source.policy.resource_name == "hpoa"
    assert source.policy.license_id == "HPO-custom"
    assert source.policy.redistribution_policy == "user_supplied"


def test_discover_version_prefers_operator_pin(artifact: Path) -> None:
    (artifact.parent / "VERSION").write_text("2026-08-01\n", encoding="utf-8")
    source = HpoaSyncSource(artifact_path=artifact)
    assert source.discover_version(staging_root=artifact.parent) == "2026-08-01"


def test_discover_version_falls_back_to_artifact_mtime(artifact: Path) -> None:
    source = HpoaSyncSource(artifact_path=artifact)
    version = source.discover_version(staging_root=artifact.parent)
    assert version == f"mtime-{artifact.stat().st_mtime_ns}"
    assert not version.startswith("v")


def test_discover_version_without_artifact_names_expected_path(tmp_path: Path) -> None:
    missing = tmp_path / "missing.tsv"
    source = HpoaSyncSource(artifact_path=missing)
    with pytest.raises(FileNotFoundError, match="HPOA artifact not found"):
        source.discover_version(staging_root=tmp_path)


def test_dry_run_fetch_copies_nothing(artifact: Path, tmp_path: Path) -> None:
    staging = tmp_path / "staging"
    source = HpoaSyncSource(artifact_path=artifact)
    root = source.fetch(staging_root=staging, version="v1", dry_run=True)
    assert root == artifact.parent
    assert not (staging / "v1").exists()


def test_publish_fetch_stages_artifact_and_pin(artifact: Path, tmp_path: Path) -> None:
    (artifact.parent / "VERSION").write_text("2026-08-01\n", encoding="utf-8")
    staging = tmp_path / "staging"
    source = HpoaSyncSource(artifact_path=artifact)
    root = source.fetch(staging_root=staging, version="2026-08-01", dry_run=False)
    assert (root / "2026-08-01" / "hpoa.tsv").is_file()
    pin = root / "2026-08-01" / "VERSION"
    assert pin.read_text(encoding="utf-8").strip() == "2026-08-01"


def test_missing_artifact_raises_file_not_found(tmp_path: Path) -> None:
    source = HpoaSyncSource(artifact_path=tmp_path / "absent.tsv")
    with pytest.raises(FileNotFoundError, match="HPOA artifact not found"):
        source.fetch(staging_root=tmp_path / "staging", version="v1", dry_run=False)


def test_verify_returns_checksums(artifact: Path) -> None:
    source = HpoaSyncSource(artifact_path=artifact)
    checksums = source.verify(artifact.parent)
    assert checksums["hpoa.tsv"].startswith("sha256:")


def test_verify_rejects_empty_root(tmp_path: Path) -> None:
    source = HpoaSyncSource(artifact_path=tmp_path / "absent.tsv")
    with pytest.raises(ValueError, match="No HPOA artifact"):
        source.verify(tmp_path)


def test_normalize_preserves_direction_and_warnings(artifact: Path) -> None:
    source = HpoaSyncSource(artifact_path=artifact)
    bundle = source.normalize(artifact.parent, version="v1", mondo_mappings=MONDO_MAPPINGS)

    claims = [claim for claim in bundle.claims if claim.predicate == Predicate.HAS_PHENOTYPE]
    assert claims
    assert {claim.subject_curie for claim in claims} == {"MONDO:0007915"}
    directions = {evidence.direction for evidence in bundle.evidence}
    assert EvidenceDirection.SUPPORTING in directions
    assert EvidenceDirection.CONTRADICTORY in directions

    codes = {warning.code for warning in bundle.warnings}
    assert "unresolved_disease_mapping" in codes
    assert "skipped_row" in codes
    # An unmapped disease must never become a fabricated claim subject.
    assert all(claim.subject_curie != "OMIM:999999" for claim in claims)


def test_normalize_is_deterministic(artifact: Path) -> None:
    source = HpoaSyncSource(artifact_path=artifact)
    first = source.normalize(artifact.parent, version="v1", mondo_mappings=MONDO_MAPPINGS)
    second = source.normalize(artifact.parent, version="v1", mondo_mappings=MONDO_MAPPINGS)
    assert first.snapshot.checksum == second.snapshot.checksum
    assert [claim.id for claim in first.claims] == [claim.id for claim in second.claims]
    assert [item.id for item in first.evidence] == [item.id for item in second.evidence]


def test_provenance_records_source_identity(artifact: Path) -> None:
    source = HpoaSyncSource(artifact_path=artifact)
    bundle = source.normalize(artifact.parent, version="v1", mondo_mappings=MONDO_MAPPINGS)
    provenance = source.build_provenance(
        bundle, stages_completed=["discover_version", "verify", "normalize"]
    )
    assert provenance.source_id == "hpoa"
    assert provenance.resource_name == "hpoa"
    assert provenance.importer_name == "HpoaSyncSource"
    assert provenance.importer_version == "1.0.0"
    assert provenance.checksum == bundle.snapshot.checksum
    assert provenance.manifest_fingerprint


def test_diff_detects_checksum_change(artifact: Path) -> None:
    source = HpoaSyncSource(artifact_path=artifact)
    bundle = source.normalize(artifact.parent, version="v1", mondo_mappings=MONDO_MAPPINGS)

    unchanged = source.diff(
        bundle, previous_checksum=bundle.snapshot.checksum, previous_counts=None
    )
    assert unchanged.changed is False

    changed = source.diff(bundle, previous_checksum="sha256:older", previous_counts={"claims": 0})
    assert changed.changed is True
    assert changed.counts_delta["claims"] == bundle.counts.claims


def test_sync_registration_includes_hpoa() -> None:
    assert list_syncable_sources() == ["hpoa", "mondo", "open_targets"]
    assert list_sources() == ["hpoa", "mondo", "open_targets"]
    assert get_sync_source("hpoa").source_id == "hpoa"

    row = next(entry for entry in SOURCE_MATRIX if entry.source == "hpoa")
    assert "HpoaSyncSource" in row.adapter
    assert row.tests == "tests/biomed/sync/test_hpoa_sync.py"


def test_sync_service_dry_run_completes(repository, tmp_path: Path) -> None:
    from med_research.biomed.sync.lifecycle import SyncService
    from med_research.biomed.sync.models import SyncStage

    service = SyncService(repository, staging_root=tmp_path / "staging")
    report = service.run("hpoa", dry_run=True, publish=False)

    assert report.succeeded, report.error
    stages = [item.stage for item in report.stages]
    assert SyncStage.DISCOVER_VERSION in stages
    assert SyncStage.VERIFY in stages
    assert SyncStage.NORMALIZE in stages
    assert SyncStage.DIFF in stages
    assert report.provenance is not None
    assert report.provenance.source_id == "hpoa"
