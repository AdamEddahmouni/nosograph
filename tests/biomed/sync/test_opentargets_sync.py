from __future__ import annotations

import uuid
from pathlib import Path

import pytest

from med_research.biomed.imports.mondo import MondoAdapter
from med_research.biomed.imports.opentargets_adapter import OpenTargetsImportAdapter
from med_research.biomed.imports.service import ImportService
from med_research.biomed.models import ResourcePolicy
from med_research.biomed.repository import BiomedicalRepository
from med_research.biomed.sync import SyncService
from med_research.biomed.sync.models import SyncStage, SyncStatus

FIXTURES = Path("tests/fixtures/biomed")
OT_FIXTURES = Path("tests/fixtures/opentargets")


@pytest.fixture(scope="module", autouse=True)
def _build_ot_fixtures() -> None:
    import runpy

    runpy.run_path(str(OT_FIXTURES / "build_fixtures.py"), run_name="__main__")


@pytest.fixture
def sync_repository(tmp_path) -> BiomedicalRepository:
    from med_research.biomed.identifiers import mapping_uuid
    from med_research.biomed.models import MappingKind

    repository = BiomedicalRepository(tmp_path / "biomedical.sqlite3")
    repository.initialize()
    service = ImportService(repository)
    policy = ResourcePolicy(
        resource_name="mondo",
        license_id="CC-BY-4.0",
        license_url="https://creativecommons.org/licenses/by/4.0/",
        redistribution_policy="redistributable",
    )
    bundle = MondoAdapter().parse(FIXTURES / "mondo" / "minimal.json", policy=policy)
    service.import_bundle(bundle)
    mapping_id = mapping_uuid("MONDO:0007915", "EFO:0001370", MappingKind.EXACT, bundle.snapshot.id)
    with repository.database.connect() as connection:
        connection.execute(
            """
            INSERT INTO entity_mappings (id, subject_curie, object_curie, relation, snapshot_id, source_record_id)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                str(mapping_id),
                "MONDO:0007915",
                "EFO:0001370",
                "exact",
                str(bundle.snapshot.id),
                "test:EFO_0001370",
            ),
        )
        connection.commit()
    return repository


def test_opentargets_adapter_is_deterministic(sync_repository) -> None:
    adapter = OpenTargetsImportAdapter()
    policy = ResourcePolicy(
        resource_name="open_targets",
        license_id="Open-Targets-data",
        license_url="https://platform.opentargets.org/downloads",
        redistribution_policy="user_supplied",
    )
    mappings = {"EFO_0001370": "MONDO:0007915"}
    first = adapter.parse_bulk(
        OT_FIXTURES,
        policy,
        version="25.03",
        mondo_mappings=mappings,
    )
    second = adapter.parse_bulk(
        OT_FIXTURES,
        policy,
        version="25.03",
        mondo_mappings=mappings,
    )
    assert first.snapshot.checksum == second.snapshot.checksum
    assert first.counts.claims == second.counts.claims
    assert first.counts.evidence == second.counts.evidence
    assert first.counts.claims > 0


def test_snapshot_id_is_typed_as_uuid() -> None:
    from med_research.biomed.imports.opentargets_adapter import _snapshot_id

    value = _snapshot_id("open_targets", "25.03", "sha256:fixture")
    assert isinstance(value, uuid.UUID)
    assert value == _snapshot_id("open_targets", "25.03", "sha256:fixture")


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        (3, 3),
        (0, 0),
        ("2", 2),
        (" 1 ", 1),
        (None, None),
        (True, None),
        (False, None),
        ("Phase 3", None),
        ("N/A", None),
        ("", None),
        (object(), None),
    ],
)
def test_normalize_phase_handles_integer_numeric_and_invalid_values(raw, expected) -> None:
    from med_research.biomed.imports.opentargets_adapter import _normalize_phase

    result = _normalize_phase(raw)
    assert result == expected
    assert (result is None) == (expected is None)


def test_sync_lifecycle_dry_run_records_all_stages(sync_repository) -> None:
    service = SyncService(sync_repository, staging_root=Path("data/bulk/sync-test"))
    report = service.run("open_targets", dry_run=True, publish=False)
    assert report.succeeded
    stage_names = [item.stage for item in report.stages]
    assert SyncStage.DISCOVER_VERSION in stage_names
    assert SyncStage.VERIFY in stage_names
    assert SyncStage.NORMALIZE in stage_names
    assert SyncStage.DIFF in stage_names
    assert report.provenance is not None
    assert report.provenance.manifest_fingerprint


def test_sync_publish_creates_active_snapshot(sync_repository) -> None:
    service = SyncService(sync_repository, staging_root=Path("data/bulk/sync-test"))
    report = service.run("open_targets", dry_run=False, publish=True)
    assert report.status is SyncStatus.COMPLETED
    snapshot = sync_repository.get_active_snapshot("open_targets")
    assert snapshot is not None
    assert snapshot.checksum == report.diff.current_checksum if report.diff else True
