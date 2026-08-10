"""Synergy API router."""

from typing import Any

from fastapi import APIRouter, Query

from med_research.web.models.synergy import SynergyResponse
from med_research.web.services.synergy_service import run_synergy

router = APIRouter(tags=["Synergy"])


@router.get("/api/synergy/pairs", response_model=SynergyResponse)
async def drug_synergy(
    top_n: int = Query(20, ge=1, le=100, description="Number of top pairs"),
    disease_id: str = Query("sle", description="Disease ID"),
) -> dict[str, Any]:
    """Predict synergistic drug combinations from a disease's drug library."""
    return run_synergy(top_n=top_n, disease_id=disease_id)
