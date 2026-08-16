"""Assemble legacy disease projections into import bundles."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Sequence

from med_research.biomed.identifiers import snapshot_uuid
from med_research.biomed.imports.models import ImportBundle
from med_research.biomed.legacy.checksums import legacy_bundle_checksum
from med_research.biomed.legacy.manifest import legacy_disease_ids, legacy_resource_version
from med_research.biomed.legacy.projector import merge_projections, project_disease
from med_research.biomed.models import ResourcePolicy, ResourceSnapshot


class LegacyMigrationAdapter:
    resource_name = "legacy-curated"

    def build_bundle(self, disease_ids: Sequence[str] | None = None) -> ImportBundle:
        selected = sorted(disease_ids or legacy_disease_ids())
        version = legacy_resource_version()
        checksum = legacy_bundle_checksum(list(selected))
        snapshot_id = snapshot_uuid(self.resource_name, version, checksum)
        projections = [
            project_disease(disease_id, snapshot_id=snapshot_id) for disease_id in selected
        ]
        entities, revisions, mappings, claims, evidence, warnings, metadata = merge_projections(
            projections,
            snapshot_id=snapshot_id,
        )
        now = datetime.now(tz=UTC)
        snapshot = ResourceSnapshot(
            id=snapshot_id,
            resource_name=self.resource_name,
            version=version,
            checksum=checksum,
            name="Curated legacy disease projections",
            namespace_prefix="LEGACY",
            artifact_format="json",
            upstream_version=version,
            license_id="CC-BY-4.0",
            license_url="https://creativecommons.org/licenses/by/4.0/",
            redistribution_policy="redistributable",
            imported_at=now,
            counts={
                "diseases": len(selected),
                "entities": len(entities),
                "claims": len(claims),
            },
        )
        return ImportBundle.build(
            snapshot,
            entities=entities,
            revisions=revisions,
            mappings=mappings,
            claims=claims,
            evidence=evidence,
            warnings=warnings,
            metadata=metadata,
        )

    @property
    def policy(self) -> ResourcePolicy:
        return ResourcePolicy(
            resource_name=self.resource_name,
            license_id="CC-BY-4.0",
            license_url="https://creativecommons.org/licenses/by/4.0/",
            redistribution_policy="redistributable",
        )
