"""Drug Repurposing API router."""

from typing import Any

from fastapi import APIRouter, HTTPException, Query

from med_research.web.models.repurpose import GeneRepurposingResponse, RepurposingResponse
from med_research.web.services.repurpose_service import get_gene_repurposing, run_repurposing

router = APIRouter(prefix="/api/repurpose", tags=["Drug Repurposing"])


@router.get("/candidates", response_model=RepurposingResponse)
async def repurposing_candidates(
    top_n: int = Query(15, ge=1, le=50, description="Number of top candidates"),
    gene_id: str | None = Query(None, description="Filter by gene ID"),
    disease: str = Query("sle", description="Disease ID to run repurposing for"),
) -> dict[str, Any]:
    """Get top drug repurposing candidates ranked by composite score."""
    return run_repurposing(top_n=top_n, gene_id=gene_id, disease_id=disease)


@router.get("/gene/{gene_id}", response_model=GeneRepurposingResponse)
async def gene_repurposing(
    gene_id: str,
    disease: str = Query("sle", description="Disease ID the gene belongs to"),
) -> dict[str, Any]:
    """Get all repurposing candidates for a specific gene."""
    result = get_gene_repurposing(gene_id, disease_id=disease)
    if result is None:
        raise HTTPException(status_code=404, detail=f"Gene '{gene_id}' not found")
    return result
