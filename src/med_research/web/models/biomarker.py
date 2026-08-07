"""Pydantic models for Biomarker Discovery API."""

from pydantic import BaseModel, Field


class BiomarkerResult(BaseModel):
    """Single biomarker result."""
    gene_id: str
    gene_name: str
    category: str = ""
    cross_module_consistency: float = 0.0
    expression_predictiveness: float = 0.0
    cart_alignment: float = 0.0
    druggability: float = 0.0
    biomarker_novelty: float = 0.0
    composite_score: float = 0.0
    best_modality: str = ""
    tier: str = ""


class BiomarkerResponse(BaseModel):
    """Response model for biomarker discovery."""
    biomarkers: list[BiomarkerResult]
    total_genes: int
    avg_score: float = Field(0.0)
    tier1_count: int = Field(0)
    tier2_count: int = Field(0)
    coverage: dict = Field(default_factory=dict)
    status: str = "ready"
