"""LLM Extractor service — wraps extract_all via module registry."""

from med_research.web.services.registry_service import run_module


def run_llm_extraction(
    query: str,
    sources: list = None,
    max_articles: int = 20,
    model: str = None,
    use_cache: bool = True,
    disease_id: str | None = None,
) -> dict:
    """Run LLM evidence extraction via the llm_extractor registry adapter."""
    return run_module(
        "llm_extractor",
        disease_id or "sle",
        query=query,
        sources=sources,
        max_articles=max_articles,
        model=model,
        use_cache=use_cache,
    )
