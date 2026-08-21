"""Query service for the versioned universal biomedical API."""

from __future__ import annotations

from collections import deque
from uuid import UUID

from med_research.biomed.legacy.compat import legacy_projection_enabled
from med_research.biomed.legacy.manifest import LEGACY_DISEASE_MONDO_MAP
from med_research.biomed.models import (
    ClaimEvidence,
    EntityType,
    EvidenceDirection,
    Predicate,
    ResourceSnapshot,
)
from med_research.biomed.repository import BiomedicalRepository, ClaimView
from med_research.web.models.universal import (
    ClaimDetailView,
    ClaimEvidenceDetailView,
    ClaimEvidenceView,
    ClaimProvenanceStepView,
    ConditionClaimView,
    ConditionHierarchy,
    ConditionSummary,
    EntityMappingView,
    EntitySummaryView,
    EntityTypeLiteral,
    HierarchyNode,
    ImportReportView,
    PagedResponse,
    ReadinessBadge,
    ResearchDisclaimer,
    SnapshotSummary,
)

_DISCLAIMER = ResearchDisclaimer()


def search_conditions(
    repository: BiomedicalRepository,
    query: str,
    *,
    limit: int = 50,
    offset: int = 0,
) -> PagedResponse[EntitySummaryView]:
    page = repository.search_entities(
        query,
        entity_type=EntityType.CONDITION,
        limit=limit,
        offset=offset,
    )
    items = [
        EntitySummaryView(
            curie=item.entity.primary_curie,
            label=item.label,
            entity_type=_entity_type_literal(item.entity.entity_type),
        )
        for item in page.items
    ]
    return PagedResponse(
        items=items,
        total=page.total,
        limit=page.limit,
        offset=page.offset,
        disclaimer=_DISCLAIMER,
    )


def get_condition(repository: BiomedicalRepository, curie: str) -> ConditionSummary | None:
    view = repository.get_entity(curie)
    if view is None or view.entity.entity_type is not EntityType.CONDITION:
        return None
    revision = view.revision
    label = revision.label if revision and revision.label else view.entity.primary_curie
    definition = revision.definition if revision else ""
    synonyms = list(revision.synonyms) if revision else []
    mappings = [
        EntityMappingView(
            subject_curie=mapping.subject_curie,
            object_curie=mapping.object_curie,
            relation=mapping.relation.value,
            can_auto_join=mapping.relation.can_auto_join,
            source_record_id=mapping.source_record_id or "",
        )
        for mapping in view.mappings
    ]
    active_ids = {snapshot.id for snapshot in repository.list_active_snapshots()}
    snapshots = [
        _snapshot_summary(snapshot, active=snapshot.id in active_ids)
        for snapshot in repository.list_active_snapshots()
    ]
    return ConditionSummary(
        curie=view.entity.primary_curie,
        label=label,
        entity_type=_entity_type_literal(view.entity.entity_type),
        definition=definition,
        synonyms=synonyms,
        mappings=mappings,
        snapshots=snapshots,
        readiness=_readiness_badge(repository, view.entity.primary_curie),
        disclaimer=_DISCLAIMER,
    )


def get_hierarchy(
    repository: BiomedicalRepository,
    curie: str,
    *,
    depth: int = 1,
) -> ConditionHierarchy | None:
    view = repository.get_entity(curie)
    if view is None or view.entity.entity_type is not EntityType.CONDITION:
        return None
    normalized = view.entity.primary_curie
    nodes: list[HierarchyNode] = [
        HierarchyNode(
            curie=normalized,
            label=_entity_label(repository, normalized),
            depth=0,
            relation="self",
        )
    ]
    if depth > 0:
        nodes.extend(_traverse_parents(repository, normalized, depth))
        nodes.extend(_traverse_children(repository, normalized, depth))
    return ConditionHierarchy(
        curie=normalized,
        depth_limit=depth,
        nodes=nodes,
        disclaimer=_DISCLAIMER,
    )


