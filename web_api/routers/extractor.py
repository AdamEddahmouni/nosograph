"""LLM Evidence Extractor API router."""

from fastapi import APIRouter, Query

from web_api.models.extractor import ExtractionResponse
from web_api.services.extractor_service import run_llm_extraction

router = APIRouter(tags=["LLM Extraction"])


@router.get("/api/llm/extract", response_model=ExtractionResponse)
async def llm_extract(
    q: str = Query(..., description="Search query (natural language)"),
    sources: str = Query("pubmed,preprints,clinical_trials",
                         description="Comma-separated source types"),
    max_articles: int = Query(20, ge=1, le=100,
                              description="Max articles to extract from"),
    model: str = Query("", description="LLM model name (default: gpt-4o-mini)"),
    use_cache: bool = Query(True, description="Use cached extractions"),
):
    """Extract structured data from biomedical evidence using an LLM.

    Gathers articles from the evidence gatherer, then uses an LLM
    (OpenAI-compatible API) to extract evidence levels, model systems,
    key findings, drug mentions, sample sizes, and more from each abstract.

    Requires OPENAI_API_KEY environment variable to be set.
    """
    return run_llm_extraction(
        query=q,
        sources=[s.strip() for s in sources.split(",")] if sources else None,
        max_articles=max_articles,
        model=model if model else None,
        use_cache=use_cache,
    )
