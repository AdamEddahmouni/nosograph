"""Drug Repurposing API router."""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query

from med_research.pipeline.results import GeneRepurposingResponse, RepurposingAnalysisResponse
from med_research.web.disease_params import resolve_optional_query_disease
from med_research.web.models.repurpose import (
    GeneRepurposingResponse as GeneRepurposingModel,
)
from med_research.web.models.repurpose import (
    RepurposingResponse as RepurposingModel,
)
from med_research.web.services.repurpose_service import get_gene_repurposing, run_repurposing

router = APIRouter(prefix="/api/repurpose", tags=["Drug Repurposing"])

ResolvedDisease = Annotated[str, Depends(resolve_optional_query_disease)]


@router.get("/candidates", response_model=RepurposingModel)
async def repurposing_candidates(
    disease: ResolvedDisease,
    top_n: int = Query(15, ge=1, le=50, description="Number of top candidates"),
    gene_id: str | None = Query(None, description="Filter by gene ID"),
) -> RepurposingAnalysisResponse:
    """Get top drug repurposing candidates ranked by composite score."""
    return run_repurposing(top_n=top_n, gene_id=gene_id, disease_id=disease)


@router.get("/gene/{gene_id}", response_model=GeneRepurposingModel)
async def gene_repurposing(
    gene_id: str,
    disease: ResolvedDisease,
) -> GeneRepurposingResponse:
    """Get all repurposing candidates for a specific gene."""
    result = get_gene_repurposing(gene_id, disease_id=disease)
    if result is None:
        raise HTTPException(status_code=404, detail=f"Gene '{gene_id}' not found")
    return result
