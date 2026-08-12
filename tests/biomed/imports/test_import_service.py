from __future__ import annotations

import pytest

from med_research.biomed.errors import BiomedicalValidationError, SnapshotConflictError
from med_research.biomed.imports.service import ImportService


def test_import_is_idempotent_and_activates_snapshot(repository, mondo_bundle) -> None:
    service = ImportService(repository)
    first = service.import_bundle(mondo_bundle)
    second = service.import_bundle(mondo_bundle)
    assert first.snapshot_id == second.snapshot_id
    assert repository.get_active_snapshot("mondo") is not None


def test_checksum_conflict_rolls_back(repository, mondo_bundle, tmp_path) -> None:
    service = ImportService(repository)
    service.import_bundle(mondo_bundle)
    tampered = mondo_bundle.model_copy(
        update={"snapshot": mondo_bundle.snapshot.model_copy(update={"checksum": "deadbeef"})}
    )
    with pytest.raises(SnapshotConflictError):
        service.import_bundle(tampered)
    assert repository.get_active_snapshot("mondo").checksum == mondo_bundle.snapshot.checksum


def test_failed_validation_leaves_previous_active_snapshot(
    repository, mondo_bundle, monkeypatch
) -> None:
    service = ImportService(repository)
    service.import_bundle(mondo_bundle)
    monkeypatch.setattr(
        service,
        "_validate_bundle",
        lambda _b: (_ for _ in ()).throw(BiomedicalValidationError("bad")),
    )
    with pytest.raises(BiomedicalValidationError):
        service.import_bundle(mondo_bundle)
    assert repository.get_active_snapshot("mondo") is not None
