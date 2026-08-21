"""Domain models for biomedical source synchronization."""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class SyncStage(str, Enum):
    DISCOVER_VERSION = "discover_version"
    FETCH = "fetch"
    VERIFY = "verify"
    STORE_RAW = "store_raw"
    NORMALIZE = "normalize"
    VALIDATE = "validate"
    DIFF = "diff"
    PUBLISH = "publish"
    UPDATE_PROVENANCE = "update_provenance"


class SyncStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"


class StageResult(BaseModel):
    model_config = ConfigDict(frozen=True)

    stage: SyncStage
    status: SyncStatus
    message: str = ""
    started_at: datetime | None = None
    finished_at: datetime | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class SyncDiff(BaseModel):
    model_config = ConfigDict(frozen=True)

    previous_snapshot_id: UUID | None = None
    previous_checksum: str | None = None
    current_checksum: str
    counts_delta: dict[str, int] = Field(default_factory=dict)
    changed: bool = False


class SyncProvenance(BaseModel):
    model_config = ConfigDict(frozen=True)

    source_id: str
    resource_name: str
    upstream_version: str
    checksum: str
    snapshot_id: UUID | None = None
    manifest_fingerprint: str = ""
    retrieved_at: datetime | None = None
    importer_name: str = ""
    importer_version: str = ""
    stages_completed: list[SyncStage] = Field(default_factory=list)


class SyncReport(BaseModel):
    model_config = ConfigDict(frozen=True)

    source_id: str
    status: SyncStatus
    dry_run: bool = False
    stages: list[StageResult] = Field(default_factory=list)
    diff: SyncDiff | None = None
    provenance: SyncProvenance | None = None
    import_report_fingerprint: str = ""
    error: str | None = None

    @property
    def succeeded(self) -> bool:
        return self.status is SyncStatus.COMPLETED and self.error is None
