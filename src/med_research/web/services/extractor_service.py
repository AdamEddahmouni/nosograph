"""LLM Extractor service — thin wrapper around extract_all()."""

from med_research.pipeline.evidence.extractor import extract_all


def run_llm_extraction(
    query: str,
    sources: list = None,
    max_articles: int = 20,
    model: str = None,
    use_cache: bool = True,
) -> dict:
    """Run LLM evidence extraction and return structured results.

    Args:
        query: Search query string.
        sources: List of source types.
        max_articles: Max articles to extract from.
        model: LLM model name.
        use_cache: Whether to use cached extractions.

    Returns:
        Dict with extractions, stats, and metadata.
    """
    return extract_all(
        query=query,
        sources=sources,
        max_articles=max_articles,
        model=model,
        use_cache=use_cache,
    )
