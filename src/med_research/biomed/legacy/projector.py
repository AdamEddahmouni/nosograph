"""Project legacy disease JSON graphs into canonical import bundles."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any
from uuid import UUID

from med_research.biomed.identifiers import (
    claim_evidence_uuid,
    claim_uuid,
    entity_revision_uuid,
    entity_uuid,
    mapping_uuid,
)
from med_research.biomed.imports.models import ImportWarning
from med_research.biomed.legacy.checksums import legacy_file_checksums
from med_research.biomed.legacy.manifest import legacy_manifest_entry
from med_research.biomed.models import (
    Claim,
    ClaimEvidence,
    Entity,
    EntityMapping,
    EntityRevision,
    EntityType,
    EvidenceDirection,
    MappingKind,
    Predicate,
)
from med_research.diseases.base import Disease

_LEGACY_LOCAL = re.compile(r"[^A-Za-z0-9._-]+")


@dataclass
class DiseaseProjection:
    disease_id: str
    mondo_curie: str
    entities: list[Entity] = field(default_factory=list)
    revisions: list[EntityRevision] = field(default_factory=list)
    mappings: list[EntityMapping] = field(default_factory=list)
    claims: list[Claim] = field(default_factory=list)
    evidence: list[ClaimEvidence] = field(default_factory=list)
    warnings: list[ImportWarning] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)


def project_disease(disease_id: str, *, snapshot_id: UUID) -> DiseaseProjection:
    manifest = legacy_manifest_entry(disease_id)
    disease = Disease(disease_id)
    profile = disease.profile
    mondo_curie = manifest.mondo_curie

    projection = DiseaseProjection(
        disease_id=disease_id,
        mondo_curie=mondo_curie,
        metadata={
            "legacy_id": disease_id,
            "display_name": manifest.display_name,
            "mondo_curie": mondo_curie,
            "file_checksums": legacy_file_checksums(disease_id),
        },
    )

    node_registry = _NodeRegistry(disease_id, mondo_curie, profile.kg_node_id, profile.name)
    _register_genes(disease, projection, snapshot_id, node_registry)
    _register_drugs(disease, projection, snapshot_id, node_registry)
    _register_pathways(disease, projection, snapshot_id, node_registry)
    _register_biomarkers(profile.hallmark_markers, projection, snapshot_id, node_registry)
    _register_legacy_mappings(disease_id, mondo_curie, profile, projection, snapshot_id)
    _project_relationships(disease, projection, snapshot_id, node_registry)
    _project_biomarker_claims(
        mondo_curie, profile.hallmark_markers, projection, snapshot_id, node_registry
    )

    return projection


def merge_projections(
    projections: list[DiseaseProjection],
    *,
    snapshot_id: UUID,
) -> tuple[
    list[Entity],
    list[EntityRevision],
    list[EntityMapping],
    list[Claim],
    list[ClaimEvidence],
    list[ImportWarning],
    dict[str, Any],
]:
    entities: dict[UUID, Entity] = {}
    revisions: dict[UUID, EntityRevision] = {}
    mappings: dict[UUID, EntityMapping] = {}
    claims: dict[UUID, Claim] = {}
    evidence: dict[UUID, ClaimEvidence] = {}
    warnings: list[ImportWarning] = []
    diseases: list[dict[str, Any]] = []

    for projection in projections:
        diseases.append(projection.metadata)
        for entity in projection.entities:
            entities[entity.id] = entity
        for revision in projection.revisions:
            revisions[revision.id] = _with_snapshot(revision, snapshot_id)
        for mapping in projection.mappings:
            mappings[mapping.id] = _with_snapshot_mapping(mapping, snapshot_id)
        for claim in projection.claims:
            claims[claim.id] = claim
        for evidence_item in projection.evidence:
            evidence[evidence_item.id] = _with_snapshot_evidence(evidence_item, snapshot_id)
        warnings.extend(projection.warnings)

    metadata = {"diseases": diseases}
    return (
        list(entities.values()),
        list(revisions.values()),
        list(mappings.values()),
        list(claims.values()),
        list(evidence.values()),
        warnings,
        metadata,
    )


class _NodeRegistry:
    def __init__(
        self,
        disease_id: str,
        mondo_curie: str,
        kg_node_id: str,
        profile_name: str,
    ) -> None:
        self._disease_id = disease_id
        self._nodes: dict[str, str] = {}
        self._register(kg_node_id, mondo_curie)
        self._register(profile_name, mondo_curie)
        self._register(disease_id, mondo_curie)

    def register(self, label: str, curie: str) -> None:
        self._register(label, curie)

    def resolve(self, label: str) -> str | None:
        key = label.strip()
        if not key:
            return None
        if key in self._nodes:
            return self._nodes[key]
        lowered = key.casefold()
        for candidate, curie in self._nodes.items():
            if candidate.casefold() == lowered:
                return curie
        return None

    def _register(self, label: str, curie: str) -> None:
        key = label.strip()
        if key:
            self._nodes[key] = curie


def _register_genes(
    disease: Disease,
    projection: DiseaseProjection,
    snapshot_id: UUID,
    registry: _NodeRegistry,
) -> None:
    for entry in disease.load_genes().get("genes", []):
        gene_id = str(entry.get("id", "")).strip()
        if not gene_id:
            continue
        curie = legacy_curie("gene", projection.disease_id, gene_id)
        registry.register(gene_id, curie)
        entity = Entity(
            id=entity_uuid(EntityType.GENE, curie),
            primary_curie=curie,
            entity_type=EntityType.GENE,
            created_in_snapshot_id=snapshot_id,
        )
        projection.entities.append(entity)
        projection.revisions.append(
            EntityRevision(
                id=entity_revision_uuid(entity.id, snapshot_id),
                entity_id=entity.id,
                snapshot_id=snapshot_id,
                label=str(entry.get("name", gene_id)),
                definition=str(entry.get("function", "")),
                synonyms=[gene_id] if gene_id != str(entry.get("name", "")) else [],
                source_record_id=f"genes.json:{gene_id}",
                audit={"legacy_id": gene_id, "chromosome": entry.get("chromosome", "")},
            )
        )
        projection.mappings.append(
            EntityMapping(
                id=mapping_uuid(
                    curie,
                    legacy_local_id(projection.disease_id, gene_id),
                    MappingKind.EXACT,
                    snapshot_id,
                ),
                subject_curie=curie,
                object_curie=legacy_local_id(projection.disease_id, gene_id),
                relation=MappingKind.EXACT,
                snapshot_id=snapshot_id,
                source_record_id=f"genes.json:{gene_id}",
            )
        )


def _register_drugs(
    disease: Disease,
    projection: DiseaseProjection,
    snapshot_id: UUID,
    registry: _NodeRegistry,
) -> None:
    for entry in disease.load_drugs().get("drugs", []):
        drug_id = str(entry.get("id", "")).strip()
        if not drug_id:
            continue
        curie = legacy_curie("drug", projection.disease_id, drug_id)
        registry.register(drug_id, curie)
        registry.register(str(entry.get("name", "")), curie)
        entity = Entity(
            id=entity_uuid(EntityType.INTERVENTION, curie),
            primary_curie=curie,
            entity_type=EntityType.INTERVENTION,
            created_in_snapshot_id=snapshot_id,
        )
        projection.entities.append(entity)
        projection.revisions.append(
            EntityRevision(
                id=entity_revision_uuid(entity.id, snapshot_id),
                entity_id=entity.id,
                snapshot_id=snapshot_id,
                label=str(entry.get("name", drug_id)),
                definition=str(entry.get("mechanism", "")),
                synonyms=[drug_id],
                source_record_id=f"drugs.json:{drug_id}",
                audit={
                    "legacy_id": drug_id,
                    "approval": entry.get("approval", ""),
                    "route": entry.get("route", ""),
                },
            )
        )
        projection.mappings.append(
            EntityMapping(
                id=mapping_uuid(
                    curie,
                    legacy_local_id(projection.disease_id, drug_id),
                    MappingKind.EXACT,
                    snapshot_id,
                ),
                subject_curie=curie,
                object_curie=legacy_local_id(projection.disease_id, drug_id),
                relation=MappingKind.EXACT,
                snapshot_id=snapshot_id,
                source_record_id=f"drugs.json:{drug_id}",
            )
        )


def _register_pathways(
    disease: Disease,
    projection: DiseaseProjection,
    snapshot_id: UUID,
    registry: _NodeRegistry,
) -> None:
    for entry in disease.load_pathways().get("pathways", []):
        pathway_id = str(entry.get("id", "")).strip()
        if not pathway_id:
            continue
        curie = legacy_curie("pathway", projection.disease_id, pathway_id)
        registry.register(pathway_id, curie)
        registry.register(str(entry.get("name", "")), curie)
        entity = Entity(
            id=entity_uuid(EntityType.PATHWAY, curie),
            primary_curie=curie,
            entity_type=EntityType.PATHWAY,
            created_in_snapshot_id=snapshot_id,
        )
        projection.entities.append(entity)
        projection.revisions.append(
            EntityRevision(
                id=entity_revision_uuid(entity.id, snapshot_id),
                entity_id=entity.id,
                snapshot_id=snapshot_id,
                label=str(entry.get("name", pathway_id)),
                definition=str(entry.get("description", "")),
                synonyms=[pathway_id],
                source_record_id=f"pathways.json:{pathway_id}",
                audit={"legacy_id": pathway_id},
            )
        )
        projection.mappings.append(
            EntityMapping(
                id=mapping_uuid(
                    curie,
                    legacy_local_id(projection.disease_id, pathway_id),
                    MappingKind.EXACT,
                    snapshot_id,
                ),
                subject_curie=curie,
                object_curie=legacy_local_id(projection.disease_id, pathway_id),
                relation=MappingKind.EXACT,
                snapshot_id=snapshot_id,
                source_record_id=f"pathways.json:{pathway_id}",
            )
        )


def _register_biomarkers(
    markers: list[str],
    projection: DiseaseProjection,
    snapshot_id: UUID,
    registry: _NodeRegistry,
) -> None:
    for marker in markers:
        marker_id = marker.strip()
        if not marker_id:
            continue
        curie = legacy_curie("biomarker", projection.disease_id, marker_id)
        registry.register(marker_id, curie)
        entity = Entity(
            id=entity_uuid(EntityType.BIOMARKER, curie),
            primary_curie=curie,
            entity_type=EntityType.BIOMARKER,
            created_in_snapshot_id=snapshot_id,
        )
        projection.entities.append(entity)
        projection.revisions.append(
            EntityRevision(
                id=entity_revision_uuid(entity.id, snapshot_id),
                entity_id=entity.id,
                snapshot_id=snapshot_id,
                label=marker_id,
                source_record_id=f"profile.json:hallmark_markers:{marker_id}",
            )
        )


def _register_legacy_mappings(
    disease_id: str,
    mondo_curie: str,
    profile: Any,
    projection: DiseaseProjection,
    snapshot_id: UUID,
) -> None:
    projection.mappings.append(
        EntityMapping(
            id=mapping_uuid(
                mondo_curie, legacy_local_id(disease_id, disease_id), MappingKind.EXACT, snapshot_id
            ),
            subject_curie=mondo_curie,
            object_curie=legacy_local_id(disease_id, disease_id),
            relation=MappingKind.EXACT,
            snapshot_id=snapshot_id,
            source_record_id=f"profile.json:id:{disease_id}",
        )
    )
    kg_node_id = profile.kg_node_id.strip()
    if kg_node_id and kg_node_id.casefold() not in {disease_id.casefold(), profile.name.casefold()}:
        projection.mappings.append(
            EntityMapping(
                id=mapping_uuid(
                    mondo_curie,
                    legacy_local_id(disease_id, kg_node_id),
                    MappingKind.EXACT,
                    snapshot_id,
                ),
                subject_curie=mondo_curie,
                object_curie=legacy_local_id(disease_id, kg_node_id),
                relation=MappingKind.EXACT,
                snapshot_id=snapshot_id,
                source_record_id=f"profile.json:kg_node_id:{kg_node_id}",
            )
        )


def _project_relationships(
    disease: Disease,
    projection: DiseaseProjection,
    snapshot_id: UUID,
    registry: _NodeRegistry,
) -> None:
    for index, row in enumerate(disease.load_relationships().get("relationships", []), start=1):
        source = str(row.get("source", "")).strip()
        target = str(row.get("target", "")).strip()
        rel_type = str(row.get("type", "")).strip().upper()
        description = str(row.get("description", "")).strip()
        source_record_id = f"relationships.json:{index}"

        mapped = _map_relationship(
            projection.mondo_curie,
            source,
            target,
            rel_type,
            description,
            registry,
        )
        if mapped is None:
            projection.warnings.append(
                ImportWarning(
                    code="unsupported_predicate",
                    message=(
                        f"Could not map relationship {rel_type} from {source!r} to {target!r}"
                    ),
                    source_record_id=source_record_id,
                )
            )
            continue

        subject_curie, predicate, object_curie, qualifiers = mapped
        claim = Claim(
            id=claim_uuid(subject_curie, predicate, object_curie, qualifiers),
            subject_curie=subject_curie,
            object_curie=object_curie,
            predicate=predicate,
            qualifiers=qualifiers,
        )
        projection.claims.append(claim)
        projection.evidence.append(
            ClaimEvidence(
                id=claim_evidence_uuid(
                    claim.id,
                    snapshot_id,
                    EvidenceDirection.SUPPORTING,
                    source_record_id,
                ),
                claim_id=claim.id,
                snapshot_id=snapshot_id,
                direction=EvidenceDirection.SUPPORTING,
                source_record_id=source_record_id,
                rationale=description,
                extraction_method="legacy-migration",
            )
        )


def _project_biomarker_claims(
    mondo_curie: str,
    markers: list[str],
    projection: DiseaseProjection,
    snapshot_id: UUID,
    registry: _NodeRegistry,
) -> None:
    for marker in markers:
        marker_id = marker.strip()
        if not marker_id:
            continue
        object_curie = registry.resolve(marker_id)
        if object_curie is None:
            continue
        claim = Claim(
            id=claim_uuid(mondo_curie, Predicate.HAS_BIOMARKER, object_curie, {}),
            subject_curie=mondo_curie,
            object_curie=object_curie,
            predicate=Predicate.HAS_BIOMARKER,
        )
        source_record_id = f"profile.json:hallmark_markers:{marker_id}"
        projection.claims.append(claim)
        projection.evidence.append(
            ClaimEvidence(
                id=claim_evidence_uuid(
                    claim.id,
                    snapshot_id,
                    EvidenceDirection.SUPPORTING,
                    source_record_id,
                ),
                claim_id=claim.id,
                snapshot_id=snapshot_id,
                direction=EvidenceDirection.SUPPORTING,
                source_record_id=source_record_id,
                extraction_method="legacy-migration",
            )
        )


def _map_relationship(
    mondo_curie: str,
    source: str,
    target: str,
    rel_type: str,
    description: str,
    registry: _NodeRegistry,
) -> tuple[str, Predicate, str, dict[str, Any]] | None:
    source_curie = registry.resolve(source)
    target_curie = registry.resolve(target)
    qualifiers: dict[str, Any] = {"legacy_type": rel_type}
    if description:
        qualifiers["description"] = description

    if rel_type == "TARGETS":
        if source_curie is None or target_curie is None:
            return None
        return source_curie, Predicate.ASSOCIATED_WITH_GENE, target_curie, qualifiers

    if rel_type == "TREATS":
        if source_curie is None:
            return None
        condition_curie = target_curie or mondo_curie
        return condition_curie, Predicate.TREATED_BY, source_curie, qualifiers

    if rel_type == "ASSOCIATED_WITH":
        if source_curie is None:
            return None
        condition_curie = target_curie or mondo_curie
        return condition_curie, Predicate.ASSOCIATED_WITH_GENE, source_curie, qualifiers

    if rel_type == "PARTICIPATES_IN":
        if source_curie is None or target_curie is None:
            return None
        return source_curie, Predicate.INVOLVES_PATHWAY, target_curie, qualifiers

    if rel_type == "MODULATES":
        if source_curie is None or target_curie is None:
            return None
        qualifiers["modulation"] = True
        return source_curie, Predicate.INVOLVES_PATHWAY, target_curie, qualifiers

    if rel_type == "DRIVES":
        if target_curie is None and registry.resolve(target) is None:
            condition_curie = mondo_curie
        else:
            condition_curie = target_curie or mondo_curie
        pathway_curie = source_curie
        if pathway_curie is None:
            return None
        qualifiers["driver"] = True
        return condition_curie, Predicate.INVOLVES_PATHWAY, pathway_curie, qualifiers

    return None


def legacy_curie(kind: str, disease_id: str, local_id: str) -> str:
    return f"LEGACY-{kind.upper()}:{disease_id}-{_sanitize_local_id(local_id)}"


def legacy_local_id(disease_id: str, local_id: str) -> str:
    return f"LEGACY-LOCAL:{disease_id}-{_sanitize_local_id(local_id)}"


def _sanitize_local_id(value: str) -> str:
    sanitized = _LEGACY_LOCAL.sub("-", value.strip())
    return sanitized.strip("-") or "unknown"


def _with_snapshot(revision: EntityRevision, snapshot_id: UUID) -> EntityRevision:
    if revision.snapshot_id == snapshot_id:
        return revision
    return revision.model_copy(
        update={
            "id": entity_revision_uuid(revision.entity_id, snapshot_id),
            "snapshot_id": snapshot_id,
        }
    )


def _with_snapshot_mapping(mapping: EntityMapping, snapshot_id: UUID) -> EntityMapping:
    if mapping.snapshot_id == snapshot_id:
        return mapping
    return mapping.model_copy(
        update={
            "id": mapping_uuid(
                mapping.subject_curie,
                mapping.object_curie,
                mapping.relation,
                snapshot_id,
            ),
            "snapshot_id": snapshot_id,
        }
    )


def _with_snapshot_evidence(evidence: ClaimEvidence, snapshot_id: UUID) -> ClaimEvidence:
    if evidence.snapshot_id == snapshot_id:
        return evidence
    return evidence.model_copy(
        update={
            "id": claim_evidence_uuid(
                evidence.claim_id,
                snapshot_id,
                evidence.direction,
                evidence.source_record_id,
            ),
            "snapshot_id": snapshot_id,
        }
    )
