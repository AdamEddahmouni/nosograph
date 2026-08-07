"""Router for cross-disease analysis endpoints."""

from fastapi import APIRouter, Query

from med_research.web.models.cross_disease import CrossDiseaseResponse
from med_research.web.services.cross_disease_service import (
    run_comparative_modules,
    run_cross_disease_analysis,
)

router = APIRouter(prefix="/api/cross-disease", tags=["Cross-Disease Analysis"])


@router.get("/overlap", response_model=CrossDiseaseResponse)
def get_cross_disease_overlap():
    """Get shared genes, drugs, pathways, and disease similarity across 7 diseases."""
    result = run_cross_disease_analysis()
    return CrossDiseaseResponse(**result)


@router.get("/similarity")
def get_disease_similarity():
    """Get pairwise disease similarity matrix."""
    result = run_cross_disease_analysis()
    return {"similarity": result.get("disease_similarity", []), "diseases": result.get("diseases", [])}


@router.get("/drugs")
def get_multi_disease_drugs(top: int = Query(20, ge=1, le=100)):
    """Get drugs ranked by multi-disease therapeutic potential."""
    result = run_cross_disease_analysis()
    drugs = result.get("multi_disease_drugs", [])
    return {"drugs": drugs[:top], "disease_count": result.get("disease_count", 0)}


@router.get("/modules")
def get_comparative_modules(top_synergy: int = Query(5, ge=1, le=20)):
    """Run biomarker/expression/synergy across all 7 diseases, stacked side by side.

    Returns per-disease gene/drug score matrices (entity -> disease -> score)
    plus top synergy pairs per disease for the comparative dashboard view.
    """
    return run_comparative_modules(top_synergy=top_synergy)
