"""Pydantic models for CAR-T Response Predictor API."""

from pydantic import BaseModel, Field


class CARTGeneResult(BaseModel):
    """Single gene CAR-T suitability result."""
    gene_id: str
    gene_name: str
    category: str = ""
    function: str = ""
    b_cell_dependency: float = 0.0
    autoantibody_association: float = 0.0
    plasma_cell_relevance: float = 0.0
    cd19_targeting: float = 0.0
    clinical_evidence: float = 0.0
    composite_score: float = 0.0
    tier: str = ""
    recommendation: str = ""


class CARTResponse(BaseModel):
    """Response model for CAR-T suitability analysis."""
    genes: list[CARTGeneResult]
    total_genes: int
    avg_score: float = Field(0.0)
    tier1_count: int = Field(0)
    tier2_count: int = Field(0)
    tier3_count: int = Field(0)
