"""Semantic Search service layer."""


def run_semantic_search(query: str, top_k: int = 20, disease_id: str = "sle") -> dict:
    """Run semantic search and return serializable result."""
    from med_research.pipeline.semantic_search.engine import SemanticSearchEngine

    engine = SemanticSearchEngine(disease_id=disease_id)
    indexed = engine.get_indexed_count()
    results = engine.search(query, top_k=top_k)

    return {
        "query": query,
        "results": results,
        "total_results": len(results),
        "indexed_articles": indexed,
    }
