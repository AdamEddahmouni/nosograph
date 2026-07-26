"""Analysis API routers — Literature, Screening, Trials, ML."""

from fastapi import APIRouter, Query

from med_research.web.models.shared import (
    LiteratureResponse,
    MLResponse,
    ScreeningResponse,
    TrialsResponse,
)
from med_research.web.services.shared_services import (
    run_literature,
    run_ml_prediction,
    run_screening,
    run_trials,
)

router = APIRouter(tags=["Analysis"])


# ── Literature Mining ──────────────────────────────────────────────────────

@router.get("/api/literature", response_model=LiteratureResponse)
async def literature_mining(
    max_articles: int = Query(30, ge=1, le=100, description="Max articles"),
    targeted: bool = Query(False, description="Include per-drug targeted queries"),
    no_cache: bool = Query(False, description="Skip cache"),
):
    """Mine PubMed for SLE-related articles with biomedical NER."""
    return run_literature(max_articles=max_articles, targeted=targeted, no_cache=no_cache)


# ── Virtual Screening ──────────────────────────────────────────────────────

@router.get("/api/screening", response_model=ScreeningResponse)
async def virtual_screening(
    gene_id: str | None = Query(None, description="Screen against a specific gene"),
    top_n: int = Query(15, ge=1, le=50, description="Top compounds per target"),
    use_vina: bool = Query(False, description="Use AutoDock Vina docking"),
):
    """Run virtual drug screening against lupus targets."""
    return run_screening(gene_id=gene_id, top_n=top_n, use_vina=use_vina)


# ── Clinical Trials ────────────────────────────────────────────────────────

@router.get("/api/trials", response_model=TrialsResponse)
async def clinical_trials(
    max_trials: int = Query(100, ge=1, le=200, description="Max trials"),
    query: str = Query("lupus OR SLE", min_length=1, max_length=500, description="ClinicalTrials.gov search query"),
    no_cache: bool = Query(False, description="Skip cache"),
):
    """Track lupus clinical trials from ClinicalTrials.gov."""
    return run_trials(max_trials=max_trials, query=query, no_cache=no_cache)


# ── ML Predictor ───────────────────────────────────────────────────────────

@router.get("/api/ml/predict", response_model=MLResponse)
async def ml_predictor(
    top_n: int = Query(15, ge=1, le=50, description="Top predictions"),
    no_shap: bool = Query(False, description="Skip SHAP analysis"),
):
    """Run ML target druggability prediction with XGBoost + SHAP."""
    return run_ml_prediction(top_n=top_n, no_shap=no_shap)
