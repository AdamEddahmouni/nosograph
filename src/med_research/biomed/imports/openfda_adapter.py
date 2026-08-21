"""OpenFDA adverse events & drug indications import adapter."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from med_research.biomed.identifiers import (
    claim_evidence_uuid,
    claim_uuid,
    entity_revision_uuid,
    entity_uuid,
    snapshot_uuid,
)
from med_research.biomed.imports.contracts import ImportAdapter
from med_research.biomed.imports.models import ImportBundle
from med_research.biomed.models import (
    Claim,
    ClaimEvidence,
    Entity,
    EntityRevision,
    EntityType,
    EvidenceDirection,
    Predicate,
    ResourcePolicy,
    ResourceSnapshot,
)


class OpenFDAImportAdapter(ImportAdapter):
    """Adapter for importing OpenFDA drug adverse events and label indications."""

    @property
    def resource_name(self) -> str:
        return "openfda"

    @property
    def supported_formats(self) -> tuple[str, ...]:
        return ("json",)

    def parse(
        self,
        path: Path,
        policy: ResourcePolicy,
        **kwargs: object,
    ) -> ImportBundle:
        raw_text = path.read_text(encoding="utf-8")
        checksum = hashlib.sha256(raw_text.encode("utf-8")).hexdigest()
        version = str(kwargs.get("version", "2026.1"))
        snap_id = snapshot_uuid(self.resource_name, version, checksum)

        snapshot = ResourceSnapshot(
            id=snap_id,
            resource_name=self.resource_name,
            version=version,
            checksum=checksum,
            name="OpenFDA Drug Adverse Events & Indications",
            namespace_prefix=self.resource_name,
            upstream_version=version,
            artifact_format="json",
            importer_name="OpenFDAImportAdapter",
            importer_version="1.0.0",
        )

        data = json.loads(raw_text)
        records: list[dict[str, Any]] = []
        if isinstance(data, list):
            records = data
        elif isinstance(data, dict):
            records = data.get("results") or data.get("records") or []

        entities: list[Entity] = []
        revisions: list[EntityRevision] = []
        claims: list[Claim] = []
        evidence: list[ClaimEvidence] = []
        seen_entities: set[str] = set()

        for item in records:
            drug_name = str(
                item.get("drug_name")
                or item.get("medicinalproduct")
                or item.get("substance_name")
                or ""
            )
            cid = item.get("pubchem_cid") or item.get("cid")
            condition_curie = str(
                item.get("condition_curie") or item.get("mondo_id") or item.get("ncit_id") or ""
            )
            condition_name = str(
                item.get("condition_name")
                or item.get("reaction")
                or item.get("indication")
                or condition_curie
            )
            report_id = str(
                item.get("safetyreportid") or item.get("report_id") or item.get("id") or ""
            )
            record_type = str(item.get("record_type") or "indication")

            if not drug_name and not cid:
                continue
            if not condition_curie:
                continue

            drug_curie = (
                f"PUBCHEM.COMPOUND:{cid}" if cid else f"DRUG:{drug_name.upper().replace(' ', '_')}"
            )

            # Ensure intervention entity
            if drug_curie not in seen_entities:
                seen_entities.add(drug_curie)
                c_ent_id = entity_uuid(EntityType.INTERVENTION, drug_curie)
                entities.append(
                    Entity(
                        id=c_ent_id,
                        primary_curie=drug_curie,
                        entity_type=EntityType.INTERVENTION,
                        created_in_snapshot_id=snapshot.id,
                    )
                )
                revisions.append(
                    EntityRevision(
                        id=entity_revision_uuid(c_ent_id, snapshot.id),
                        entity_id=c_ent_id,
                        snapshot_id=snapshot.id,
                        label=drug_name or drug_curie,
                    )
                )

            # Ensure condition entity
            if condition_curie not in seen_entities:
                seen_entities.add(condition_curie)
                d_ent_id = entity_uuid(EntityType.CONDITION, condition_curie)
                entities.append(
                    Entity(
                        id=d_ent_id,
                        primary_curie=condition_curie,
                        entity_type=EntityType.CONDITION,
                        created_in_snapshot_id=snapshot.id,
                    )
                )
                revisions.append(
                    EntityRevision(
                        id=entity_revision_uuid(d_ent_id, snapshot.id),
                        entity_id=d_ent_id,
                        snapshot_id=snapshot.id,
                        label=condition_name,
                    )
                )

            if record_type == "adverse_event":
                predicate = Predicate.ASSOCIATED_WITH_EXPOSURE
                direction = EvidenceDirection.SUPPORTING
                evidence_type = "adverse_event_report"
            else:
                predicate = Predicate.TREATED_BY
                direction = EvidenceDirection.SUPPORTING
                evidence_type = "label_indication"

            c_id = claim_uuid(condition_curie, predicate, drug_curie)
            claims.append(
                Claim(
                    id=c_id,
                    subject_curie=condition_curie,
                    predicate=predicate,
                    object_curie=drug_curie,
                )
            )

            rec_id = (
                report_id
                if report_id
                else f"FDA:{hashlib.md5(f'{drug_curie}_{condition_curie}'.encode(), usedforsecurity=False).hexdigest()[:8]}"
            )
            ev_id = claim_evidence_uuid(c_id, snapshot.id, direction, rec_id)

            evidence.append(
                ClaimEvidence(
                    id=ev_id,
                    claim_id=c_id,
                    snapshot_id=snapshot.id,
                    direction=direction,
                    source_record_id=rec_id,
                    evidence_type=evidence_type,
                    strength_label=record_type.replace("_", " ").title(),
                )
            )

        return ImportBundle.build(
            snapshot=snapshot,
            entities=entities,
            revisions=revisions,
            mappings=[],
            claims=claims,
            evidence=evidence,
        )
