"""Staging models for biomedical ontology imports."""

from __future__ import annotations

import hashlib
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from med_research.biomed.identifiers import fingerprint_json, snapshot_uuid
from med_research.biomed.models import (
    Claim,
    ClaimEvidence,
    Entity,
    EntityMapping,
    EntityRevision,
    ResourcePolicy,
    ResourceSnapshot,
)


class ImportRecordCounts(BaseModel):
    model_config = ConfigDict(frozen=True)

    entities: int = 0
    entity_revisions: int = 0
    mappings: int = 0
    claims: int = 0
    evidence: int = 0

    @classmethod
    def from_records(
        cls,
        *,
        entities: list[Any],
        revisions: list[Any],
        mappings: list[Any],
        claims: list[Any],
        evidence: list[Any],
    ) -> ImportRecordCounts:
        return cls(
            entities=len(entities),
            entity_revisions=len(revisions),
            mappings=len(mappings),
            claims=len(claims),
            evidence=len(evidence),
        )

    @classmethod
    def empty(cls) -> ImportRecordCounts:
        return cls()


class ImportWarning(BaseModel):
    model_config = ConfigDict(frozen=True)

    code: str
    message: str
    source_record_id: str = ""


class ImportBundle(BaseModel):
    model_config = ConfigDict(frozen=True)

    snapshot: ResourceSnapshot
    entities: list[Entity] = Field(default_factory=list)
    revisions: list[EntityRevision] = Field(default_factory=list)
    mappings: list[EntityMapping] = Field(default_factory=list)
    claims: list[Claim] = Field(default_factory=list)
    evidence: list[ClaimEvidence] = Field(default_factory=list)
    counts: ImportRecordCounts = Field(default_factory=ImportRecordCounts.empty)
    warnings: list[ImportWarning] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)

    @classmethod
    def build(
        cls,
        snapshot: ResourceSnapshot,
        *,
        entities: list[Entity] | None = None,
        revisions: list[EntityRevision] | None = None,
        mappings: list[EntityMapping] | None = None,
        claims: list[Claim] | None = None,
        evidence: list[ClaimEvidence] | None = None,
        warnings: list[ImportWarning] | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> ImportBundle:
        entity_list = list(entities or [])
        revision_list = list(revisions or [])
        mapping_list = list(mappings or [])
        claim_list = list(claims or [])
        evidence_list = list(evidence or [])
        warning_list = list(warnings or [])
        counts = ImportRecordCounts.from_records(
            entities=entity_list,
            revisions=revision_list,
            mappings=mapping_list,
            claims=claim_list,
            evidence=evidence_list,
        )
        return cls(
            snapshot=snapshot,
            entities=entity_list,
            revisions=revision_list,
            mappings=mapping_list,
            claims=claim_list,
            evidence=evidence_list,
            counts=counts,
            warnings=warning_list,
            metadata=dict(metadata or {}),
        )

    @classmethod
    def from_artifact(
        cls,
        *,
        policy: ResourcePolicy,
        artifact_path: Path,
        upstream_version: str,
        entities: list[Entity] | None = None,
        revisions: list[EntityRevision] | None = None,
        mappings: list[EntityMapping] | None = None,
        claims: list[Claim] | None = None,
        evidence: list[ClaimEvidence] | None = None,
        warnings: list[ImportWarning] | None = None,
        artifact_format: str = "",
        namespace_prefix: str = "",
        name: str = "",
    ) -> ImportBundle:
        if policy.redistribution_policy == "restricted":
            raise ValueError(
                f"Resource {policy.resource_name} has restricted redistribution policy; "
                "operator-supplied local artifacts require explicit adapter configuration"
            )
        resolved = artifact_path.resolve()
        checksum = _artifact_checksum(resolved)
        version = upstream_version.strip() or checksum[:16]
        snapshot_id = snapshot_uuid(policy.resource_name, version, checksum)
        now = datetime.now(tz=UTC)
        snapshot = ResourceSnapshot(
            id=snapshot_id,
            resource_name=policy.resource_name,
            version=version,
            checksum=checksum,
            name=name or policy.resource_name,
            namespace_prefix=namespace_prefix,
            artifact_format=artifact_format or resolved.suffix.lstrip("."),
            upstream_version=upstream_version,
            artifact_size=resolved.stat().st_size,
            license_id=policy.license_id,
            license_url=policy.license_url,
            redistribution_policy=policy.redistribution_policy,
            imported_at=now,
        )
        return cls.build(
            snapshot,
            entities=entities,
            revisions=revisions,
            mappings=mappings,
            claims=claims,
            evidence=evidence,
            warnings=warnings,
        )


class ImportReport(BaseModel):
    model_config = ConfigDict(frozen=True)

    resource_name: str
    snapshot_id: UUID | None = None
    counts: ImportRecordCounts = Field(default_factory=ImportRecordCounts.empty)
    warnings: list[ImportWarning] = Field(default_factory=list)
    rejected_records: int = 0
    fingerprint: str = ""
    duration_seconds: float = 0.0

    @classmethod
    def empty(cls, resource_name: str) -> ImportReport:
        return cls(resource_name=resource_name)

    def add_warning(self, code: str, message: str, *, source_record_id: str = "") -> ImportReport:
        warning = ImportWarning(code=code, message=message, source_record_id=source_record_id)
        return self.model_copy(update={"warnings": [*self.warnings, warning]})

    def with_snapshot(self, snapshot_id: UUID, counts: ImportRecordCounts) -> ImportReport:
        fingerprint_payload = {
            "resource_name": self.resource_name,
            "snapshot_id": str(snapshot_id),
            "counts": counts.model_dump(),
            "warnings": [item.model_dump() for item in self.warnings],
            "rejected_records": self.rejected_records,
        }
        return self.model_copy(
            update={
                "snapshot_id": snapshot_id,
                "counts": counts,
                "fingerprint": fingerprint_json(fingerprint_payload),
            }
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "resource_name": self.resource_name,
            "snapshot_id": str(self.snapshot_id) if self.snapshot_id else None,
            "counts": self.counts.model_dump(),
            "warnings": [item.model_dump() for item in self.warnings],
            "rejected_records": self.rejected_records,
            "fingerprint": self.fingerprint,
            "duration_seconds": self.duration_seconds,
        }


def _artifact_checksum(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return f"sha256:{digest.hexdigest()}"
