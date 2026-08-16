"""ChEMBL drug-target bioactivity import adapter."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

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


class ChEMBLImportAdapter(ImportAdapter):
    """Adapter for importing ChEMBL drug-target bioactivity claims from JSON artifacts."""

    @property
    def resource_name(self) -> str:
        return "chembl"

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
        data = json.loads(raw_text)
        if not isinstance(data, list):
            data = data.get("activities", [])

        checksum = hashlib.sha256(raw_text.encode("utf-8")).hexdigest()
        version = str(kwargs.get("version", "33"))
        snap_id = snapshot_uuid(self.resource_name, version, checksum)

        snapshot = ResourceSnapshot(
            id=snap_id,
            resource_name=self.resource_name,
            version=version,
            checksum=checksum,
            name="ChEMBL Drug Target Bioactivities",
            artifact_format="json",
            importer_name="ChEMBLImportAdapter",
            importer_version="1.0.0",
        )

        entities: list[Entity] = []
        revisions: list[EntityRevision] = []
        claims: list[Claim] = []
        evidence: list[ClaimEvidence] = []
        seen_entities: set[str] = set()

        for item in data:
            drug_id = item.get("molecule_chembl_id") or item.get("drug_id")
            target_id = item.get("target_chembl_id") or item.get("target_id")
            if not drug_id or not target_id:
                continue

            drug_curie = f"CHEMBL:{drug_id}"
            target_curie = (
                f"UNIPROT:{target_id}" if not target_id.startswith("CHEMBL:") else target_id
            )

            if drug_curie not in seen_entities:
                seen_entities.add(drug_curie)
                d_ent_id = entity_uuid(EntityType.INTERVENTION, drug_curie)
                entities.append(
                    Entity(
                        id=d_ent_id,
                        primary_curie=drug_curie,
                        entity_type=EntityType.INTERVENTION,
                        created_in_snapshot_id=snapshot.id,
                    )
                )
                revisions.append(
                    EntityRevision(
                        id=entity_revision_uuid(d_ent_id, snapshot.id),
                        entity_id=d_ent_id,
                        snapshot_id=snapshot.id,
                        label=item.get("molecule_name", drug_curie),
                    )
                )

            if target_curie not in seen_entities:
                seen_entities.add(target_curie)
                t_ent_id = entity_uuid(EntityType.GENE, target_curie)
                entities.append(
                    Entity(
                        id=t_ent_id,
                        primary_curie=target_curie,
                        entity_type=EntityType.GENE,
                        created_in_snapshot_id=snapshot.id,
                    )
                )
                revisions.append(
                    EntityRevision(
                        id=entity_revision_uuid(t_ent_id, snapshot.id),
                        entity_id=t_ent_id,
                        snapshot_id=snapshot.id,
                        label=item.get("target_name", target_curie),
                    )
                )

            c_id = claim_uuid(drug_curie, Predicate.TREATED_BY, target_curie)
            c_obj = Claim(
                id=c_id,
                subject_curie=drug_curie,
                object_curie=target_curie,
                predicate=Predicate.TREATED_BY,
                qualifiers={
                    "ic50_nm": item.get("value"),
                    "type": item.get("standard_type", "IC50"),
                },
            )
            claims.append(c_obj)

            ev_id = claim_evidence_uuid(
                c_obj.id,
                snapshot.id,
                EvidenceDirection.SUPPORTING,
                str(item.get("activity_id", drug_id)),
            )
            evidence.append(
                ClaimEvidence(
                    id=ev_id,
                    claim_id=c_obj.id,
                    snapshot_id=snapshot.id,
                    direction=EvidenceDirection.SUPPORTING,
                    source_record_id=str(item.get("activity_id", drug_id)),
                    evidence_type="chembl_bioactivity",
                )
            )

        return ImportBundle.build(
            snapshot,
            entities=entities,
            revisions=revisions,
            mappings=[],
            claims=claims,
            evidence=evidence,
        )
