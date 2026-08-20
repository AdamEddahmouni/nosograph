"""Biomedical graph analytics and target prioritization API router."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Query

from med_research.biomed.graph_analytics import BiomedicalGraphAnalytics
from med_research.web.dependencies_biomed import BiomedicalRepositoryDep

router = APIRouter(prefix="/api/v1/biomed", tags=["Biomedical Analytics"])


@router.get("/pathways")
def find_claim_pathways(
    repository: BiomedicalRepositoryDep,
    start_curie: str = Query(..., description="Start node CURIE (e.g. MONDO:0007915)"),
    target_curie: str = Query(..., description="Target node CURIE (e.g. UNIPROT:P01375)"),
    max_depth: int = Query(3, ge=1, le=5),
    limit: int = Query(10, ge=1, le=50),
) -> dict[str, Any]:
    """Find claim-based path connections between two biomedical entities using BFS."""
    analytics = BiomedicalGraphAnalytics(repository)
    paths = analytics.find_shortest_paths(
        start_curie=start_curie,
        target_curie=target_curie,
        max_depth=max_depth,
        limit=limit,
    )
    return {
        "start_curie": start_curie,
        "target_curie": target_curie,
        "max_depth": max_depth,
        "total_paths": len(paths),
        "paths": [
            {
                "nodes": p.nodes,
                "predicates": p.predicates,
                "score": p.score,
            }
            for p in paths
        ],
    }


@router.get("/target-prioritization/{disease_curie}")
def prioritize_targets(
    disease_curie: str,
    repository: BiomedicalRepositoryDep,
    top_k: int = Query(10, ge=1, le=50),
) -> dict[str, Any]:
    """Rank disease targets based on canonical claim evidence, graph centrality, and 3D AlphaFold structure."""
    from med_research.pipeline.structure_3d.engine import get_target_3d_structure

    analytics = BiomedicalGraphAnalytics(repository)
    scores = analytics.prioritize_disease_targets(disease_curie=disease_curie, top_k=top_k)

    rankings = []
    for s in scores:
        struct = get_target_3d_structure(target_id=s.target_curie, gene_name=s.target_label)
        rankings.append(
            {
                "target_curie": s.target_curie,
                "target_label": s.target_label,
                "supporting_evidence": s.supporting_evidence_count,
                "contradictory_evidence": s.contradictory_evidence_count,
                "centrality_score": s.centrality_score,
                "vulnerability_score": s.combined_vulnerability_score,
                "plddt_score": struct.get("plddt_score", 0.0),
                "pocket_volume_A3": struct.get("pocket_volume_A3", 0.0),
                "docking_readiness_score": struct.get("docking_readiness_score", 0.0),
                "confidence_category": struct.get("confidence_category", "Unknown"),
                "druggability_tier": struct.get(
                    "druggability_tier", "Tier 2 (Moderate Druggability)"
                ),
                "uniprot_id": struct.get("uniprot_id", ""),
                "pdb_id": struct.get("pdb_id", ""),
                "structure_3d": struct,
            }
        )

    return {
        "disease_curie": disease_curie,
        "total_targets": len(scores),
        "rankings": rankings,
    }


@router.get("/structures/{target_identifier}")
def get_target_structure(
    target_identifier: str,
) -> dict[str, Any]:
    """Retrieve 3D protein structure, AlphaFold pLDDT scores, domain boundaries, and binding pocket details."""
    from med_research.pipeline.structure_3d.engine import get_target_3d_structure

    return get_target_3d_structure(target_id=target_identifier)


@router.get("/analytics/summary")
def get_graph_summary(
    repository: BiomedicalRepositoryDep,
) -> dict[str, Any]:
    """Get high-throughput DuckDB summary statistics across the canonical knowledge store."""
    analytics = BiomedicalGraphAnalytics(repository)
    engine = analytics.get_duckdb_engine()
    return engine.get_summary_statistics()


@router.get("/analytics/shared-mechanisms")
def get_shared_mechanisms(
    repository: BiomedicalRepositoryDep,
    curie_a: str = Query(..., description="Condition A CURIE (e.g. MONDO:0007915)"),
    curie_b: str = Query(..., description="Condition B CURIE (e.g. MONDO:0008383)"),
) -> dict[str, Any]:
    """Calculate shared biological pathways, genes, and Jaccard similarity between two conditions."""
    analytics = BiomedicalGraphAnalytics(repository)
    engine = analytics.get_duckdb_engine()
    res = engine.compute_shared_mechanisms(curie_a=curie_a, curie_b=curie_b)
    return {
        "condition_a": res.condition_a,
        "condition_b": res.condition_b,
        "shared_pathways": res.shared_pathways,
        "shared_genes": res.shared_genes,
        "jaccard_similarity": res.jaccard_similarity,
    }


@router.get("/analytics/subgraph")
def get_multi_hop_subgraph(
    repository: BiomedicalRepositoryDep,
    start_curie: str = Query(..., description="Start node CURIE (e.g. MONDO:0007915)"),
    max_hops: int = Query(2, ge=1, le=4),
    limit: int = Query(50, ge=1, le=200),
) -> dict[str, Any]:
    """Extract a multi-hop neighborhood subgraph around a starting node."""
    analytics = BiomedicalGraphAnalytics(repository)
    engine = analytics.get_duckdb_engine()
    paths = engine.find_multi_hop_subgraph(start_curie=start_curie, max_hops=max_hops, limit=limit)
    return {
        "start_curie": start_curie,
        "max_hops": max_hops,
        "total_edges": len(paths),
        "edges": [
            {
                "source": p.source,
                "predicate": p.predicate,
                "target": p.target,
                "evidence_count": p.evidence_count,
            }
            for p in paths
        ],
    }


@router.get("/analytics/matrix")
def get_cross_disease_matrix(
    repository: BiomedicalRepositoryDep,
    curies: str = Query(
        "MONDO:0007915,MONDO:0008383,MONDO:0005301,MONDO:0005265",
        description="Comma-separated list of condition CURIEs",
    ),
) -> dict[str, Any]:
    """Compute an N x N cross-disease biological similarity matrix via DuckDB."""
    curie_list = [c.strip() for c in curies.split(",") if c.strip()]
    analytics = BiomedicalGraphAnalytics(repository)
    engine = analytics.get_duckdb_engine()
    return engine.compute_cross_disease_matrix(curie_list)


@router.get("/analytics/druggability")
def get_druggability_analytics(
    repository: BiomedicalRepositoryDep,
    disease_curie: str | None = Query(None, description="Optional condition CURIE"),
) -> dict[str, Any]:
    """Compute target druggability and evidence predicate distributions via DuckDB."""
    analytics = BiomedicalGraphAnalytics(repository)
    engine = analytics.get_duckdb_engine()
    return engine.get_druggability_distribution(disease_curie=disease_curie)