def list_condition_claims(
    repository: BiomedicalRepository,
    curie: str,
    *,
    predicate: Predicate | None = None,
    evidence_direction: EvidenceDirection | None = None,
    limit: int = 50,
    offset: int = 0,
) -> PagedResponse[ConditionClaimView]:
    claims = repository.list_claims(curie, predicate=predicate)
    items = [_claim_view(repository, claim_view) for claim_view in claims]
    if evidence_direction is not None:
        items = [
            item
            for item in items
            if (evidence_direction is EvidenceDirection.SUPPORTING and item.supporting_evidence)
            or (
                evidence_direction is EvidenceDirection.CONTRADICTORY
                and item.contradictory_evidence
            )
        ]
    total = len(items)
    page_items = items[offset : offset + limit]
    return PagedResponse(
        items=page_items,
        total=total,
        limit=limit,
        offset=offset,
        disclaimer=_DISCLAIMER,
    )


def list_snapshots(
    repository: BiomedicalRepository,
    *,
    resource_name: str | None = None,
    limit: int = 50,
    offset: int = 0,
) -> PagedResponse[SnapshotSummary]:
    page = repository.list_snapshots(resource_name=resource_name, limit=limit, offset=offset)
    active = {snapshot.id for snapshot in repository.list_active_snapshots()}
    items = [_snapshot_summary(snapshot, active=snapshot.id in active) for snapshot in page.items]
    return PagedResponse(
        items=items,
        total=page.total,
        limit=page.limit,
        offset=page.offset,
        disclaimer=_DISCLAIMER,
    )


def get_import_report(
    repository: BiomedicalRepository,
    snapshot_id: UUID,
) -> ImportReportView | None:
    snapshot = repository.get_snapshot(snapshot_id)
    if snapshot is None:
        return None
    warnings = [str(item) for item in snapshot.warnings]
    return ImportReportView(
        resource_name=snapshot.resource_name,
        snapshot_id=snapshot.id,
        version=snapshot.version,
        checksum=snapshot.checksum,
        counts=dict(snapshot.counts),
        warnings=warnings,
        fingerprint=snapshot.manifest_fingerprint,
        disclaimer=_DISCLAIMER,
    )


def get_claim_detail(repository: BiomedicalRepository, claim_id: UUID) -> ClaimDetailView | None:
    claim_view = repository.get_claim_by_id(claim_id)
    if claim_view is None:
        return None
    supporting = [
        _evidence_detail_view(repository, item)
        for item in claim_view.evidence
        if item.direction is EvidenceDirection.SUPPORTING
    ]
    contradictory = [
        _evidence_detail_view(repository, item)
        for item in claim_view.evidence
        if item.direction is EvidenceDirection.CONTRADICTORY
    ]
    summary = _evidence_summary(supporting, contradictory)
    provenance = _claim_provenance_steps(repository, claim_view)
    return ClaimDetailView(
        claim_id=claim_view.claim.id,
        predicate=claim_view.claim.predicate.value,
        subject_curie=claim_view.subject_curie,
        object_curie=claim_view.object_curie,
        subject_label=_entity_label(repository, claim_view.subject_curie),
        object_label=_entity_label(repository, claim_view.object_curie),
        qualifiers=dict(claim_view.claim.qualifiers),
        evidence_summary=summary,
        supporting_evidence=supporting,
        contradictory_evidence=contradictory,
        provenance=provenance,
        disclaimer=_DISCLAIMER,
    )


def list_claim_evidence(
    repository: BiomedicalRepository, claim_id: UUID
) -> list[ClaimEvidenceDetailView]:
    claim_view = repository.get_claim_by_id(claim_id)
    if claim_view is None:
        return []
    return [_evidence_detail_view(repository, item) for item in claim_view.evidence]


def get_claim_provenance(
    repository: BiomedicalRepository,
    claim_id: UUID,
) -> list[ClaimProvenanceStepView]:
    claim_view = repository.get_claim_by_id(claim_id)
    if claim_view is None:
        return []
    return _claim_provenance_steps(repository, claim_view)


def _evidence_summary(
    supporting: list[ClaimEvidenceDetailView],
    contradictory: list[ClaimEvidenceDetailView],
) -> str:
    if supporting and contradictory:
        return "INCONCLUSIVE"
    if supporting:
        return "SUPPORTS"
    if contradictory:
        return "CONTRADICTS"
    return "UNASSERTED"


