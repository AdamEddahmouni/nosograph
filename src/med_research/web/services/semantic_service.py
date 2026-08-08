"""Semantic Search service layer."""

from med_research.pipeline.semantic_search.engine import last_coverage, resolve_semantic_coverage
from med_research.web.services.registry_service import run_module


def run_semantic_search(query: str, top_k: int = 20, disease_id: str = "sle") -> dict:
    """Run semantic search via the semantic_search registry adapter."""
    coverage = resolve_semantic_coverage(disease_id)
    if not coverage.is_runnable:
        return {
            "query": query,
            "results": [],
            "total_results": 0,
            "indexed_articles": 0,
            "coverage": coverage.to_dict(),
            "status": "blocked",
        }

    raw = run_module("semantic_search", disease_id, query=query, top=top_k)
    results = raw.get("results", [])
    coverage_payload = last_coverage.to_dict() if last_coverage else coverage.to_dict()

    return {
        "query": query,
        "results": results,
        "total_results": len(results),
        "indexed_articles": raw.get("indexed_count", 0),
        "coverage": coverage_payload,
        "status": (
            "limited_coverage"
            if coverage_payload.get("level") == "partial"
            else "ready"
        ),
    }
