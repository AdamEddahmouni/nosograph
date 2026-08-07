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
                        for module, inputs in {
                            "literature": ("genes", "drugs", "pathways", "pubmed_queries"),
                            "gwas": ("genes", "gwas_search_terms"),
                            "enrichment": ("genes", "pathways"),
                            "screening": ("genes", "drugs", "pathways", "screening_profile"),
                            "safety": ("symptoms", "adverse_event_profile", "safety_risk"),
                            "car_t": ("genes", "car_t_scores"),
                        }.items()
                    },
                },
            )
        )
    diseases.sort(key=lambda d: d.id)
    return DiseasesResponse(count=len(diseases), diseases=diseases)


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
