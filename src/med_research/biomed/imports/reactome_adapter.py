"""Reactome Pathway Database import adapter."""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Any

from med_research.biomed.errors import BiomedicalValidationError
from med_research.biomed.identifiers import (
    claim_evidence_uuid,
    claim_uuid,
    entity_revision_uuid,
    entity_uuid,
    normalize_curie,
    snapshot_uuid,
)
from med_research.biomed.imports.contracts import ImportAdapter
from med_research.biomed.imports.models import ImportBundle, ImportWarning
from med_research.biomed.models import (
    Claim,
    ClaimEvidence,
    Entity,
    EntityMapping,
    EntityRevision,
    EntityType,
    EvidenceDirection,
    Predicate,
    ResourcePolicy,
    ResourceSnapshot,
)

_REACTOME_ID_PATTERN = re.compile(r"^(?:REACTOME:)?(R-[A-Z]{3}-\d+(?:\.\d+)?)$", re.IGNORECASE)


def _normalize_reactome_id(raw_id: str) -> str:
    match = _REACTOME_ID_PATTERN.match(raw_id.strip())
    if match:
        return f"REACTOME:{match.group(1).upper()}"
    if raw_id.upper().startswith("REACTOME:"):
        return normalize_curie(raw_id)
    return f"REACTOME:{raw_id.strip().upper()}"


