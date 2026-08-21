"""Orchestrate the biomedical source sync lifecycle."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING

from med_research.biomed.imports.service import ImportService
from med_research.biomed.sync.contracts import SyncSource
from med_research.biomed.sync.models import (
    StageResult,
    SyncReport,
    SyncStage,
    SyncStatus,
)
from med_research.biomed.sync.registry import list_syncable_sources
from med_research.biomed.sync.sources.opentargets import OpenTargetsSyncSource
from med_research.logging_config import get_logger

if TYPE_CHECKING:
    from med_research.biomed.repository import BiomedicalRepository

logger = get_logger(__name__)

_SYNC_SOURCES: dict[str, SyncSource] = {
    "open_targets": OpenTargetsSyncSource(),
}


def get_sync_source(source_id: str) -> SyncSource:
    if source_id not in _SYNC_SOURCES:
        supported = ", ".join(sorted(_SYNC_SOURCES))
        raise ValueError(f"Unknown sync source {source_id!r}; supported: {supported}")
    return _SYNC_SOURCES[source_id]


class SyncService:
    """Production sync orchestrator: DISCOVER → FETCH → … → UPDATE PROVENANCE."""

    def __init__(
        self,
        repository: BiomedicalRepository,
        *,
        staging_root: Path | None = None,
    ) -> None:
        self._repository = repository
        self._staging_root = staging_root or Path("data/bulk/sync")

    def run(
        self,
        source_id: str,
        *,
        dry_run: bool = False,
        publish: bool = True,
    ) -> SyncReport:
        source = get_sync_source(source_id)
        stages: list[StageResult] = []
        staging = self._staging_root / source.source_id
        staging.mkdir(parents=True, exist_ok=True)

        def record(stage: SyncStage, status: SyncStatus, message: str = "", **meta: object) -> None:
            stages.append(
                StageResult(
                    stage=stage,
                    status=status,
                    message=message,
                    finished_at=datetime.now(UTC),
                    metadata={key: value for key, value in meta.items() if value is not None},
                )
            )

        try:
            version = source.discover_version(staging_root=staging)
            record(SyncStage.DISCOVER_VERSION, SyncStatus.COMPLETED, f"version={version}")

            artifact_root = source.fetch(staging_root=staging, version=version, dry_run=dry_run)
            record(
                SyncStage.FETCH,
                SyncStatus.COMPLETED if not dry_run else SyncStatus.SKIPPED,
                str(artifact_root),
                dry_run=dry_run,
            )

            checksums = source.verify(artifact_root)
            record(SyncStage.VERIFY, SyncStatus.COMPLETED, f"{len(checksums)} artifacts verified")
            record(SyncStage.STORE_RAW, SyncStatus.COMPLETED, str(artifact_root))

            mondo_mappings = self._load_mondo_mappings()
            bundle = source.normalize(
                artifact_root,
                version=version,
                mondo_mappings=mondo_mappings,
            )
            record(
                SyncStage.NORMALIZE,
                SyncStatus.COMPLETED,
                f"{bundle.counts.claims} claims, {bundle.counts.evidence} evidence",
            )

            ImportService(self._repository)._validate_bundle(bundle)
            record(SyncStage.VALIDATE, SyncStatus.COMPLETED)

            previous = self._repository.get_active_snapshot(source.resource_name)
            previous_checksum = previous.checksum if previous else None
            previous_counts = dict(previous.counts) if previous else None
            diff = source.diff(
                bundle,
                previous_checksum=previous_checksum,
                previous_counts=previous_counts,
            )
            record(SyncStage.DIFF, SyncStatus.COMPLETED, f"changed={diff.changed}")

            import_fingerprint = ""
            if publish and not dry_run:
                report = ImportService(self._repository).import_bundle(bundle, activate=True)
                import_fingerprint = report.fingerprint
                record(
                    SyncStage.PUBLISH,
                    SyncStatus.COMPLETED,
                    f"snapshot={report.snapshot_id}",
                )
            else:
                record(
                    SyncStage.PUBLISH,
                    SyncStatus.SKIPPED,
                    "dry-run" if dry_run else "publish disabled",
                )

            provenance = source.build_provenance(
                bundle,
                stages_completed=[
                    stage.stage.value for stage in stages if stage.status is SyncStatus.COMPLETED
                ],
            )
            record(
                SyncStage.UPDATE_PROVENANCE,
                SyncStatus.COMPLETED,
                provenance.manifest_fingerprint,
            )

            return SyncReport(
                source_id=source_id,
                status=SyncStatus.COMPLETED,
                dry_run=dry_run,
                stages=stages,
                diff=diff,
                provenance=provenance,
                import_report_fingerprint=import_fingerprint,
            )
        except Exception as exc:
            logger.exception("Sync failed for %s", source_id)
            return SyncReport(
                source_id=source_id,
                status=SyncStatus.FAILED,
                dry_run=dry_run,
                stages=stages,
                error=str(exc),
            )

    def _load_mondo_mappings(self) -> dict[str, str]:
        snapshot = self._repository.get_active_snapshot("mondo")
        if snapshot is None:
            return {}
        with self._repository.database.connect() as connection:
            rows = connection.execute(
                """
                SELECT subject_curie, object_curie FROM entity_mappings
                WHERE snapshot_id = ? AND relation = 'exact'
                """,
                (str(snapshot.id),),
            ).fetchall()
        mappings: dict[str, str] = {}
        for row in rows:
            external = str(row["object_curie"])
            mondo = str(row["subject_curie"])
            mappings[external] = mondo
            if external.upper().startswith("EFO:"):
                mappings[external.replace(":", "_")] = mondo
        return mappings


def list_sources() -> list[str]:
    return list_syncable_sources()
