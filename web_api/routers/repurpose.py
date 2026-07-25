"""Drug Repurposing API router."""

from fastapi import APIRouter, HTTPException, Query

from web_api.models.repurpose import GeneRepurposingResponse, RepurposingResponse
from web_api.services.repurpose_service import get_gene_repurposing, run_repurposing

router = APIRouter(prefix="/api/repurpose", tags=["Drug Repurposing"])


@router.get("/candidates", response_model=RepurposingResponse)
async def repurposing_candidates(
    top_n: int = Query(15, ge=1, le=50, description="Number of top candidates"),
    gene_id: str | None = Query(None, description="Filter by gene ID"),
):
    """Get top drug repurposing candidates ranked by composite score."""
    return run_repurposing(top_n=top_n, gene_id=gene_id)


@router.get("/gene/{gene_id}", response_model=GeneRepurposingResponse)
async def gene_repurposing(gene_id: str):
    """Get all repurposing candidates for a specific gene."""
    result = get_gene_repurposing(gene_id)
    if result is None:
        raise HTTPException(status_code=404, detail=f"Gene '{gene_id}' not found")
    return result
