"""Versioned universal biomedical condition API."""

from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, HTTPException, Query, Response

from med_research.biomed.analytics.duckdb_engine import DuckDBBiomedicalEngine
from med_research.biomed.comparison.service import ConditionComparisonService
from med_research.biomed.errors import BiomedicalValidationError
from med_research.biomed.identifiers import normalize_curie
from med_research.biomed.models import EvidenceDirection, Predicate
from med_research.biomed.nosograph_compare.service import (
    CompareRunIncompleteError,
    CompareRunNotFoundError,
    NosoGraphCompareService,
)
from med_research.web.dependencies_biomed import BiomedicalRepositoryDep
from med_research.web.models.universal import (
    AnalyticsSharedMechanismView,
    AnalyticsStatsView,
    AnalyticsSubgraphEdgeView,
    AnalyticsSubgraphView,
    AnalyticsTargetView,
    ClaimDetailView,
    ClaimEvidenceDetailView,
    ClaimProvenanceStepView,
    ComparisonRequest,
    ComparisonResultView,
    ConditionClaimView,
    ConditionHierarchy,
    ConditionSummary,
    EntitySummaryView,
    ImportReportView,
    NosoGraphCompareRequest,
    NosoGraphCompareResultView,
    NosoGraphCompareV2Request,
    NosoGraphCompareV2ResultView,
    PagedResponse,
    RelatedClaimView,
    SnapshotSummary,
)
from med_research.web.services import (
    comparison_service,
    nosograph_compare_service,
    universal_service,
)
from med_research.web.services.nosograph_compare_export import (
    render_json as render_compare_json,
)
from med_research.web.services.nosograph_compare_export import (
    render_markdown as render_compare_markdown,
)

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


@router.get("/claims/{claim_id}", response_model=ClaimDetailView)
def get_claim(
    claim_id: UUID,
    repository: BiomedicalRepositoryDep,
) -> ClaimDetailView:
    detail = universal_service.get_claim_detail(repository, claim_id)
    if detail is None:
        raise HTTPException(status_code=404, detail=f"Claim '{claim_id}' not found")
    return detail


@router.get("/claims/{claim_id}/evidence", response_model=PagedResponse[ClaimEvidenceDetailView])
def get_claim_evidence(
    claim_id: UUID,
    repository: BiomedicalRepositoryDep,
    direction: EvidenceDirectionQuery = None,
    evidence_type: str | None = Query(default=None, max_length=200),
    source: str | None = Query(default=None, max_length=200),
    species_context: str | None = Query(default=None, max_length=50),
    sort: str = Query(default="newest", pattern="^(newest|oldest|source)$"),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
) -> PagedResponse[ClaimEvidenceDetailView]:
    if repository.get_claim_by_id(claim_id) is None:
        raise HTTPException(status_code=404, detail=f"Claim '{claim_id}' not found")
    return universal_service.list_claim_evidence(
        repository,
        claim_id,
        direction=direction,
        evidence_type=evidence_type,
        source_name=source,
        species_context=species_context,
        sort=sort,
        limit=limit,
        offset=offset,
    )


@router.get("/claims/{claim_id}/related", response_model=list[RelatedClaimView])
def get_related_claims(
    claim_id: UUID,
    repository: BiomedicalRepositoryDep,
    limit: int = Query(20, ge=1, le=100),
) -> list[RelatedClaimView]:
    if repository.get_claim_by_id(claim_id) is None:
        raise HTTPException(status_code=404, detail=f"Claim '{claim_id}' not found")
    return universal_service.list_related_claims(repository, claim_id, limit=limit)


@router.get("/claims/{claim_id}/provenance", response_model=list[ClaimProvenanceStepView])
def get_claim_provenance(
    claim_id: UUID,
    repository: BiomedicalRepositoryDep,
) -> list[ClaimProvenanceStepView]:
    if repository.get_claim_by_id(claim_id) is None:
        raise HTTPException(status_code=404, detail=f"Claim '{claim_id}' not found")
    return universal_service.get_claim_provenance(repository, claim_id)


@router.post("/nosograph/compare", response_model=NosoGraphCompareResultView, deprecated=True)
def nosograph_compare(
    payload: NosoGraphCompareRequest,
    repository: BiomedicalRepositoryDep,
) -> NosoGraphCompareResultView:
    try:
        result = NosoGraphCompareService(repository).compare(
            normalize_curie(payload.left_curie),
            normalize_curie(payload.right_curie),
            dimensions=payload.dimensions,
        )
        return nosograph_compare_service.to_compare_view(result)
    except BiomedicalValidationError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.post("/nosograph/comparisons", response_model=NosoGraphCompareV2ResultView)
def nosograph_compare_v2(
    payload: NosoGraphCompareV2Request,
    repository: BiomedicalRepositoryDep,
) -> NosoGraphCompareV2ResultView:
    try:
        result = NosoGraphCompareService(repository).compare_many(
            payload.condition_curies,
            dimensions=payload.dimensions,
        )
        return nosograph_compare_service.to_compare_v2_view(result)
    except BiomedicalValidationError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


def _persisted_compare_view(
    run_id: UUID, repository: BiomedicalRepositoryDep
) -> NosoGraphCompareV2ResultView:
    try:
        result = NosoGraphCompareService(repository).get_comparison(run_id)
    except CompareRunNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except CompareRunIncompleteError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return nosograph_compare_service.to_compare_v2_view(result)


@router.get("/nosograph/comparisons/{run_id}", response_model=NosoGraphCompareV2ResultView)
def get_nosograph_comparison(
    run_id: UUID, repository: BiomedicalRepositoryDep
) -> NosoGraphCompareV2ResultView:
    return _persisted_compare_view(run_id, repository)


@router.get("/nosograph/comparisons/{run_id}/exports/json")
def export_nosograph_comparison_json(run_id: UUID, repository: BiomedicalRepositoryDep) -> Response:
    result = _persisted_compare_view(run_id, repository)
    filename = f"nosograph-comparison-{run_id}.json"
    return Response(
        content=render_compare_json(result),
        media_type="application/json",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get("/nosograph/comparisons/{run_id}/exports/markdown")
def export_nosograph_comparison_markdown(
    run_id: UUID, repository: BiomedicalRepositoryDep
) -> Response:
    result = _persisted_compare_view(run_id, repository)
    filename = f"nosograph-comparison-{run_id}.md"
    return Response(
        content=render_compare_markdown(result),
        media_type="text/markdown",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


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