class ReactomeImportAdapter(ImportAdapter):
    """Adapter for importing Reactome biological pathways, hierarchical relations, and participants."""

    @property
    def resource_name(self) -> str:
        return "reactome"

    @property
    def supported_formats(self) -> tuple[str, ...]:
        return ("json", "tsv", "txt")

    def parse(
        self,
        path: Path,
        policy: ResourcePolicy,
        **kwargs: object,
    ) -> ImportBundle:
        raw_text = path.read_text(encoding="utf-8")
        checksum = hashlib.sha256(raw_text.encode("utf-8")).hexdigest()
        version = str(kwargs.get("version", "v89"))
        snap_id = snapshot_uuid(self.resource_name, version, checksum)

        snapshot = ResourceSnapshot(
            id=snap_id,
            resource_name=self.resource_name,
            version=version,
            checksum=checksum,
            name="Reactome Pathway Knowledgebase",
            namespace_prefix="REACTOME",
            source_url=str(kwargs.get("source_url") or "https://reactome.org"),
            upstream_version=version,
            artifact_format=path.suffix.lstrip("."),
            license_id="CC-BY-4.0",
            license_spdx="CC-BY-4.0",
            redistribution_policy=policy.redistribution_policy or "permitted",
            importer_name="ReactomeImportAdapter",
            importer_version="3.0.0",
        )

        entities: dict[str, Entity] = {}
        revisions: list[EntityRevision] = []
        mappings: list[EntityMapping] = []
        claims: list[Claim] = []
        evidence: list[ClaimEvidence] = []
        warnings: list[ImportWarning] = []

        if path.suffix.lower() == ".json":
            self._parse_json_content(
                raw_text, snap_id, entities, revisions, mappings, claims, evidence, warnings
            )
        else:
            self._parse_tsv_content(
                raw_text, snap_id, entities, revisions, mappings, claims, evidence, warnings
            )

        return ImportBundle.build(
            snapshot,
            entities=list(entities.values()),
            revisions=revisions,
            mappings=mappings,
            claims=claims,
            evidence=evidence,
            warnings=warnings,
        )

    def _parse_json_content(
        self,
        content: str,
        snap_id: Any,
        entities: dict[str, Entity],
        revisions: list[EntityRevision],
        mappings: list[EntityMapping],
        claims: list[Claim],
        evidence: list[ClaimEvidence],
        warnings: list[ImportWarning],
    ) -> None:
        try:
            data = json.loads(content)
        except json.JSONDecodeError as err:
            raise BiomedicalValidationError(f"Invalid JSON in Reactome artifact: {err}") from err

        pathways = data.get("pathways", data if isinstance(data, list) else [])
        for p in pathways:
            p_id = p.get("id") or p.get("stId") or p.get("pathway_id")
            if not p_id:
                continue
            curie = _normalize_reactome_id(p_id)
            name = p.get("name") or p.get("displayName") or curie
            species = p.get("species", "Homo sapiens")
            definition = p.get("definition") or p.get("summation") or ""

            ent_id = entity_uuid(EntityType.PATHWAY, curie)
            entities[curie] = Entity(
                id=ent_id,
                primary_curie=curie,
                entity_type=EntityType.PATHWAY,
                canonical_name=name,
                created_in_snapshot_id=snap_id,
            )

            rev_id = entity_revision_uuid(ent_id, snap_id)
            revisions.append(
                EntityRevision(
                    id=rev_id,
                    entity_id=ent_id,
                    snapshot_id=snap_id,
                    label=name,
                    definition=definition,
                    source_record_id=curie,
                    attributes={"species": species},
                )
            )

            # Subpathway parent relations
            parents = p.get("parents", p.get("hasPart", []))
            for parent in parents:
                parent_curie = _normalize_reactome_id(parent)
                c_id = claim_uuid(curie, Predicate.PART_OF, parent_curie)
                claims.append(
                    Claim(
                        id=c_id,
                        subject_curie=curie,
                        predicate=Predicate.PART_OF,
                        object_curie=parent_curie,
                    )
                )

            # Participant genes / proteins
            participants = p.get("genes", p.get("participants", []))
            for gene in participants:
                gene_symbol = gene.get("symbol") if isinstance(gene, dict) else str(gene)
                if not gene_symbol:
                    continue
                gene_curie = normalize_curie(
                    gene_symbol if ":" in gene_symbol else f"HGNC:{gene_symbol}"
                )

                if gene_curie not in entities:
                    g_ent_id = entity_uuid(EntityType.GENE, gene_curie)
                    entities[gene_curie] = Entity(
                        id=g_ent_id,
                        primary_curie=gene_curie,
                        entity_type=EntityType.GENE,
                        canonical_name=gene_symbol.split(":")[-1],
                        created_in_snapshot_id=snap_id,
                    )
                    revisions.append(
                        EntityRevision(
                            id=entity_revision_uuid(g_ent_id, snap_id),
                            entity_id=g_ent_id,
                            snapshot_id=snap_id,
                            label=gene_symbol.split(":")[-1],
                            source_record_id=gene_curie,
                        )
                    )

                claim_id = claim_uuid(gene_curie, Predicate.INVOLVES_PATHWAY, curie)
                claims.append(
                    Claim(
                        id=claim_id,
                        subject_curie=gene_curie,
                        predicate=Predicate.INVOLVES_PATHWAY,
                        object_curie=curie,
                    )
                )
                ev_id = claim_evidence_uuid(
                    claim_id, snap_id, EvidenceDirection.SUPPORTING, f"{gene_curie}->{curie}"
                )
                evidence.append(
                    ClaimEvidence(
                        id=ev_id,
                        claim_id=claim_id,
                        snapshot_id=snap_id,
                        direction=EvidenceDirection.SUPPORTING,
                        source_record_id=f"{gene_curie}->{curie}",
                        evidence_type="reactome_pathway_participation",
                        confidence_score=1.0,
                    )
                )

    def _parse_tsv_content(
        self,
        content: str,
        snap_id: Any,
        entities: dict[str, Entity],
        revisions: list[EntityRevision],
        mappings: list[EntityMapping],
        claims: list[Claim],
        evidence: list[ClaimEvidence],
        warnings: list[ImportWarning],
    ) -> None:
        for line in content.splitlines():
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            parts = line.split("\t")
            if len(parts) >= 3:
                # Format: Identifier \t Pathway_ID \t URL \t Pathway_Name \t Evidence_Code \t Species
                gene_id, p_id = parts[0].strip(), parts[1].strip()
                p_name = parts[3].strip() if len(parts) > 3 else p_id
                species = parts[5].strip() if len(parts) > 5 else "Homo sapiens"

                p_curie = _normalize_reactome_id(p_id)
                if p_curie not in entities:
                    ent_id = entity_uuid(EntityType.PATHWAY, p_curie)
                    entities[p_curie] = Entity(
                        id=ent_id,
                        primary_curie=p_curie,
                        entity_type=EntityType.PATHWAY,
                        canonical_name=p_name,
                        created_in_snapshot_id=snap_id,
                    )
                    revisions.append(
                        EntityRevision(
                            id=entity_revision_uuid(ent_id, snap_id),
                            entity_id=ent_id,
                            snapshot_id=snap_id,
                            label=p_name,
                            source_record_id=p_curie,
                            attributes={"species": species},
                        )
                    )

                if gene_id:
                    gene_curie = normalize_curie(
                        gene_id if ":" in gene_id else f"UNIPROT:{gene_id}"
                    )
                    if gene_curie not in entities:
                        g_ent_id = entity_uuid(EntityType.GENE, gene_curie)
                        entities[gene_curie] = Entity(
                            id=g_ent_id,
                            primary_curie=gene_curie,
                            entity_type=EntityType.GENE,
                            canonical_name=gene_id.split(":")[-1],
                            created_in_snapshot_id=snap_id,
                        )
                        revisions.append(
                            EntityRevision(
                                id=entity_revision_uuid(g_ent_id, snap_id),
                                entity_id=g_ent_id,
                                snapshot_id=snap_id,
                                label=gene_id.split(":")[-1],
                                source_record_id=gene_curie,
                            )
                        )

                    c_id = claim_uuid(gene_curie, Predicate.INVOLVES_PATHWAY, p_curie)
                    claims.append(
                        Claim(
                            id=c_id,
                            subject_curie=gene_curie,
                            predicate=Predicate.INVOLVES_PATHWAY,
                            object_curie=p_curie,
                        )
                    )
                    ev_id = claim_evidence_uuid(
                        c_id, snap_id, EvidenceDirection.SUPPORTING, f"{gene_curie}->{p_curie}"
                    )
                    evidence.append(
                        ClaimEvidence(
                            id=ev_id,
                            claim_id=c_id,
                            snapshot_id=snap_id,
                            direction=EvidenceDirection.SUPPORTING,
                            source_record_id=f"{gene_curie}->{p_curie}",
                            evidence_type="reactome_tsv_mapping",
                            confidence_score=1.0,
                        )
                    )
