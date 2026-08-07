"""Evidence Gatherer API router."""

from fastapi import APIRouter, HTTPException, Query

from med_research.diseases.base import Disease
from med_research.web.models.evidence import EvidenceGatherResponse, EvidenceItem
from med_research.web.services.evidence_service import run_evidence_gather

router = APIRouter(tags=["Evidence Gathering"])


@router.get("/api/evidence/gather", response_model=EvidenceGatherResponse)
async def evidence_gather(
    q: str = Query(..., min_length=2, max_length=500, description="Search query"),
    sources: str = Query(default="pubmed,preprints,clinical_trials,fda_labels,patents",
                         min_length=1, max_length=500,
                         description="Comma-separated source types"),
    max_per_source: int = Query(default=20, ge=1, le=100),
    use_cache: bool = Query(default=True),
    disease_id: str = Query("sle", description="Disease ID"),
):
    """Gather evidence from multiple biomedical sources simultaneously.

    Searches PubMed, preprints (bioRxiv/medRxiv), ClinicalTrials.gov,
    FDA labels (DailyMed), and patents — all with a single query.
    """
    source_list = [s.strip() for s in sources.split(",")]
    try:
        disease_name = Disease(disease_id).get_display_name()
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    search_query = q if disease_name.lower() in q.lower() else f"{disease_name} {q}"

    gathered = run_evidence_gather(
        query=search_query,
        sources=source_list,
        max_per_source=max_per_source,
        use_cache=use_cache,
        disease_id=disease_id,
    )

    raw_results = gathered.get("all_results", gathered.get("results", []))
    results = [
        EvidenceItem(
            title=r.get("title", ""),
            source=r.get("source", ""),
            source_type=r.get("source_type", ""),
            year=str(r.get("year", "")),
            url=r.get("url", ""),
            snippet=r.get("snippet", "")[:400],
            id=r.get("id", ""),
            citation_count=r.get("citation_count", 0),
        )
        for r in raw_results
    ]

    return EvidenceGatherResponse(
        query=gathered["query"],
        sources_searched=gathered["sources_searched"],
        total_results=gathered["total_results"],
        elapsed_seconds=gathered["elapsed_seconds"],
        results_by_source=gathered["results_by_source"],
        crossref=gathered.get("crossref", {}),
        results=results,
        generated_at=gathered["generated_at"],
        coverage=gathered.get("coverage", {}),
        status=gathered.get("status", "ready"),
    )
