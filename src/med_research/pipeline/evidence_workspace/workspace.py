"""End-to-end Evidence-to-Hypothesis Workspace orchestration."""

from __future__ import annotations

from contextlib import suppress
from datetime import datetime, timezone
from typing import Callable
from uuid import uuid4

from med_research.diseases.base import Disease
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

ProgressCallback = Callable[[int, str], None]


def _report(callback: ProgressCallback | None, percent: int, message: str) -> None:
    """Emit progress without allowing UI/reporting failures to abort research."""
    if callback is None:
        return
    with suppress(Exception):
        callback(percent, message)


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
    graph=None,
    llm_client=None,
    model: str | None = None,
    progress_callback: ProgressCallback | None = None,
) -> EvidenceDossier:
    request = normalize_request(request)
    validate_disease_contract(request.disease_id)
    run_id = f"ew-{uuid4().hex}"
    _report(progress_callback, 5, "Validating research request")
    started = datetime.now(timezone.utc)
    search_terms = build_search_terms(request)
    _report(progress_callback, 10, "Building evidence search plan")
    source_map = sources or default_sources()
    statuses = []
    warnings = []
    records = []
    for index, source_name in enumerate(request.sources):
        percent, message = REPORTABLE_SOURCE_STEPS.get(
            source_name,
            (15 + int((index / max(len(request.sources), 1)) * 25), f"Searching {source_name}"),
        )
        _report(progress_callback, percent, message)
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
    _report(progress_callback, 45, "Normalizing and deduplicating evidence")
    records = deduplicate_evidence(records)[: request.max_evidence]
    _report(progress_callback, 55, "Extracting entities and evidence claims")
    extraction = extract_claims(records, request.disease_id, request.enable_llm, llm_client, model)
    warnings.extend(extraction.warnings)
    claims = extraction.claims
    drug_rankings = (
        rank_drugs(records, claims) if request.candidate_type in {"drugs", "both"} else []
    )
    target_rankings = (
        rank_targets(records, claims) if request.candidate_type in {"targets", "both"} else []
    )
    _report(progress_callback, 75, "Ranking candidate drugs and targets")
    graph_candidates = drug_rankings[:10] + target_rankings[:10]
    graph_explanations = build_graph_explanations(graph_candidates, request.disease_id, graph)
    graph_by_candidate = {item.candidate_id: item.explanation_id for item in graph_explanations}
    for ranking in graph_candidates:
        ranking.graph_explanation_ids = [graph_by_candidate[ranking.candidate_id]]
    completed = datetime.now(timezone.utc)
    try:
        request_dump = request.model_dump(mode="json")
    except TypeError:
        request_dump = request.model_dump()
    source_counts = {status.source: status.records_found for status in statuses}
    retrieval_times = {
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
    manifest = {
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
    _report(progress_callback, 100, "Evidence dossier ready")
    return dossier
