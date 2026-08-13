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
    """Rank disease targets based on canonical claim evidence and graph degree centrality."""
    analytics = BiomedicalGraphAnalytics(repository)
    scores = analytics.prioritize_disease_targets(disease_curie=disease_curie, top_k=top_k)
    return {
        "disease_curie": disease_curie,
        "total_targets": len(scores),
        "rankings": [
            {
                "target_curie": s.target_curie,
                "target_label": s.target_label,
                "supporting_evidence": s.supporting_evidence_count,
                "contradictory_evidence": s.contradictory_evidence_count,
                "centrality_score": s.centrality_score,
                "vulnerability_score": s.combined_vulnerability_score,
            }
            for s in scores
        ],
    }
