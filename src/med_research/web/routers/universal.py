"""Versioned universal biomedical condition API."""

from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, HTTPException, Query

from med_research.biomed.analytics.duckdb_engine import DuckDBBiomedicalEngine
from med_research.biomed.comparison.service import ConditionComparisonService
from med_research.biomed.errors import BiomedicalValidationError
from med_research.biomed.identifiers import normalize_curie
from med_research.biomed.models import EvidenceDirection, Predicate
from med_research.web.dependencies_biomed import BiomedicalRepositoryDep
from med_research.web.models.universal import (
    AnalyticsSharedMechanismView,
    AnalyticsStatsView,
    AnalyticsSubgraphEdgeView,
    AnalyticsSubgraphView,
    AnalyticsTargetView,
    ComparisonRequest,
    ComparisonResultView,
    ConditionClaimView,
    ConditionHierarchy,
    ConditionSummary,
    EntitySummaryView,
    ImportReportView,
    PagedResponse,
    SnapshotSummary,
)
from med_research.web.services import comparison_service, universal_service

router = APIRouter(prefix="/api/v1", tags=["Universal Biomedical"])

PredicateQuery = Annotated[Predicate | None, Query()]
EvidenceDirectionQuery = Annotated[EvidenceDirection | None, Query()]
ResourceNameQuery = Annotated[str | None, Query()]


@router.get("/conditions/search", response_model=PagedResponse[EntitySummaryView])
def search_conditions(
    repository: BiomedicalRepositoryDep,
    q: str = Query(..., min_length=1, max_length=500),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
) -> PagedResponse[EntitySummaryView]:
    try:
        return universal_service.search_conditions(repository, q, limit=limit, offset=offset)
    except BiomedicalValidationError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.get("/conditions/{curie}", response_model=ConditionSummary)
def get_condition(
    curie: str,
    repository: BiomedicalRepositoryDep,
) -> ConditionSummary:
    summary = universal_service.get_condition(repository, normalize_curie(curie))
    if summary is None:
        raise HTTPException(status_code=404, detail=f"Condition '{curie}' not found")
    return summary


@router.get("/conditions/{curie}/hierarchy", response_model=ConditionHierarchy)
def get_condition_hierarchy(
    curie: str,
    repository: BiomedicalRepositoryDep,
    depth: int = Query(1, ge=0, le=3),
) -> ConditionHierarchy:
    hierarchy = universal_service.get_hierarchy(repository, normalize_curie(curie), depth=depth)
    if hierarchy is None:
        raise HTTPException(status_code=404, detail=f"Condition '{curie}' not found")
    return hierarchy


@router.get("/conditions/{curie}/claims", response_model=PagedResponse[ConditionClaimView])
def list_condition_claims(
    curie: str,
    repository: BiomedicalRepositoryDep,
    predicate: PredicateQuery = None,
    evidence_direction: EvidenceDirectionQuery = None,
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
) -> PagedResponse[ConditionClaimView]:
    try:
        return universal_service.list_condition_claims(
            repository,
            normalize_curie(curie),
            predicate=predicate,
            evidence_direction=evidence_direction,
            limit=limit,
            offset=offset,
        )
    except BiomedicalValidationError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.get("/snapshots", response_model=PagedResponse[SnapshotSummary])
def list_snapshots(
    repository: BiomedicalRepositoryDep,
    resource: ResourceNameQuery = None,
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
) -> PagedResponse[SnapshotSummary]:
    try:
        return universal_service.list_snapshots(
            repository,
            resource_name=resource,
            limit=limit,
            offset=offset,
        )
    except BiomedicalValidationError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.get("/snapshots/{snapshot_id}/report", response_model=ImportReportView)
def get_snapshot_report(
    snapshot_id: UUID,
    repository: BiomedicalRepositoryDep,
) -> ImportReportView:
    report = universal_service.get_import_report(repository, snapshot_id)
    if report is None:
        raise HTTPException(status_code=404, detail=f"Snapshot '{snapshot_id}' not found")
    return report


