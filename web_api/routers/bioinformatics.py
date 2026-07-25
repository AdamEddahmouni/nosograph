"""Bioinformatics API router — GWAS, Enrichment, PPI."""

from fastapi import APIRouter, Query

from web_api.models.bioinformatics import EnrichmentResponse, GWASResponse, PPINetworkResponse
from web_api.services.bioinformatics_service import run_enrichment, run_gwas, run_ppi

router = APIRouter(prefix="/api/bioinformatics", tags=["Bioinformatics"])


@router.get("/gwas", response_model=GWASResponse)
async def bio_gwas(
    max_studies: int = Query(30, ge=1, le=100, description="Max GWAS studies"),
    no_cache: bool = Query(False, description="Skip cache"),
):
    """Run GWAS catalog annotation for lupus-associated variants."""
    return run_gwas(max_studies=max_studies, no_cache=no_cache)


@router.get("/enrichment", response_model=EnrichmentResponse)
async def bio_enrichment(
    untargeted_only: bool = Query(False, description="Only untargeted genes"),
    no_cache: bool = Query(False, description="Skip cache"),
):
    """Run pathway enrichment analysis (GO, KEGG, Reactome, WikiPathways)."""
    return run_enrichment(untargeted_only=untargeted_only, no_cache=no_cache)


@router.get("/ppi", response_model=PPINetworkResponse)
async def bio_ppi(
    confidence: float = Query(0.4, ge=0.15, le=1.0, description="STRING confidence"),
    no_cache: bool = Query(False, description="Skip cache"),
):
    """Build PPI network and compute hub scores from STRING."""
    return run_ppi(confidence=confidence, no_cache=no_cache)
