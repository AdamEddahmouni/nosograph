"""Semantic Search API router."""

from typing import Any

from fastapi import APIRouter, Query

from med_research.web.models.semantic import SemanticSearchResponse
from med_research.web.services.semantic_service import run_semantic_search

router = APIRouter(tags=["Semantic Search"])


@router.get("/api/semantic/search", response_model=SemanticSearchResponse)
async def semantic_search(
    q: str = Query(..., min_length=1, max_length=500, description="Natural language search query"),
    top_k: int = Query(20, ge=1, le=100, description="Number of results to return"),
    disease_id: str = Query("sle", description="Disease ID"),
) -> dict[str, Any]:
    """Semantic search over indexed PubMed abstracts.

    Find papers by meaning, not exact keyword match.
    Uses sentence-transformers embeddings + ChromaDB vector search.
    """
    result = run_semantic_search(query=q, top_k=top_k, disease_id=disease_id)
    return result
