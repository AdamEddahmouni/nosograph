"""Evidence Gatherer service layer."""

from med_research.web.services.registry_service import run_module


def run_evidence_gather(
    query: str,
    sources: list = None,
    max_per_source: int = 20,
    use_cache: bool = True,
    disease_id: str | None = None,
) -> dict:
    """Run the evidence gatherer via the evidence_gather registry adapter."""
    disease_id = disease_id or "sle"
    result = run_module(
        "evidence_gather",
        disease_id,
        query=query,
        sources=sources,
        max_per_source=max_per_source,
        use_cache=use_cache,
    )
    if "all_results" in result and "results" not in result:
        result["results"] = result["all_results"]
    return result
