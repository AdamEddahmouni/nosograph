"""Synergy API router."""

from fastapi import APIRouter, Query

from web_api.models.synergy import SynergyResponse
from web_api.services.synergy_service import run_synergy

router = APIRouter(tags=["Synergy"])


@router.get("/api/synergy/pairs", response_model=SynergyResponse)
async def drug_synergy(
    top_n: int = Query(20, ge=1, le=100, description="Number of top pairs"),
):
    """Predict synergistic drug combinations from the 26-drug library."""
    return run_synergy(top_n=top_n)
