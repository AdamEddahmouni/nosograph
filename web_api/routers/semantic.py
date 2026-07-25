"""Semantic Search API router."""

from fastapi import APIRouter, Query

from web_api.models.semantic import SemanticSearchResponse
from web_api.services.semantic_service import run_semantic_search

router = APIRouter(tags=["Semantic Search"])


@router.get("/api/semantic/search", response_model=SemanticSearchResponse)
async def semantic_search(
    q: str = Query(..., description="Natural language search query"),
    top_k: int = Query(20, ge=1, le=100, description="Number of results to return"),
):
    """Semantic search over indexed PubMed abstracts.

    Find papers by meaning, not exact keyword match.
    Uses sentence-transformers embeddings + ChromaDB vector search.
    """
    result = run_semantic_search(query=q, top_k=top_k)
    return result
