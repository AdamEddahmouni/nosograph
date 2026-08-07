"""Drug Repurposing Pydantic models."""

from typing import Optional

from pydantic import BaseModel


class RepurposingCandidate(BaseModel):
    rank: int
    drug_name: str
    drug_category: str = ""
    gene_id: str
    gene_name: str
    gene_category: str = ""
    composite_score: float
    target_similarity_score: float
    pathway_proximity_score: float
    mechanistic_rationale_score: float
    clinical_evidence_score: float
    safety_score: float
    novelty_score: float
    evidence_level: str = ""
    mechanism: str = ""
    rationale: str = ""
    status: str = ""
    tier: str = ""


class RepurposingResponse(BaseModel):
    candidates: list[RepurposingCandidate]
    total: int
    tier1_count: int
    tier2_count: int
    avg_score: float
    top_n: int
    coverage: dict = {}
    status: str = "ready"


class GeneRepurposingResponse(BaseModel):
    gene_id: str
    gene_name: str
    gene_category: str = ""
    gene_function: str = ""
    lupus_evidence: str = ""
    odds_ratio: Optional[float] = None
    candidates: list[RepurposingCandidate]
    best_score: float
    count: int


class RepurposingRequest(BaseModel):
    top_n: int = 15
    gene_id: Optional[str] = None
