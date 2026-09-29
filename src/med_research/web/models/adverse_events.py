"""Adverse Event Profiling Pydantic models."""

from pydantic import BaseModel


class DrugSafetyProfile(BaseModel):
    drug_id: str
    drug_name: str
    disease_id: str = "sle"
    score_status: str = "scored"
    disease_symptom_overlap_score: float | None = None
    disease_overlap_score: float | None = None
    lupus_symptom_overlap_score: float | None = None
    severity_burden_score: float | None = None
    chronic_use_safety_score: float | None = None
    disease_specific_risk_score: float | None = None
    dil_risk_score: float | None = None
    composite_safety_score: float | None = None
    n_disease_overlap_ae: int = 0
    n_lupus_overlap_ae: int | None = None
    disease_overlap_ae: list[str] = []
    lupus_overlap_ae: list[str] | None = None
    evidence_grade: str = ""
    profile_source: str = ""
    profile_curated_inputs: list[str] = []
    profile_inferred_inputs: list[str] = []
    limitations: list[str] = []
    black_box_warnings: list[str] = []
    monitoring_required: str = ""
    n_severe_ae: int = 0


class SafetySummaryResponse(BaseModel):
    disease_id: str = "sle"
    total_drugs: int
    scored_drugs: int = 0
    unscored_drugs: int = 0
    avg_safety_score: float | None = None
    safest_drug: str
    safest_score: float | None = None
    riskiest_drug: str
    riskiest_score: float | None = None
    drugs_with_bbw: int
    drugs_with_disease_specific_risk: int
    drugs_with_dil_risk: int | None = None
    profiles: list[dict] = []
    coverage: dict = {}
    status: str = "ready"
    profile_source: str = ""
    profile_curated_inputs: list[str] = []
    profile_inferred_inputs: list[str] = []
    limitations: list[str] = []
