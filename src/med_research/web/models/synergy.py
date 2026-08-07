"""Drug Combination Synergy Pydantic models."""

from pydantic import BaseModel


class SynergyPair(BaseModel):
    rank: int = 0
    drug_a_id: str
    drug_a_name: str
    drug_b_id: str
    drug_b_name: str
    target_complementarity: float
    pathway_diversity: float
    mechanism_orthogonality: float
    safety_non_overlap: float
    combined_evidence: float
    composite_score: float
    tier: str = ""
    drug_a_type: str = ""
    drug_b_type: str = ""
    drug_a_category: str = ""
    drug_b_category: str = ""


class SynergyResponse(BaseModel):
    total_pairs: int
    pairs: list[dict]
    tier1_count: int
    tier2_count: int
    tier3_count: int
    avg_score: float
    max_score: float
    coverage: dict = {}
    status: str = "ready"


class SynergyRequest(BaseModel):
    top_n: int = 15
