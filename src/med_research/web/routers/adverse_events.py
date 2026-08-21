"""Adverse Events API router."""

from typing import Annotated, Any

from fastapi import APIRouter, Depends, Query

from med_research.web.disease_params import resolve_optional_query_disease
from med_research.web.services.adverse_events_service import run_safety_profiling

router = APIRouter(tags=["Safety"])

ResolvedDisease = Annotated[str, Depends(resolve_optional_query_disease)]


@router.get("/api/safety/profiles")
async def safety_profiles(
    disease_id: ResolvedDisease,
    drug_id: str | None = Query(None, description="Filter to a specific drug ID"),
) -> Any:
    """Get adverse event safety profiles.

    Without drug_id: returns all drugs of the selected disease with summary
    statistics. With drug_id: returns detailed profile for a single drug.
    """
    return run_safety_profiling(drug_id=drug_id, disease_id=disease_id)
