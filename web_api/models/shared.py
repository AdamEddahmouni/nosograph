"""Literature Mining, Virtual Screening, Clinical Trials, and ML Pydantic models."""

from typing import Any, Optional

from pydantic import BaseModel

# ── Literature Mining ──────────────────────────────────────────────────────

class LiteratureArticle(BaseModel):
    pmid: str
    title: str
    abstract: str = ""
    journal: str = ""
    year: Optional[int] = None
    entities: dict[str, Any] = {}
    relevance_score: float = 0.0


class LiteratureCrossReference(BaseModel):
    gene_id: str
    gene_name: str = ""
    article_count: int
    supporting_count: int
    coverage_score: float


class LiteratureResponse(BaseModel):
    total_articles: int
    queries_run: int
    articles: list[dict[str, Any]]
    gene_coverage: list[LiteratureCrossReference]
    candidate_support: list[dict[str, Any]]


class LiteratureRequest(BaseModel):
    max_articles: int = 30
    targeted: bool = False
    no_cache: bool = False


# ── Virtual Screening ──────────────────────────────────────────────────────

class ScreeningCompound(BaseModel):
    drug_id: str
    drug_name: str
    composite_score: float
    binding_estimate: float
    druglikeness: float
    target_complementarity: float
    similarity_score: float
    novelty_score: float
    tier: str = ""
    gene_id: str = ""
    gene_name: str = ""
    drug_type: str = ""


class ScreeningTargetResult(BaseModel):
    gene_id: str
    gene_name: str
    gene_category: str = ""
    top_compounds: list[ScreeningCompound]
    total_screened: int
    mean_score: float


class ScreeningResponse(BaseModel):
    targets: list[ScreeningTargetResult]
    compounds_screened: int
    total_pairings: int
    tier1_count: int
    tier2_count: int
    vina_available: bool
    rdkit_available: bool


class ScreeningRequest(BaseModel):
    gene_id: Optional[str] = None
    top_n: int = 15
    use_vina: bool = False


# ── Clinical Trials ────────────────────────────────────────────────────────

class ClinicalTrial(BaseModel):
    nct_id: str
    title: str
    phase: str = ""
    status: str = ""
    conditions: list[str] = []
    interventions: list[str] = []
    sponsors: list[str] = []
    enrollment: Optional[int] = None
    start_date: Optional[str] = None
    kg_drugs: list[str] = []
    kg_genes: list[str] = []
    moa_category: str = ""


class TrialsResponse(BaseModel):
    total_trials: int
    phase_distribution: dict[str, int]
    moa_distribution: dict[str, int]
    top_sponsors: list[dict[str, Any]]
    trials: list[dict[str, Any]]
    kg_crossref: dict[str, Any] = {}


class TrialsRequest(BaseModel):
    max_trials: int = 100
    query: str = "lupus OR SLE"
    no_cache: bool = False


# ── ML Predictor ───────────────────────────────────────────────────────────

class MLPrediction(BaseModel):
    rank: int
    gene_id: str
    gene_name: str
    gene_category: str = ""
    druggability_score: float
    is_targeted: bool = False
    features: dict[str, Any] = {}


class MLResponse(BaseModel):
    predictions: list[MLPrediction]
    model_type: str = "XGBoost"
    cross_val_auc: Optional[float] = None
    accuracy: Optional[float] = None
    top_features: list[dict[str, Any]] = []


class MLRequest(BaseModel):
    top_n: int = 15
    no_shap: bool = False
