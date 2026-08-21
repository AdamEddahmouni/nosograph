"""CAR-T Response Predictor API router."""

from typing import Annotated, Any

from fastapi import APIRouter, Depends, Query

from med_research.web.disease_params import resolve_optional_query_disease
from med_research.web.models.car_t import CARTResponse
from med_research.web.services.car_t_service import run_cart_analysis

router = APIRouter(tags=["CAR-T"])

ResolvedDisease = Annotated[str, Depends(resolve_optional_query_disease)]


@router.get("/api/cart/suitability", response_model=CARTResponse)
async def cart_suitability(
    disease_id: ResolvedDisease,
    top_n: int = Query(35, ge=1, le=35, description="Number of top genes to return"),
) -> dict[str, Any]:
    """Score genes for CD19 CAR-T cell therapy suitability.

    Returns ranked genes scored across 5 dimensions: B cell dependency,
    autoantibody association, plasma cell relevance, CD19 targeting,
    and clinical evidence.
    """
    result = run_cart_analysis(top_n=top_n, disease_id=disease_id)
    return result