def _confidence_explanation(evidence: ClaimEvidence) -> str:
    score = (
        evidence.confidence_score if evidence.confidence_score is not None else evidence.confidence
    )
    if score is None:
        return "No numeric confidence score recorded for this evidence item."
    label = evidence.strength_label or evidence.evidence_type or "evidence"
    return f"{label} confidence {score:.3f} from {evidence.extraction_method or 'imported source'}"


def _evidence_detail_view(
    repository: BiomedicalRepository,
    evidence: ClaimEvidence,
) -> ClaimEvidenceDetailView:
    direction = evidence.direction
    summary = "SUPPORTS" if direction is EvidenceDirection.SUPPORTING else "CONTRADICTS"
    snapshot = repository.get_snapshot(evidence.snapshot_id)
    provenance = [
        ClaimProvenanceStepView(
            stage="normalized_record",
            resource_name=snapshot.resource_name if snapshot else "",
            snapshot_id=evidence.snapshot_id,
            snapshot_version=snapshot.version if snapshot else "",
            checksum=snapshot.checksum if snapshot else "",
            source_record_id=evidence.source_record_id,
            source_url=evidence.source_url or "",
            importer=evidence.extraction_method or (snapshot.importer_name if snapshot else ""),
            retrieved_at=snapshot.retrieved_at if snapshot else None,
        )
    ]
    if snapshot is not None:
        provenance.insert(
            0,
            ClaimProvenanceStepView(
                stage="source_snapshot",
                resource_name=snapshot.resource_name,
                snapshot_id=snapshot.id,
                snapshot_version=snapshot.version,
                checksum=snapshot.checksum,
                source_url=snapshot.source_url,
                importer=snapshot.importer_name,
                retrieved_at=snapshot.retrieved_at,
            ),
        )
    return ClaimEvidenceDetailView(
        id=evidence.id,
        direction=direction.value,
        summary=summary,
        snapshot_id=evidence.snapshot_id,
        source_record_id=evidence.source_record_id,
        source_url=evidence.source_url or "",
        evidence_type=evidence.evidence_type or "",
        confidence=evidence.confidence_score
        if evidence.confidence_score is not None
        else evidence.confidence,
        confidence_explanation=_confidence_explanation(evidence),
        rationale=evidence.rationale or "",
        curator=evidence.curator or "",
        extraction_method=evidence.extraction_method or "",
        publication_date=evidence.publication_date or "",
        limitations=list(evidence.limitations),
        provenance=provenance,
    )


def _claim_provenance_steps(
    repository: BiomedicalRepository,
    claim_view: ClaimView,
) -> list[ClaimProvenanceStepView]:
    steps: list[ClaimProvenanceStepView] = []
    seen_snapshots: set[UUID] = set()
    for evidence in claim_view.evidence:
        snapshot = repository.get_snapshot(evidence.snapshot_id)
        if snapshot is None or snapshot.id in seen_snapshots:
            continue
        seen_snapshots.add(snapshot.id)
        steps.append(
            ClaimProvenanceStepView(
                stage="ingestion",
                resource_name=snapshot.resource_name,
                snapshot_id=snapshot.id,
                snapshot_version=snapshot.version,
                checksum=snapshot.checksum,
                source_url=snapshot.source_url,
                importer=snapshot.importer_name or evidence.extraction_method or "",
                retrieved_at=snapshot.retrieved_at,
            )
        )
    steps.sort(key=lambda item: (item.resource_name, str(item.snapshot_id or "")))
    steps.append(
        ClaimProvenanceStepView(
            stage="graph_claim",
            resource_name="biomed_store",
            source_record_id=str(claim_view.claim.id),
        )
    )
    return steps


def _snapshot_summary(snapshot: ResourceSnapshot, *, active: bool) -> SnapshotSummary:
    return SnapshotSummary(
        id=snapshot.id,
        resource_name=snapshot.resource_name,
        version=snapshot.version,
        checksum=snapshot.checksum,
        active=active,
        imported_at=snapshot.imported_at,
        counts=dict(snapshot.counts),
    )


