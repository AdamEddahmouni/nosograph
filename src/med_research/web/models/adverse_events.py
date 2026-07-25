"""Adverse Event Profiling Pydantic models."""

from pydantic import BaseModel


class DrugSafetyProfile(BaseModel):
    drug_id: str
    drug_name: str
    lupus_symptom_overlap_score: float
    severity_burden_score: float
    chronic_use_safety_score: float
    dil_risk_score: float
    composite_safety_score: float
    n_lupus_overlap_ae: int
    lupus_overlap_ae: list[str] = []
    black_box_warnings: list[str] = []
    monitoring_required: str = ""
    n_severe_ae: int = 0


class SafetySummaryResponse(BaseModel):
    total_drugs: int
    avg_safety_score: float
    safest_drug: str
    safest_score: float
    riskiest_drug: str
    riskiest_score: float
    drugs_with_bbw: int
    drugs_with_dil_risk: int
    profiles: list[dict] = []