@router.post("/comparisons", response_model=ComparisonResultView)
def compare_conditions(
    payload: ComparisonRequest,
    repository: BiomedicalRepositoryDep,
) -> ComparisonResultView:
    try:
        config = comparison_service.build_similarity_config(payload.weights)
        result = ConditionComparisonService(repository).compare(
            normalize_curie(payload.left_curie),
            normalize_curie(payload.right_curie),
            config,
        )
        return comparison_service.to_comparison_view(result)
    except BiomedicalValidationError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.get("/comparisons/{run_id}", response_model=ComparisonResultView)
def get_comparison_run(
    run_id: UUID,
    repository: BiomedicalRepositoryDep,
) -> ComparisonResultView:
    view = comparison_service.get_comparison_run(repository, run_id)
    if view is None:
        raise HTTPException(status_code=404, detail=f"Comparison run '{run_id}' not found")
    return view


@router.get("/analytics/stats", response_model=AnalyticsStatsView)
def get_analytics_stats(
    repository: BiomedicalRepositoryDep,
) -> AnalyticsStatsView:
    engine = DuckDBBiomedicalEngine(repository.database.path)
    stats = engine.get_summary_statistics()
    return AnalyticsStatsView(
        total_entities=stats.get("total_entities", 0),
        total_claims=stats.get("total_claims", 0),
        total_evidence=stats.get("total_evidence", 0),
        total_snapshots=stats.get("total_snapshots", 0),
        entity_type_distribution=stats.get("entity_type_distribution", {}),
        predicate_distribution=stats.get("predicate_distribution", {}),
    )


@router.get("/analytics/targets/{curie}", response_model=list[AnalyticsTargetView])
def prioritize_targets(
    curie: str,
    repository: BiomedicalRepositoryDep,
    top_k: int = Query(20, ge=1, le=100),
) -> list[AnalyticsTargetView]:
    engine = DuckDBBiomedicalEngine(repository.database.path)
    norm_curie = normalize_curie(curie)
    targets = engine.prioritize_targets_vectorized(norm_curie, top_k=top_k)
    return [
        AnalyticsTargetView(
            target_curie=t.target_curie,
            target_name=t.target_name,
            target_type=t.target_type,
            supporting_count=t.supporting_count,
            contradictory_count=t.contradictory_count,
            evidence_score=t.evidence_score,
            pathway_count=t.pathway_count,
            phenotype_count=t.phenotype_count,
        )
        for t in targets
    ]


@router.get("/analytics/shared-mechanisms", response_model=AnalyticsSharedMechanismView)
def get_shared_mechanisms(
    repository: BiomedicalRepositoryDep,
    left_curie: str = Query(...),
    right_curie: str = Query(...),
) -> AnalyticsSharedMechanismView:
    engine = DuckDBBiomedicalEngine(repository.database.path)
    left = normalize_curie(left_curie)
    right = normalize_curie(right_curie)
    res = engine.compute_shared_mechanisms(left, right)
    return AnalyticsSharedMechanismView(
        condition_a=res.condition_a,
        condition_b=res.condition_b,
        shared_pathways=res.shared_pathways,
        shared_genes=res.shared_genes,
        jaccard_similarity=res.jaccard_similarity,
    )


@router.get("/analytics/subgraph/{curie}", response_model=AnalyticsSubgraphView)
def get_subgraph(
    curie: str,
    repository: BiomedicalRepositoryDep,
    max_hops: int = Query(2, ge=1, le=4),
    limit: int = Query(100, ge=1, le=500),
) -> AnalyticsSubgraphView:
    engine = DuckDBBiomedicalEngine(repository.database.path)
    norm_curie = normalize_curie(curie)
    edges = engine.find_multi_hop_subgraph(norm_curie, max_hops=max_hops, limit=limit)
    return AnalyticsSubgraphView(
        root_curie=norm_curie,
        edges=[
            AnalyticsSubgraphEdgeView(
                source=e.source,
                predicate=e.predicate,
                target=e.target,
                evidence_count=e.evidence_count,
            )
            for e in edges
        ],
        edge_count=len(edges),
    )
