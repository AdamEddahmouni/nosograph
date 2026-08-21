"""Semantic Search API router."""

from typing import Annotated, Any

from fastapi import APIRouter, Depends, Query

from med_research.web.disease_params import resolve_optional_query_disease
from med_research.web.models.semantic import SemanticSearchResponse
from med_research.web.services.semantic_service import run_semantic_search

router = APIRouter(tags=["Semantic Search"])

ResolvedDisease = Annotated[str, Depends(resolve_optional_query_disease)]


@router.get("/api/semantic/search", response_model=SemanticSearchResponse)
async def semantic_search(
    disease_id: ResolvedDisease,
    q: str = Query(..., min_length=1, max_length=500, description="Natural language search query"),
    top_k: int = Query(20, ge=1, le=100, description="Number of results to return"),
) -> dict[str, Any]:
    """Semantic search over indexed PubMed abstracts.

    Find papers by meaning, not exact keyword match.
    Uses sentence-transformers embeddings + ChromaDB vector search.
    """
    result = run_semantic_search(query=q, top_k=top_k, disease_id=disease_id)
    return result
