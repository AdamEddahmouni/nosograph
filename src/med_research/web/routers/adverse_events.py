"""Adverse Events API router."""

from typing import Any

from fastapi import APIRouter, Query

from med_research.web.services.adverse_events_service import run_safety_profiling

router = APIRouter(tags=["Safety"])


@router.get("/api/safety/profiles")
async def safety_profiles(
    drug_id: str | None = Query(None, description="Filter to a specific drug ID"),
    disease: str = Query("sle", description="Legacy disease ID parameter"),
    disease_id: str | None = Query(None, description="Disease ID to profile drugs against"),
) -> Any:
    """Get adverse event safety profiles.

    Without drug_id: returns all drugs of the selected disease with summary
    statistics. With drug_id: returns detailed profile for a single drug.
    """
    return run_safety_profiling(drug_id=drug_id, disease_id=disease_id or disease)
