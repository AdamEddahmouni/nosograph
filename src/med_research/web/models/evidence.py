"""Evidence Gatherer API models."""

from pydantic import BaseModel, Field


class EvidenceItem(BaseModel):
    """A single evidence result from any source."""

    title: str
    source: str
    source_type: str
    year: str = ""
    url: str
    snippet: str = ""
    id: str = ""
    citation_count: int = 0


class CrossRefPair(BaseModel):
    source_a: str
    source_b: str
    overlap_count: int


class EvidenceGatherResponse(BaseModel):
    """Response from the evidence gatherer API."""

    query: str
    sources_searched: list[str]
    total_results: int
    elapsed_seconds: float
    results_by_source: dict[str, int]
    crossref: dict = Field(default_factory=dict)
    results: list[EvidenceItem]
    generated_at: str
    coverage: dict = Field(default_factory=dict)
    status: str = "ready"


class EvidenceGatherRequest(BaseModel):
    """Request to gather evidence."""

    query: str = Field(..., min_length=2, max_length=500, description="Search query")
    sources: list[str] = Field(
        default=["pubmed", "preprints", "clinical_trials", "fda_labels", "patents"]
    )
    max_per_source: int = Field(default=20, ge=1, le=100)
    use_cache: bool = True
