"""Bioinformatics API router — GWAS, Enrichment, PPI."""

from typing import Any

from fastapi import APIRouter, Query

from med_research.web.models.bioinformatics import (
    EnrichmentResponse,
    GWASResponse,
    PPINetworkResponse,
)
from med_research.web.services.bioinformatics_service import run_enrichment, run_gwas, run_ppi

router = APIRouter(prefix="/api/bioinformatics", tags=["Bioinformatics"])


@router.get("/gwas", response_model=GWASResponse)
async def bio_gwas(
    max_studies: int = Query(30, ge=1, le=100, description="Max GWAS studies"),
    no_cache: bool = Query(False, description="Skip cache"),
    disease_id: str = Query("sle", description="Disease ID"),
) -> dict[str, Any]:
    """Run disease-specific GWAS catalog annotation."""
    return run_gwas(
        max_studies=max_studies,
        no_cache=no_cache,
        disease_id=disease_id,
    )


@router.get("/enrichment", response_model=EnrichmentResponse)
async def bio_enrichment(
    untargeted_only: bool = Query(False, description="Only untargeted genes"),
    no_cache: bool = Query(False, description="Skip cache"),
    disease_id: str = Query("sle", description="Disease ID"),
) -> dict[str, Any]:
    """Run disease-specific pathway enrichment analysis."""
    return run_enrichment(
        untargeted_only=untargeted_only,
        no_cache=no_cache,
        disease_id=disease_id,
    )


@router.get("/ppi", response_model=PPINetworkResponse)
async def bio_ppi(
    confidence: float = Query(0.4, ge=0.15, le=1.0, description="STRING confidence"),
    no_cache: bool = Query(False, description="Skip cache"),
    disease_id: str = Query("sle", description="Disease ID"),
) -> dict[str, Any]:
    """Build a disease-specific PPI network and compute hub scores."""
    return run_ppi(
        confidence=confidence,
        no_cache=no_cache,
        disease_id=disease_id,
    )