def _readiness_badge(repository: BiomedicalRepository, curie: str) -> ReadinessBadge:
    ontology_present = repository.get_active_snapshot("mondo") is not None
    legacy_curated = legacy_projection_enabled(repository)
    legacy_disease_id = next(
        (disease_id for disease_id, mapped in LEGACY_DISEASE_MONDO_MAP.items() if mapped == curie),
        None,
    )
    if ontology_present and legacy_curated and legacy_disease_id:
        message = "Ontology and curated legacy module projections are available."
    elif ontology_present:
        message = "Ontology snapshot imported; curated legacy projections may be unavailable."
    else:
        message = "No active ontology snapshot; condition detail may be incomplete."
    return ReadinessBadge(
        ontology_present=ontology_present,
        legacy_curated=legacy_curated,
        legacy_disease_id=legacy_disease_id,
        message=message,
    )


def _entity_label(repository: BiomedicalRepository, curie: str) -> str:
    view = repository.get_entity(curie)
    if view is None:
        return curie
    if view.revision and view.revision.label:
        return view.revision.label
    return view.entity.primary_curie


def _traverse_parents(
    repository: BiomedicalRepository,
    curie: str,
    depth_limit: int,
) -> list[HierarchyNode]:
    nodes: list[HierarchyNode] = []
    queue: deque[tuple[str, int]] = deque([(curie, 0)])
    seen = {curie}
    while queue:
        current, current_depth = queue.popleft()
        if current_depth >= depth_limit:
            continue
        for claim_view in repository.list_claims(current, predicate=Predicate.IS_A):
            parent = claim_view.object_curie
            if parent in seen:
                continue
            seen.add(parent)
            nodes.append(
                HierarchyNode(
                    curie=parent,
                    label=_entity_label(repository, parent),
                    depth=current_depth + 1,
                    relation="parent",
                )
            )
            queue.append((parent, current_depth + 1))
    return nodes


def _traverse_children(
    repository: BiomedicalRepository,
    curie: str,
    depth_limit: int,
) -> list[HierarchyNode]:
    nodes: list[HierarchyNode] = []
    queue: deque[tuple[str, int]] = deque([(curie, 0)])
    seen = {curie}
    while queue:
        current, current_depth = queue.popleft()
        if current_depth >= depth_limit:
            continue
        for claim_view in repository.list_claims_by_object(current, predicate=Predicate.IS_A):
            child = claim_view.subject_curie
            if child in seen:
                continue
            seen.add(child)
            nodes.append(
                HierarchyNode(
                    curie=child,
                    label=_entity_label(repository, child),
                    depth=current_depth + 1,
                    relation="child",
                )
            )
            queue.append((child, current_depth + 1))
    return nodes


def _claim_view(repository: BiomedicalRepository, claim_view: ClaimView) -> ConditionClaimView:
    supporting = [
        _evidence_view(item)
        for item in claim_view.evidence
        if item.direction is EvidenceDirection.SUPPORTING
    ]
    contradictory = [
        _evidence_view(item)
        for item in claim_view.evidence
        if item.direction is EvidenceDirection.CONTRADICTORY
    ]
    return ConditionClaimView(
        claim_id=claim_view.claim.id,
        predicate=claim_view.claim.predicate.value,
        subject_curie=claim_view.subject_curie,
        object_curie=claim_view.object_curie,
        subject_label=_entity_label(repository, claim_view.subject_curie),
        object_label=_entity_label(repository, claim_view.object_curie),
        qualifiers=dict(claim_view.claim.qualifiers),
        supporting_evidence=supporting,
        contradictory_evidence=contradictory,
    )


def _entity_type_literal(entity_type: EntityType) -> EntityTypeLiteral:
    return entity_type.value


def _evidence_view(evidence: ClaimEvidence) -> ClaimEvidenceView:
    return ClaimEvidenceView(
        id=evidence.id,
        direction=evidence.direction.value,
        snapshot_id=evidence.snapshot_id,
        source_record_id=evidence.source_record_id,
        source_url=evidence.source_url or "",
        evidence_type=evidence.evidence_type or "",
        rationale=evidence.rationale or "",
    )
