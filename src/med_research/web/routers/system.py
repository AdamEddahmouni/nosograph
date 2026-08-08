"""System API router — health checks, platform stats, disease registry."""

from datetime import datetime
from importlib.metadata import version

from fastapi import APIRouter, Query

from med_research.web.dependencies import (
    get_candidates,
    get_kg_drugs,
    get_kg_genes,
    get_kg_pathways,
    get_knowledge_graph,
)
from med_research.web.models import (
    DiseaseInfo,
    DiseasesResponse,
    HealthResponse,
    PlatformStats,
)

router = APIRouter(tags=["System"])


@router.get("/api/health", response_model=HealthResponse)
async def health():
    """Health check endpoint."""
    return {
        "status": "ok",
        "version": version("med-research"),
        "timestamp": datetime.now().isoformat(),
    }


@router.get("/api/system/diseases", response_model=DiseasesResponse)
async def disease_registry():
    """List all available diseases (fresh filesystem scan).

    Scans the diseases/ tree on every request so diseases scaffolded via
    ``med-research disease add`` appear without restarting the server.
    """
    import json

    from med_research.diseases.base import Disease
    from med_research.diseases.coverage import coverage_for_disease, module_coverage
    from med_research.diseases.coverage_report import DEFAULT_MODULE_INPUTS
    from med_research.exceptions import DataValidationError

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
            except Exception:
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
                        module: module_coverage(
                            disease_id,
                            module,
                            required_inputs=inputs,
                        ).to_dict()
                        for module, inputs in DEFAULT_MODULE_INPUTS.items()
                    },
                },
            )
        )
    diseases.sort(key=lambda d: d.id)
    return DiseasesResponse(count=len(diseases), diseases=diseases)


@router.get("/api/system/modules")
async def pipeline_modules(
    disease: str = Query("sle", description="Disease ID for per-module coverage metadata"),
):
    """List registered pipeline modules with per-disease coverage metadata."""
    from med_research.diseases.coverage import module_coverage
    from med_research.pipeline.registry import get_module, list_modules

    modules = []
    for module_id in list_modules():
        adapter = get_module(module_id)
        coverage_module = getattr(adapter, "_COVERAGE_MODULE", module_id)
        coverage = module_coverage(
            disease,
            coverage_module,
            adapter.coverage_inputs(),
        )
        modules.append({
            "module_id": module_id,
            "depends_on": list(adapter.depends_on),
            "coverage_inputs": list(adapter.coverage_inputs()),
            "coverage": coverage.to_dict(),
        })

    return {
        "count": len(modules),
        "disease_id": disease,
        "modules": modules,
    }


@router.get("/api/stats", response_model=PlatformStats)
async def platform_stats(
    disease: str = Query("sle", description="Disease ID to compute stats for"),
):
    """Get platform statistics for a specific disease."""
    G = get_knowledge_graph(disease)
    genes = get_kg_genes(disease)
    drugs = get_kg_drugs(disease)
    pathways = get_kg_pathways(disease)
    candidates = get_candidates()

    return {
        "kg_nodes": G.number_of_nodes(),
        "kg_edges": G.number_of_edges(),
        "genes": len(genes),
        "drugs": len(drugs),
        "pathways": len(pathways),
        "candidates": len(candidates),
    }
