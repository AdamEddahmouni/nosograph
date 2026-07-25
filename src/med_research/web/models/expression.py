"""Pydantic models for Gene Expression Correlation API."""

from pydantic import BaseModel, Field


class ExpressionCorrelationResult(BaseModel):
    """Single drug expression correlation result."""
    drug_id: str
    drug_name: str
    category: str = ""
    type: str = ""
    mechanism: str = ""
    signature_reversal: float = 0.0
    target_disease_overlap: float = 0.0
    cell_type_specificity: float = 0.0
    expression_evidence: float = 0.0
    directionality: float = 0.0
    composite_score: float = 0.0
    tier: str = ""


class ExpressionCorrelationResponse(BaseModel):
    """Response model for expression correlation analysis."""
    drugs: list[ExpressionCorrelationResult]
    total_drugs: int
    avg_score: float = Field(0.0, description="Average composite score")
    tier1_count: int = Field(0, description="Tier 1 count (score >= 7.5)")
    tier2_count: int = Field(0, description="Tier 2 count (6.0 <= score < 7.5)")
    tier3_count: int = Field(0, description="Tier 3 count (4.5 <= score < 6.0)")
