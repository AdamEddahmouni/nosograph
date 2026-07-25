"""Semantic Search service layer."""


def run_semantic_search(query: str, top_k: int = 20) -> dict:
    """Run semantic search and return serializable result."""
    from semantic_search.engine import SemanticSearchEngine

    engine = SemanticSearchEngine()
    indexed = engine.get_indexed_count()
    results = engine.search(query, top_k=top_k)

    return {
        "query": query,
        "results": results,
        "total_results": len(results),
        "indexed_articles": indexed,
    }
