"""System API router — health checks, platform stats, disease registry."""

from datetime import datetime
from importlib.metadata import version
from typing import Any

from fastapi import APIRouter, Query

from med_research.diseases.base import Disease
from med_research.pipeline.gateway import pipeline_gateway
from med_research.web.dependencies import (
    get_candidates,
    get_kg_drugs,
    get_kg_genes,
    get_kg_pathways,
    get_knowledge_graph,
)
from med_research.web.models import (
    CoverageSummary,
    DiseaseInfo,
    DiseasesResponse,
    HealthResponse,
    PipelineModulesResponse,
    PlatformStats,
)

router = APIRouter(tags=["System"])


@router.get("/api/health", response_model=HealthResponse)
async def health() -> dict[str, Any]:
    """Health check endpoint."""
    return {
        "status": "ok",
        "version": version("med-research"),
        "timestamp": datetime.now().isoformat(),
    }


@router.get("/api/system/diseases", response_model=DiseasesResponse)
async def disease_registry() -> DiseasesResponse:
    """List all available diseases (fresh filesystem scan).

    Scans the diseases/ tree on every request so diseases scaffolded via
    ``med-research disease add`` appear without restarting the server.
    """
    import json

    from med_research.diseases.base import Disease
    from med_research.diseases.coverage import coverage_for_disease
    from med_research.diseases.coverage_report import DEFAULT_MODULE_INPUTS
    from med_research.exceptions import DataValidationError

    catalog = pipeline_gateway.catalog()
    coverage_module_ids = {entry["coverage_module"]: entry["module_id"] for entry in catalog}

    diseases = []
    for disease_id in Disease.list_all():
        try:
            disease = Disease(disease_id)
            profile = disease.profile
            genes = disease.load_genes()
            drugs = disease.load_drugs()
            pathways = disease.load_pathways()
        except (
            ValueError,
            FileNotFoundError,
            KeyError,
            json.JSONDecodeError,
            OSError,
            DataValidationError,
        ):
            # Keep incomplete modules visible; their coverage is the reason they
            # belong in the registry and should be reported as blocked.
            try:
                disease = Disease(disease_id)
                profile = disease.profile
            except (OSError, ValueError, KeyError, TypeError, AttributeError):
                continue
            genes = drugs = pathways = {"genes": [], "drugs": [], "pathways": []}
        diseases.append(
            DiseaseInfo(
                id=disease_id,
                name=profile.name,
                description=profile.description,
                prevalence=profile.prevalence,
                genes=len(genes.get("genes", [])),
                drugs=len(drugs.get("drugs", [])),
                pathways=len(pathways.get("pathways", [])),
                coverage={
                    "core": coverage_for_disease(disease_id).to_dict(),
                    "modules": {
                        module: pipeline_gateway.coverage(
                            coverage_module_ids[module],
                            disease_id,
                        ).to_dict()
                        for module in DEFAULT_MODULE_INPUTS
                    },
                },
            )
        )
    diseases.sort(key=lambda d: d.id)
    return DiseasesResponse(count=len(diseases), diseases=diseases)


@router.get("/api/system/modules", response_model=PipelineModulesResponse)
async def pipeline_modules(
    disease: str = Query("sle", description="Disease ID for per-module coverage metadata"),
) -> dict[str, Any]:
    """List registered pipeline modules with per-disease coverage metadata."""
    modules = []
    for metadata in pipeline_gateway.catalog():
        coverage = pipeline_gateway.coverage(metadata["module_id"], disease)
        modules.append({**metadata, "coverage": coverage.to_dict()})

    return {
        "count": len(modules),
        "disease_id": disease,
        "modules": modules,
    }


@router.get("/api/system/cache/stats")
async def cache_stats() -> dict[str, Any]:
    """Return cache namespace statistics (auth-protected when API_KEY is set)."""
    from med_research.cache import CacheManager

    return CacheManager().stats()


@router.delete("/api/system/cache")
@router.delete("/api/system/cache/{namespace}")
async def cache_clear(namespace: str | None = None) -> dict[str, Any]:
    """Clear one cache namespace or all namespaces (auth-protected when API_KEY is set)."""
    from med_research.cache import CacheManager

    removed = CacheManager().clear(namespace=namespace)
    return {"removed": removed, "namespace": namespace}


def _disease_display_name(disease_id: str) -> str:
    try:
        return Disease(disease_id).profile.name
    except (OSError, ValueError, KeyError, TypeError, AttributeError):
        return disease_id


def _coverage_summary_for_disease(disease_id: str) -> CoverageSummary:
    counts = {"full": 0, "partial": 0, "unsupported": 0}
    for metadata in pipeline_gateway.catalog():
        level = pipeline_gateway.coverage(metadata["module_id"], disease_id).level
        if level in counts:
            counts[level] += 1
    return CoverageSummary(**counts)


@router.get("/api/stats", response_model=PlatformStats)
async def platform_stats(
    disease: str = Query("sle", description="Disease ID to compute stats for"),
) -> dict[str, Any]:
    """Get platform statistics for a specific disease."""
    G = get_knowledge_graph(disease)
    genes = get_kg_genes(disease)
    drugs = get_kg_drugs(disease)
    pathways = get_kg_pathways(disease)
    candidates = get_candidates(disease)

    return {
        "disease_id": disease,
        "disease_name": _disease_display_name(disease),
        "kg_nodes": G.number_of_nodes(),
        "kg_edges": G.number_of_edges(),
        "genes": len(genes),
        "drugs": len(drugs),
        "pathways": len(pathways),
        "candidates": len(candidates),
        "modules": len(pipeline_gateway.catalog()),
        "diseases": len(Disease.list_all()),
        "coverage_summary": _coverage_summary_for_disease(disease).model_dump(),
    }
