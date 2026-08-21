"""Synergy API router."""

from typing import Annotated, Any

from fastapi import APIRouter, Depends, Query

from med_research.web.disease_params import resolve_optional_query_disease
from med_research.web.models.synergy import SynergyResponse
from med_research.web.services.synergy_service import run_synergy

router = APIRouter(tags=["Synergy"])

ResolvedDisease = Annotated[str, Depends(resolve_optional_query_disease)]


@router.get("/api/synergy/pairs", response_model=SynergyResponse)
async def drug_synergy(
    disease_id: ResolvedDisease,
    top_n: int = Query(20, ge=1, le=100, description="Number of top pairs"),
) -> dict[str, Any]:
    """Predict synergistic drug combinations from a disease's drug library."""
    return run_synergy(top_n=top_n, disease_id=disease_id)
