"""Evidence source adapters for the workspace."""

from __future__ import annotations

from datetime import date, datetime, timezone
from hashlib import sha1
from typing import Any, Callable, Protocol, cast

from .schemas import EvidenceRecord, ResearchRequest, SourceName, SourceStatus


class SourceResult:
    def __init__(self, records: list[EvidenceRecord], status: SourceStatus):
        self.records = records
        self.status = status


class EvidenceSource(Protocol):
    name: SourceName

    def search(self, request: ResearchRequest, terms: list[str]) -> SourceResult: ...


def _parse_date(value: Any) -> date | None:
    if isinstance(value, date):
        return value
    if not value:
        return None
    text = str(value).strip()
    try:
        if len(text) == 4 and text.isdigit():
            return date(int(text), 1, 1)
        return date.fromisoformat(text[:10])
    except ValueError:
        return None


def _record_from_dict(item: dict[str, Any], source: SourceName, terms: list[str]) -> EvidenceRecord:
    native_id = str(
        item.get("native_id")
        or item.get("pmid")
        or item.get("nct_id")
        or item.get("accessionId")
        or item.get("setid")
        or item.get("id")
        or ""
    )
    source_prefix = {
        "pubmed": "pmid",
        "clinical_trials": "nct",
        "gwas": "gwas",
        "fda_labels": "spl",
    }[source]
    fallback = sha1(str(item.get("title", "")).encode("utf-8")).hexdigest()[:12]
    evidence_id = str(item.get("evidence_id") or f"{source_prefix}:{native_id or fallback}")
    published = _parse_date(
        item.get("published_date")
        or item.get("publication_date")
        or item.get("publicationInfo", {}).get("publicationDate")
        or item.get("updated_date")
        or item.get("year")
        or item.get("start_date")
    )
    url = str(
        item.get("url")
        or (
            {
                "pubmed": f"https://pubmed.ncbi.nlm.nih.gov/{native_id}/",
                "clinical_trials": f"https://clinicaltrials.gov/study/{native_id}",
                "gwas": f"https://www.ebi.ac.uk/gwas/studies/{native_id}",
                "fda_labels": f"https://dailymed.nlm.nih.gov/dailymed/drugInfo.cfm?setid={native_id}",
            }[source]
        )
    )
    source_ids = [str(value) for value in item.get("source_ids", []) if value]
    publication_info = item.get("publicationInfo") or {}
    if publication_info.get("pubmedId"):
        source_ids.append(str(publication_info["pubmedId"]))
    if native_id:
        source_ids.insert(0, native_id)
    return EvidenceRecord(
        evidence_id=evidence_id,
        source=source,
        native_id=native_id,
        source_ids=list(dict.fromkeys(source_ids)),
        title=str(item.get("title") or item.get("brief_title") or "Untitled evidence"),
        url=url,
        doi=item.get("doi"),
        snippet=str(
            item.get("snippet")
            or item.get("abstract")
            or item.get("summary")
            or item.get("indications")
            or item.get("reportedTrait")
            or ""
        ),
        published_date=published,
        source_date=published,
        evidence_type=str(
            item.get("evidence_type") or item.get("study_type") or item.get("phase") or "unknown"
        ),
        metadata={
            key: value
            for key, value in item.items()
            if key not in {"title", "url", "snippet", "abstract", "summary"}
        },
        query_context=terms,
        retrieval_time=datetime.now(timezone.utc),
    )


