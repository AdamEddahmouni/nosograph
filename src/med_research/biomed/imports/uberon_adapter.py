"""UBERON Anatomical Ontology & Cell Ontology (CL) import adapter."""

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

_UBERON_CL_PATTERN = re.compile(
    r"^(?:http://purl\.obolibrary\.org/obo/)?(?:(UBERON|CL)[:_])(\d+)$", re.IGNORECASE
)


def _normalize_anatomy_curie(raw_id: str) -> str:
    match = _UBERON_CL_PATTERN.match(raw_id.strip())
    if match:
        prefix = match.group(1).upper()
        return f"{prefix}:{match.group(2)}"
    if raw_id.upper().startswith(("UBERON:", "CL:")):
        return normalize_curie(raw_id)
    raise ValueError(f"Invalid UBERON/CL identifier: {raw_id}")


class UberonImportAdapter(ImportAdapter):
    """Adapter for importing UBERON anatomy and Cell Ontology (CL) terms, hierarchies, and expression mappings."""

    @property
    def resource_name(self) -> str:
        return "uberon"

    @property
    def supported_formats(self) -> tuple[str, ...]:
        return ("json", "obo")

    def parse(
        self,
        path: Path,
        policy: ResourcePolicy,
        **kwargs: object,
    ) -> ImportBundle:
        raw_text = path.read_text(encoding="utf-8")
        checksum = hashlib.sha256(raw_text.encode("utf-8")).hexdigest()
        version = str(kwargs.get("version", "2026-01"))
        snap_id = snapshot_uuid(self.resource_name, version, checksum)

        snapshot = ResourceSnapshot(
            id=snap_id,
            resource_name=self.resource_name,
            version=version,
            checksum=checksum,
            name="UBERON Anatomy and Cell Ontology",
            namespace_prefix="UBERON",
            source_url=str(kwargs.get("source_url") or "http://uberon.org"),
            upstream_version=version,
            artifact_format=path.suffix.lstrip("."),
            license_id="CC-BY-3.0",
            license_spdx="CC-BY-3.0",
            redistribution_policy=policy.redistribution_policy or "permitted",
            importer_name="UberonImportAdapter",
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
            self._parse_obo_content(
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
            raise BiomedicalValidationError(f"Invalid JSON in UBERON artifact: {err}") from err

        nodes = data.get("nodes", data.get("graphs", [{}])[0].get("nodes", []))
        edges = data.get("edges", data.get("graphs", [{}])[0].get("edges", []))
        expression_records = data.get("expression_annotations", data.get("gtex_expression", []))

        for node in nodes:
            raw_id = node.get("id", "")
            if not raw_id:
                continue
            try:
                curie = _normalize_anatomy_curie(raw_id)
            except ValueError:
                continue

            entity_type = EntityType.CELL_TYPE if curie.startswith("CL:") else EntityType.ANATOMY
            label = node.get("lbl") or node.get("label") or curie
            meta = node.get("meta", {})
            definition_obj = meta.get("definition", {})
            definition = (
                definition_obj.get("val", "")
                if isinstance(definition_obj, dict)
                else str(node.get("definition", ""))
            )
            raw_synonyms = meta.get("synonyms", node.get("synonyms", []))
            synonyms: list[str] = [
                str(s.get("val") if isinstance(s, dict) else s)
                for s in raw_synonyms
                if s
            ]
            obsolete = bool(meta.get("deprecated", node.get("is_obsolete", False)))

            ent_id = entity_uuid(entity_type, curie)
            entities[curie] = Entity(
                id=ent_id,
                primary_curie=curie,
                entity_type=entity_type,
                canonical_name=label,
                created_in_snapshot_id=snap_id,
            )

            rev_id = entity_revision_uuid(ent_id, snap_id)
            revisions.append(
                EntityRevision(
                    id=rev_id,
                    entity_id=ent_id,
                    snapshot_id=snap_id,
                    label=label,
                    definition=definition,
                    synonyms=synonyms,
                    obsolete=obsolete,
                    source_record_id=curie,
                )
            )

        for edge in edges:
            sub = edge.get("sub", edge.get("subject", ""))
            pred_raw = edge.get("pred", edge.get("predicate", "is_a"))
            obj = edge.get("obj", edge.get("object", ""))
            try:
                sub_curie = _normalize_anatomy_curie(sub)
                obj_curie = _normalize_anatomy_curie(obj)
            except ValueError:
                continue

            pred_str = str(pred_raw).lower()
            if "part_of" in pred_str or "partof" in pred_str:
                predicate = Predicate.PART_OF
            elif "located_in" in pred_str or "locatedin" in pred_str:
                predicate = Predicate.LOCATED_IN
            else:
                predicate = Predicate.IS_A

            c_id = claim_uuid(sub_curie, predicate, obj_curie)
            claims.append(
                Claim(
                    id=c_id,
                    subject_curie=sub_curie,
                    predicate=predicate,
                    object_curie=obj_curie,
                )
            )

        for exp in expression_records:
            gene = exp.get("gene") or exp.get("gene_symbol")
            tissue = exp.get("tissue") or exp.get("uberon_id") or exp.get("anatomy")
            if not gene or not tissue:
                continue
            try:
                tissue_curie = _normalize_anatomy_curie(tissue)
                gene_curie = normalize_curie(gene if ":" in gene else f"HGNC:{gene}")
            except ValueError:
                continue

            if gene_curie not in entities:
                g_ent_id = entity_uuid(EntityType.GENE, gene_curie)
                entities[gene_curie] = Entity(
                    id=g_ent_id,
                    primary_curie=gene_curie,
                    entity_type=EntityType.GENE,
                    canonical_name=gene.split(":")[-1],
                    created_in_snapshot_id=snap_id,
                )
                revisions.append(
                    EntityRevision(
                        id=entity_revision_uuid(g_ent_id, snap_id),
                        entity_id=g_ent_id,
                        snapshot_id=snap_id,
                        label=gene.split(":")[-1],
                        source_record_id=gene_curie,
                    )
                )

            claim_id = claim_uuid(gene_curie, Predicate.EXPRESSED_IN, tissue_curie)
            claims.append(
                Claim(
                    id=claim_id,
                    subject_curie=gene_curie,
                    predicate=Predicate.EXPRESSED_IN,
                    object_curie=tissue_curie,
                )
            )
            ev_id = claim_evidence_uuid(
                claim_id, snap_id, EvidenceDirection.SUPPORTING, f"{gene_curie}->{tissue_curie}"
            )
            evidence.append(
                ClaimEvidence(
                    id=ev_id,
                    claim_id=claim_id,
                    snapshot_id=snap_id,
                    direction=EvidenceDirection.SUPPORTING,
                    source_record_id=f"{gene_curie}->{tissue_curie}",
                    evidence_type="tissue_expression",
                    confidence_score=float(exp.get("tpm", exp.get("score", 1.0))),
                )
            )

    def _parse_obo_content(
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
        lines = content.splitlines()
        current_term: dict[str, Any] | None = None

        for line in lines:
            line = line.strip()
            if not line or line.startswith("!"):
                continue

            if line == "[Term]":
                if current_term and "id" in current_term:
                    self._commit_obo_term(current_term, snap_id, entities, revisions, claims)
                current_term = {"is_a": [], "part_of": [], "synonyms": []}
            elif current_term is not None:
                if line.startswith("id:"):
                    current_term["id"] = line.split("id:", 1)[1].strip()
                elif line.startswith("name:"):
                    current_term["name"] = line.split("name:", 1)[1].strip()
                elif line.startswith("def:"):
                    match = re.search(r'"([^"]*)"', line)
                    if match:
                        current_term["def"] = match.group(1)
                elif line.startswith("is_a:"):
                    parent = line.split("is_a:", 1)[1].split("!", 1)[0].strip()
                    current_term["is_a"].append(parent)
                elif line.startswith("relationship: part_of"):
                    part = line.split("relationship: part_of", 1)[1].split("!", 1)[0].strip()
                    current_term["part_of"].append(part)
                elif line.startswith("synonym:"):
                    match = re.search(r'"([^"]*)"', line)
                    if match:
                        current_term["synonyms"].append(match.group(1))

        if current_term and "id" in current_term:
            self._commit_obo_term(current_term, snap_id, entities, revisions, claims)

    def _commit_obo_term(
        self,
        term: dict[str, Any],
        snap_id: Any,
        entities: dict[str, Entity],
        revisions: list[EntityRevision],
        claims: list[Claim],
    ) -> None:
        try:
            curie = _normalize_anatomy_curie(term["id"])
        except ValueError:
            return

        entity_type = EntityType.CELL_TYPE if curie.startswith("CL:") else EntityType.ANATOMY
        label = term.get("name", curie)
        definition = term.get("def", "")
        synonyms = term.get("synonyms", [])

        ent_id = entity_uuid(entity_type, curie)
        entities[curie] = Entity(
            id=ent_id,
            primary_curie=curie,
            entity_type=entity_type,
            canonical_name=label,
            created_in_snapshot_id=snap_id,
        )

        revisions.append(
            EntityRevision(
                id=entity_revision_uuid(ent_id, snap_id),
                entity_id=ent_id,
                snapshot_id=snap_id,
                label=label,
                definition=definition,
                synonyms=synonyms,
                source_record_id=curie,
            )
        )

        for parent in term.get("is_a", []):
            try:
                p_curie = _normalize_anatomy_curie(parent)
                c_id = claim_uuid(curie, Predicate.IS_A, p_curie)
                claims.append(
                    Claim(
                        id=c_id,
                        subject_curie=curie,
                        predicate=Predicate.IS_A,
                        object_curie=p_curie,
                    )
                )
            except ValueError:
                pass

        for part in term.get("part_of", []):
            try:
                part_curie = _normalize_anatomy_curie(part)
                c_id = claim_uuid(curie, Predicate.PART_OF, part_curie)
                claims.append(
                    Claim(
                        id=c_id,
                        subject_curie=curie,
                        predicate=Predicate.PART_OF,
                        object_curie=part_curie,
                    )
                )
            except ValueError:
                pass
