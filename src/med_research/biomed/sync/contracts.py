"""Sync source protocol and shared contracts."""

from __future__ import annotations

from pathlib import Path
from typing import Protocol, runtime_checkable

from med_research.biomed.imports.models import ImportBundle
from med_research.biomed.models import ResourcePolicy
from med_research.biomed.sync.models import SyncDiff, SyncProvenance


@runtime_checkable
class SyncSource(Protocol):
    """Upstream biomedical source with a full sync lifecycle."""

    @property
    def source_id(self) -> str: ...

    @property
    def resource_name(self) -> str: ...

    @property
    def policy(self) -> ResourcePolicy: ...

    def discover_version(self, *, staging_root: Path) -> str: ...

    def fetch(self, *, staging_root: Path, version: str, dry_run: bool) -> Path: ...

    def verify(self, artifact_root: Path) -> dict[str, str]: ...

    def normalize(
        self,
        artifact_root: Path,
        *,
        version: str,
        mondo_mappings: dict[str, str] | None = None,
    ) -> ImportBundle: ...

    def diff(
        self,
        bundle: ImportBundle,
        *,
        previous_checksum: str | None,
        previous_counts: dict[str, int] | None,
    ) -> SyncDiff: ...

    def build_provenance(
        self,
        bundle: ImportBundle,
        *,
        stages_completed: list[str],
    ) -> SyncProvenance: ...
