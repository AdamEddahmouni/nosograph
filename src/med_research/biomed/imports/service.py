"""Atomic import service for biomedical ontology bundles."""

from __future__ import annotations

import time
from typing import TYPE_CHECKING

from med_research.biomed.errors import BiomedicalValidationError
from med_research.biomed.imports.models import ImportBundle, ImportReport
from med_research.biomed.models import ResourceSnapshot
from med_research.logging_config import get_logger

if TYPE_CHECKING:
    from med_research.biomed.repository import BiomedicalRepository

logger = get_logger(__name__)


class ImportService:
    def __init__(self, repository: BiomedicalRepository) -> None:
        self._repository = repository

    def import_bundle(self, bundle: ImportBundle, *, activate: bool = True) -> ImportReport:
        started = time.perf_counter()
        self._validate_bundle(bundle)
        report = ImportReport.empty(bundle.snapshot.resource_name)
        for warning in bundle.warnings:
            report = report.add_warning(
                warning.code, warning.message, source_record_id=warning.source_record_id
            )

        counts = bundle.counts
        logger.info(
            "Importing %s snapshot (%d entities, %d revisions, %d mappings, %d claims, %d evidence)",
            bundle.snapshot.resource_name,
            counts.entities,
            counts.entity_revisions,
            counts.mappings,
            counts.claims,
            counts.evidence,
        )
        self._repository.bulk_import_bundle(bundle, activate=activate)
        stored_snapshot = bundle.snapshot

        duration = time.perf_counter() - started
        logger.info(
            "Imported %s in %.1fs",
            bundle.snapshot.resource_name,
            duration,
        )
        return report.with_snapshot(stored_snapshot.id, bundle.counts).model_copy(
            update={"duration_seconds": duration}
        )

    def _validate_bundle(self, bundle: ImportBundle) -> None:
        if not bundle.snapshot.checksum:
            raise BiomedicalValidationError("Import bundle is missing a snapshot checksum")
        if not bundle.snapshot.resource_name:
            raise BiomedicalValidationError("Import bundle is missing a resource name")
        snapshot_ids = {bundle.snapshot.id}
        for entity in bundle.entities:
            if entity.created_in_snapshot_id is not None:
                snapshot_ids.add(entity.created_in_snapshot_id)
        for revision in bundle.revisions:
            if revision.snapshot_id != bundle.snapshot.id:
                raise BiomedicalValidationError(
                    f"Revision {revision.id} references unexpected snapshot"
                )
        for mapping in bundle.mappings:
            if mapping.relation.can_auto_join is False and mapping.relation.value == "exact":
                pass
            if mapping.snapshot_id != bundle.snapshot.id:
                raise BiomedicalValidationError(
                    f"Mapping {mapping.id} references unexpected snapshot"
                )
        for item in bundle.evidence:
            if item.snapshot_id != bundle.snapshot.id:
                raise BiomedicalValidationError(
                    f"Evidence {item.id} references unexpected snapshot"
                )

    def _upsert_snapshot(self, snapshot: ResourceSnapshot) -> ResourceSnapshot:
        return self._repository.upsert_snapshot(snapshot)
