"""End-to-end Evidence-to-Hypothesis Workspace orchestration."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from med_research.diseases.base import Disease
from med_research.pipeline.progress import StandardProgress, _tick
from med_research.pipeline.provenance import build_provenance, package_version

from .extraction import extract_claims
from .graph import build_graph_explanations
from .ranking import rank_drugs, rank_targets
from .schemas import (
    EvidenceDossier,
    ResearchRequest,
    SourceStatus,
    deduplicate_evidence,
    normalize_request,
)
from .sources import EvidenceSource, default_sources

REPORTABLE_SOURCE_STEPS = {
    "pubmed": (20, "Searching PubMed evidence"),
    "clinical_trials": (35, "Searching ClinicalTrials.gov evidence"),
}


def build_search_terms(request: ResearchRequest) -> list[str]:
    disease = Disease(request.disease_id)
    terms = [request.question, disease.profile.name]
    terms.extend(disease.get_gwas_search_terms())
    return list(dict.fromkeys(term.strip() for term in terms if term and term.strip()))


def validate_disease_contract(disease_id: str) -> None:
    """Fail before evidence work when a disease has unusable core configuration."""
    gaps = {field: status for field, status in Disease(disease_id).validate().items() if status != "ok"}
    if gaps:
        details = ", ".join(f"{field}: {status}" for field, status in gaps.items())
        raise ValueError(f"incomplete disease configuration for {disease_id}: {details}")


def run_workspace(
    request: ResearchRequest | dict,
    sources: dict[str, EvidenceSource] | None = None,
    graph: Any = None,
    llm_client: Any = None,
    model: str | None = None,
    progress_callback: StandardProgress | None = None,
) -> EvidenceDossier:
    request = normalize_request(request)
    validate_disease_contract(request.disease_id)
    run_id = f"ew-{uuid4().hex}"
    _tick(progress_callback, "validating request", 1, 8)
    started = datetime.now(timezone.utc)
    search_terms = build_search_terms(request)
    _tick(progress_callback, "building search plan", 2, 8)
    source_map = sources or default_sources()
    statuses = []
    warnings = []
    records = []
    for index, source_name in enumerate(request.sources, 1):
        _, step_name = REPORTABLE_SOURCE_STEPS.get(
            source_name,
            (None, f"searching {source_name}"),
        )
        _tick(progress_callback, step_name, index, len(request.sources))
        source = source_map.get(source_name)
        if source is None:
            statuses.append(
                SourceStatus(
                    source=source_name,
                    status="skipped",
                    warning="No adapter configured.",
                    retrieval_mode="unknown",
                )
            )
            warnings.append(f"No adapter configured for {source_name}.")
            continue
        result = source.search(request, search_terms)
        statuses.append(result.status)
        records.extend(result.records)
        if result.status.warning:
            warnings.append(result.status.warning)
    _tick(progress_callback, "deduplicating evidence", 4, 8)
    records = deduplicate_evidence(records)[: request.max_evidence]
    _tick(progress_callback, "extracting claims", 5, 8)
    extraction = extract_claims(records, request.disease_id, request.enable_llm, llm_client, model)
    warnings.extend(extraction.warnings)
    claims = extraction.claims
    drug_rankings = (
        rank_drugs(records, claims) if request.candidate_type in {"drugs", "both"} else []
    )
    target_rankings = (
        rank_targets(records, claims) if request.candidate_type in {"targets", "both"} else []
    )
    _tick(progress_callback, "ranking candidates", 6, 8)
    graph_candidates = drug_rankings[:10] + target_rankings[:10]
    graph_explanations = build_graph_explanations(graph_candidates, request.disease_id, graph)
    graph_by_candidate = {item.candidate_id: item.explanation_id for item in graph_explanations}
    for ranking in graph_candidates:
        ranking.graph_explanation_ids = [graph_by_candidate[ranking.candidate_id]]
    _tick(progress_callback, "building dossier", 7, 8)
    completed = datetime.now(timezone.utc)
    try:
        request_dump = request.model_dump(mode="json")
    except TypeError:
        request_dump = request.model_dump()
    source_counts = {status.source: status.records_found for status in statuses}
    retrieval_times: dict[str, str] = {
        status.source: status.retrieved_at.isoformat() for status in statuses
    }
    retrieval_modes = {
        status.retrieval_mode
        for status in statuses
        if status.status != "skipped"
    }
    known_modes = retrieval_modes - {"unknown"}
    cache_or_live = (
        next(iter(known_modes))
        if len(known_modes) == 1 and retrieval_modes == known_modes
        else "mixed"
        if known_modes
        else "unknown"
    )
    manifest: dict[str, Any] = {
        "package_version": package_version(),
        "sources": list(request.sources),
        "source_counts": source_counts,
        "llm": {"requested": request.enable_llm, "status": extraction.llm_status, "model": model},
        "cache_or_live": cache_or_live,
        "provenance": build_provenance(
            disease_id=request.disease_id,
            module="evidence_workspace",
            sources=request.sources,
            query=request.question,
            filters={
                "date_from": request.date_from,
                "date_to": request.date_to,
                "candidate_type": request.candidate_type,
                "max_evidence": request.max_evidence,
            },
            cache_or_live=cache_or_live,
            model=model,
            scoring={
                "ranking": "support/contradiction/recency/quality heuristic",
                "candidate_type": request.candidate_type,
            },
            inputs={"search_terms": search_terms, "source_counts": source_counts},
            run_id=run_id,
            retrieval_times=retrieval_times,
        ),
    }
    manifest["fingerprint"] = manifest["provenance"]["fingerprint"]
    limitations = [
        "Evidence and rankings depend on the selected sources and retrieval window.",
        "Entity extraction is deterministic pattern matching unless validated LLM enrichment is enabled.",
        "Rankings are computational prioritization heuristics and do not establish treatment efficacy.",
    ]
    dossier = EvidenceDossier(
        run_id=run_id,
        request=request,
        search_terms=search_terms,
        started_at=started,
        completed_at=completed,
        source_statuses=statuses,
        evidence=records,
        claims=claims,
        drug_rankings=drug_rankings,
        target_rankings=target_rankings,
        graph_explanations=graph_explanations,
        warnings=warnings,
        limitations=limitations,
        manifest={"request": request_dump, **manifest},
    )
    _tick(progress_callback, "evidence dossier ready", 8, 8)
    return dossier
