"""PubChem bioactivity import adapter."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from uuid import UUID

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


class PubChemImportAdapter(ImportAdapter):
    """Adapter for importing PubChem bioactivity claims."""

    @property
    def resource_name(self) -> str:
        return "pubchem"

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
            data = data.get("bioactivities", [])

        checksum = hashlib.sha256(raw_text.encode("utf-8")).hexdigest()
        version = str(kwargs.get("version", "2026.1"))
        snap_id = snapshot_uuid(self.resource_name, version, checksum)

        snapshot = ResourceSnapshot(
            id=snap_id,
            resource_name=self.resource_name,
            version=version,
            checksum=checksum,
            name="PubChem Bioactivities",
            artifact_format="json",
            importer_name="PubChemImportAdapter",
            importer_version="1.0.0",
        )

        entities: list[Entity] = []
        revisions: list[EntityRevision] = []
        claims: list[Claim] = []
        evidence: list[ClaimEvidence] = []
        seen_entities: set[str] = set()

        for item in data:
            cid = item.get("cid") or item.get("compound_id")
            gene_id = item.get("gene_id") or item.get("target_id")
            if not cid or not gene_id:
                continue

            compound_curie = f"PUBCHEM.COMPOUND:{cid}"
            target_curie = f"NCBIGene:{gene_id}"

            if compound_curie not in seen_entities:
                seen_entities.add(compound_curie)
                c_ent_id = entity_uuid(EntityType.INTERVENTION, compound_curie)
                entities.append(Entity(id=c_ent_id, primary_curie=compound_curie, entity_type=EntityType.INTERVENTION, created_in_snapshot_id=snapshot.id))
                revisions.append(EntityRevision(id=entity_revision_uuid(c_ent_id, snapshot.id), entity_id=c_ent_id, snapshot_id=snapshot.id, label=item.get("cmpd_name", compound_curie)))

            if target_curie not in seen_entities:
                seen_entities.add(target_curie)
                t_ent_id = entity_uuid(EntityType.GENE, target_curie)
                entities.append(Entity(id=t_ent_id, primary_curie=target_curie, entity_type=EntityType.GENE, created_in_snapshot_id=snapshot.id))
                revisions.append(EntityRevision(id=entity_revision_uuid(t_ent_id, snapshot.id), entity_id=t_ent_id, snapshot_id=snapshot.id, label=item.get("gene_symbol", target_curie)))

            c_id = claim_uuid(compound_curie, Predicate.TREATED_BY, target_curie)
            c_obj = Claim(
                id=c_id,
                subject_curie=compound_curie,
                object_curie=target_curie,
                predicate=Predicate.TREATED_BY,
                qualifiers={"aid": item.get("aid"), "activity": item.get("activity")},
            )
            claims.append(c_obj)


            ev_id = claim_evidence_uuid(c_obj.id, snapshot.id, EvidenceDirection.SUPPORTING, str(item.get("aid", cid)))
            evidence.append(ClaimEvidence(
                id=ev_id,
                claim_id=c_obj.id,
                snapshot_id=snapshot.id,
                direction=EvidenceDirection.SUPPORTING,
                source_record_id=str(item.get("aid", cid)),
                evidence_data={"source": "pubchem", "activity": item.get("activity")},
            ))

        return ImportBundle.create(
            snapshot=snapshot,
            entities=entities,
            revisions=revisions,
            mappings=[],
            claims=claims,
            evidence=evidence,
        )
