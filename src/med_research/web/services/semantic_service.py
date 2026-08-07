"""Semantic Search service layer."""

from med_research.pipeline.semantic_search.engine import (
    SemanticSearchEngine,
    last_coverage,
    resolve_semantic_coverage,
)


def run_semantic_search(query: str, top_k: int = 20, disease_id: str = "sle") -> dict:
    """Run semantic search and return serializable result."""
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

    engine = SemanticSearchEngine(disease_id=disease_id)
    indexed = engine.get_indexed_count()
    results = engine.search(query, top_k=top_k)
    coverage_payload = last_coverage.to_dict() if last_coverage else coverage.to_dict()

    return {
        "query": query,
        "results": results,
        "total_results": len(results),
        "indexed_articles": indexed,
        "coverage": coverage_payload,
        "status": (
            "limited_coverage"
            if coverage_payload.get("level") == "partial"
            else "ready"
        ),
    }
