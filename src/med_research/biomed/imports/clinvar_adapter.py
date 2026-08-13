"""ClinVar genomic variant & clinical significance import adapter."""

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


class ClinVarImportAdapter(ImportAdapter):
    """Adapter for importing ClinVar variant pathogenicity and disease associations."""

    @property
    def resource_name(self) -> str:
        return "clinvar"

    @property
    def supported_formats(self) -> tuple[str, ...]:
        return ("json", "tsv")

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
            name="ClinVar Genomic Variant Classifications",
            namespace_prefix=self.resource_name,
            upstream_version=version,
            artifact_format=path.suffix.lstrip("."),
            importer_name="ClinVarImportAdapter",
            importer_version="1.0.0",
        )

        records: list[dict[str, Any]] = []
        if path.suffix == ".json":
            data = json.loads(raw_text)
            if isinstance(data, list):
                records = data
            elif isinstance(data, dict):
                records = data.get("variants") or data.get("records") or []
        else:
            # Simple TSV parsing
            lines = [line.strip() for line in raw_text.splitlines() if line.strip()]
            if lines:
                headers = lines[0].split("\t")
                for line in lines[1:]:
                    vals = line.split("\t")
                    if len(vals) == len(headers):
                        records.append(dict(zip(headers, vals, strict=True)))

        entities: list[Entity] = []
        revisions: list[EntityRevision] = []
        claims: list[Claim] = []
        evidence: list[ClaimEvidence] = []
        seen_entities: set[str] = set()

        for item in records:
            vcv_id = str(item.get("vcv_id") or item.get("variation_id") or item.get("id") or "")
            gene_symbol = str(item.get("gene_symbol") or item.get("gene") or "")
            gene_id = str(item.get("gene_id") or "")
            disease_curie = str(item.get("condition_curie") or item.get("disease_curie") or item.get("mondo_id") or "")
            disease_name = str(item.get("condition_name") or item.get("disease_name") or disease_curie)
            clinical_sig = str(item.get("clinical_significance") or item.get("significance") or "Pathogenic")

            if not gene_symbol and not gene_id:
                continue

            gene_curie = f"NCBIGene:{gene_id}" if gene_id else f"HGNC:{gene_symbol}"
            if not disease_curie:
                continue

            # Ensure gene entity
            if gene_curie not in seen_entities:
                seen_entities.add(gene_curie)
                g_ent_id = entity_uuid(EntityType.GENE, gene_curie)
                entities.append(
                    Entity(
                        id=g_ent_id,
                        primary_curie=gene_curie,
                        entity_type=EntityType.GENE,
                        created_in_snapshot_id=snapshot.id,
                    )
                )
                revisions.append(
                    EntityRevision(
                        id=entity_revision_uuid(g_ent_id, snapshot.id),
                        entity_id=g_ent_id,
                        snapshot_id=snapshot.id,
                        label=gene_symbol or gene_curie,
                    )
                )

            # Ensure condition entity
            if disease_curie not in seen_entities:
                seen_entities.add(disease_curie)
                d_ent_id = entity_uuid(EntityType.CONDITION, disease_curie)
                entities.append(
                    Entity(
                        id=d_ent_id,
                        primary_curie=disease_curie,
                        entity_type=EntityType.CONDITION,
                        created_in_snapshot_id=snapshot.id,
                    )
                )
                revisions.append(
                    EntityRevision(
                        id=entity_revision_uuid(d_ent_id, snapshot.id),
                        entity_id=d_ent_id,
                        snapshot_id=snapshot.id,
                        label=disease_name,
                    )
                )

            # Claim: Condition associated with gene
            c_id = claim_uuid(disease_curie, Predicate.ASSOCIATED_WITH_GENE, gene_curie)
            claims.append(
                Claim(
                    id=c_id,
                    subject_curie=disease_curie,
                    predicate=Predicate.ASSOCIATED_WITH_GENE,
                    object_curie=gene_curie,
                )
            )

            # Map clinical significance to evidence direction
            sig_lower = clinical_sig.lower()
            if "benign" in sig_lower:
                direction = EvidenceDirection.CONTRADICTORY
            else:
                direction = EvidenceDirection.SUPPORTING

            rec_id = vcv_id if vcv_id else f"CLINVAR:{hashlib.md5(f'{gene_curie}_{disease_curie}'.encode()).hexdigest()[:8]}"
            ev_id = claim_evidence_uuid(c_id, snapshot.id, direction, rec_id)

            evidence.append(
                ClaimEvidence(
                    id=ev_id,
                    claim_id=c_id,
                    snapshot_id=snapshot.id,
                    direction=direction,
                    source_record_id=rec_id,
                    evidence_type="clinical_significance",
                    strength_label=clinical_sig,
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
