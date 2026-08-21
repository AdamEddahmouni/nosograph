"""Biomarker Discovery API router."""

from typing import Annotated, Any

from fastapi import APIRouter, Depends, Query

from med_research.web.disease_params import resolve_optional_query_disease
from med_research.web.models.biomarker import BiomarkerResponse
from med_research.web.services.biomarker_service import run_biomarker_analysis

router = APIRouter(tags=["Biomarker"])

ResolvedDisease = Annotated[str, Depends(resolve_optional_query_disease)]


@router.get("/api/biomarker/discover", response_model=BiomarkerResponse)
async def discover_biomarkers(
    disease_id: ResolvedDisease,
    top_n: int = Query(35, ge=1, le=50, description="Number of top biomarkers to return"),
) -> dict[str, Any]:
    """Cross-module biomarker discovery across 5 scoring platforms.

    Returns ranked genes with cross-module consistency, expression
    predictiveness, CAR-T alignment, druggability, and novelty scores.
    """
    result = run_biomarker_analysis(top_n=top_n, disease_id=disease_id)
    return result
