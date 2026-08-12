"""Pydantic models for Semantic Search API."""

from pydantic import BaseModel


class SemanticResult(BaseModel):
    """Single semantic search result."""

    rank: int
    pmid: str
    title: str
    year: str = ""
    journal: str = ""
    similarity: float


class SemanticSearchResponse(BaseModel):
    """Response model for semantic search."""

    query: str
    results: list[SemanticResult]
    total_results: int
    indexed_articles: int
    coverage: dict = {}
    status: str = "ready"