def _run_fetcher(
    source: SourceName,
    request: ResearchRequest,
    terms: list[str],
    fetcher: Callable[[str, int], list[dict[str, Any]]],
) -> SourceResult:
    query = " OR ".join(f"({term})" for term in terms)
    try:
        raw = fetcher(query, request.max_evidence)
        all_records = [_record_from_dict(item, source, terms) for item in (raw or [])]
        undated = sum(record.published_date is None for record in all_records)
        records = all_records
        if request.date_from or request.date_to:
            records = [
                record
                for record in records
                if record.published_date is not None
                and (request.date_from is None or record.published_date >= request.date_from)
                and (request.date_to is None or record.published_date <= request.date_to)
            ]
        warning = None
        status = "ok"
        if (request.date_from or request.date_to) and undated:
            status = "warning"
            warning = (
                f"{source} returned {undated} undated record(s); "
                "they were excluded by the requested date filter."
            )
        return SourceResult(
            records,
            SourceStatus(
                source=source,
                status=cast(Any, status),
                records_found=len(records),
                warning=warning,
                query_terms=terms,
                retrieval_mode="unknown",
            ),
        )
    except Exception as exc:
        return SourceResult(
            [],
            SourceStatus(
                source=source,
                status="error",
                warning=f"{source} source failed: {type(exc).__name__}: {exc}",
                query_terms=terms,
                retrieval_mode="unknown",
            ),
        )


class PubMedSource:
    name: SourceName = "pubmed"

    def __init__(self, fetcher: Callable[[str, int], list[dict[str, Any]]] | None = None):
        if fetcher is None:
            from med_research.pipeline.evidence.gatherer import search_europe_pmc

            def fetcher(query: str, limit: int) -> list[dict[str, Any]]:
                return search_europe_pmc(query, "pubmed", limit)

        self.fetcher = fetcher

    def search(self, request: ResearchRequest, terms: list[str]) -> SourceResult:
        return _run_fetcher(self.name, request, terms, self.fetcher)


def _fetch_gwas_live(query: str, limit: int) -> list[dict[str, Any]]:
    """Fetch GWAS studies while preserving HTTP failures for source isolation."""
    import requests

    response = requests.get(
        "https://www.ebi.ac.uk/gwas/rest/api/studies/search/findByDiseaseTrait",
        params=cast(dict[str, str | int], {"diseaseTrait": query, "size": min(limit, 50)}),
        timeout=30,
    )
    response.raise_for_status()
    return cast(
        list[dict[str, Any]], response.json().get("_embedded", {}).get("studies", [])[:limit]
    )


def _fetch_fda_live(query: str, limit: int) -> list[dict[str, Any]]:
    """Fetch DailyMed labels while preserving HTTP failures for source isolation."""
    import requests

    response = requests.get(
        "https://dailymed.nlm.nih.gov/dailymed/services/v2/spls.json",
        params=cast(dict[str, str | int], {"searchterms": query, "pagesize": min(limit, 50)}),
        timeout=30,
    )
    response.raise_for_status()
    return cast(list[dict[str, Any]], response.json().get("data", [])[:limit])


class GWASSource:
    name: SourceName = "gwas"

    def __init__(self, fetcher: Callable[[str, int], list[dict[str, Any]]] | None = None):
        if fetcher is None:
            fetcher = _fetch_gwas_live
        self.fetcher = fetcher

    def search(self, request: ResearchRequest, terms: list[str]) -> SourceResult:
        return _run_fetcher(self.name, request, terms, self.fetcher)


class FDALabelSource:
    name: SourceName = "fda_labels"

    def __init__(self, fetcher: Callable[[str, int], list[dict[str, Any]]] | None = None):
        if fetcher is None:
            fetcher = _fetch_fda_live
        self.fetcher = fetcher

    def search(self, request: ResearchRequest, terms: list[str]) -> SourceResult:
        return _run_fetcher(self.name, request, terms, self.fetcher)


class ClinicalTrialsSource:
    name: SourceName = "clinical_trials"

    def __init__(self, fetcher: Callable[[str, int], list[dict[str, Any]]] | None = None):
        if fetcher is None:
            from med_research.pipeline.evidence.gatherer import search_clinical_trials

            fetcher = search_clinical_trials
        self.fetcher = fetcher

    def search(self, request: ResearchRequest, terms: list[str]) -> SourceResult:
        return _run_fetcher(self.name, request, terms, self.fetcher)


def default_sources() -> dict[SourceName, EvidenceSource]:
    return {
        "pubmed": PubMedSource(),
        "clinical_trials": ClinicalTrialsSource(),
        "gwas": GWASSource(),
        "fda_labels": FDALabelSource(),
    }
