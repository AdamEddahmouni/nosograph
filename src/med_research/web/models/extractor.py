"""Pydantic models for the LLM Evidence Extractor API."""

from typing import Optional

from pydantic import BaseModel, Field


class ExtractionResult(BaseModel):
    """A single extracted article with structured data."""

    title: str = ""
    source_type: str = ""
    source: str = ""
    year: str = ""
    url: str = ""
    id: str = ""
    evidence_level: str = "unknown"
    model_system: str = "unknown"
    key_findings: str = ""
    drugs_mentioned: list[str] = Field(default_factory=list)
    disease: str = ""
    study_design: str = "unknown"
    sample_size: Optional[int] = None
    p_value: Optional[str] = None
    effect_size: Optional[str] = None
    relevance_to_query: int = 50
    confidence: int = 0


class ExtractionStats(BaseModel):
    """Summary statistics across all extractions."""

    evidence_levels: dict[str, int] = Field(default_factory=dict)
    model_systems: dict[str, int] = Field(default_factory=dict)
    study_designs: dict[str, int] = Field(default_factory=dict)
    unique_drugs_mentioned: list[str] = Field(default_factory=list)
    n_unique_drugs: int = 0
    top_diseases: dict[str, int] = Field(default_factory=dict)
    avg_sample_size: Optional[int] = None
    articles_with_sample_size: int = 0
    avg_confidence: float = 0.0
    avg_relevance: float = 0.0


class ExtractionResponse(BaseModel):
    """Full LLM extraction response."""

    query: str
    model: str
    total_extracted: int
    successful_extractions: int = 0
    elapsed_seconds: float = 0.0
    extractions: list[ExtractionResult] = Field(default_factory=list)
    stats: ExtractionStats = Field(default_factory=ExtractionStats)
    error: Optional[str] = None
    generated_at: str = ""
    coverage: dict = Field(default_factory=dict)
    status: str = "ready"
