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
    ClaimEvidenceView,
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
