"""Adverse Event Profiling Pydantic models."""

from pydantic import BaseModel


class DrugSafetyProfile(BaseModel):
    drug_id: str
    drug_name: str
    disease_id: str = "sle"
    disease_symptom_overlap_score: float
    disease_overlap_score: float | None = None
    lupus_symptom_overlap_score: float | None = None
    severity_burden_score: float
    chronic_use_safety_score: float
    disease_specific_risk_score: float
    dil_risk_score: float | None = None
    composite_safety_score: float
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
    avg_safety_score: float
    safest_drug: str
    safest_score: float
    riskiest_drug: str
    riskiest_score: float
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
