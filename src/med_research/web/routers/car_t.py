"""CAR-T Response Predictor API router."""

from typing import Any

from fastapi import APIRouter, Query

from med_research.web.models.car_t import CARTResponse
from med_research.web.services.car_t_service import run_cart_analysis

router = APIRouter(tags=["CAR-T"])


@router.get("/api/cart/suitability", response_model=CARTResponse)
async def cart_suitability(
    top_n: int = Query(35, ge=1, le=35, description="Number of top genes to return"),
    disease: str = Query("sle", description="Legacy disease ID parameter"),
    disease_id: str | None = Query(None, description="Disease ID to score genes for"),
) -> dict[str, Any]:
    """Score genes for CD19 CAR-T cell therapy suitability.

    Returns ranked genes scored across 5 dimensions: B cell dependency,
    autoantibody association, plasma cell relevance, CD19 targeting,
    and clinical evidence.
    """
    result = run_cart_analysis(top_n=top_n, disease_id=disease_id or disease)
    return result
