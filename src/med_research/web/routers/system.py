"""System API router — health checks, platform stats."""

from datetime import datetime
from importlib.metadata import version

from fastapi import APIRouter

from med_research.web.dependencies import (
    get_candidates,
    get_kg_drugs,
    get_kg_genes,
    get_kg_pathways,
    get_knowledge_graph,
)
from med_research.web.models import HealthResponse, PlatformStats

router = APIRouter(tags=["System"])


@router.get("/api/health", response_model=HealthResponse)
async def health():
    """Health check endpoint."""
    return {
        "status": "ok",
        "version": version("med-research"),
        "timestamp": datetime.now().isoformat(),
    }


@router.get("/api/stats", response_model=PlatformStats)
async def platform_stats():
    """Get platform-wide statistics."""
    G = get_knowledge_graph()
    genes = get_kg_genes()
    drugs = get_kg_drugs()
    pathways = get_kg_pathways()
    candidates = get_candidates()

    return {
        "kg_nodes": G.number_of_nodes(),
        "kg_edges": G.number_of_edges(),
        "genes": len(genes),
        "drugs": len(drugs),
        "pathways": len(pathways),
        "candidates": len(candidates),
    }
