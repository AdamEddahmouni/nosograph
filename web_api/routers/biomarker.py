"""Biomarker Discovery API router."""

from fastapi import APIRouter, Query

from web_api.models.biomarker import BiomarkerResponse
from web_api.services.biomarker_service import run_biomarker_analysis

router = APIRouter(tags=["Biomarker"])


@router.get("/api/biomarker/discover", response_model=BiomarkerResponse)
async def discover_biomarkers(
    top_n: int = Query(35, ge=1, le=50, description="Number of top biomarkers to return"),
):
    """Cross-module biomarker discovery across 5 scoring platforms.

    Returns ranked genes with cross-module consistency, expression
    predictiveness, CAR-T alignment, druggability, and novelty scores.
    """
    result = run_biomarker_analysis(top_n=top_n)
    return result
