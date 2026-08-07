"""Typed contracts for the Evidence-to-Hypothesis Workspace."""

from __future__ import annotations

from datetime import date, datetime, timezone
from typing import Any, Literal
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

SourceName = Literal["pubmed", "clinical_trials", "gwas", "fda_labels"]
CandidateType = Literal["drugs", "targets", "both"]
ClaimRelationship = Literal[
    "supports",
    "contradicts",
    "associated_with",
    "targets",
    "participates_in",
]


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _canonical_url(value: str) -> str:
    parsed = urlsplit(value.strip())
    if not parsed.scheme or not parsed.netloc:
        return value.strip()
    query = ""
    if parsed.netloc.lower() == "dailymed.nlm.nih.gov" and parsed.query:
        query_pairs = [(key, value) for key, value in parse_qsl(parsed.query) if key == "setid"]
        query = urlencode(query_pairs)
    return urlunsplit(
        (parsed.scheme.lower(), parsed.netloc.lower(), parsed.path.rstrip("/") or "/", query, "")
    )


class WorkspaceModel(BaseModel):
    model_config = ConfigDict(extra="forbid", validate_assignment=True)


class ResearchRequest(WorkspaceModel):
    """Normalized user request for one reproducible research run."""

    disease_id: str = "sle"
    question: str = Field(min_length=2, max_length=500)
    sources: tuple[SourceName, ...] = ("pubmed", "clinical_trials")
    date_from: date | None = None
    date_to: date | None = None
    candidate_type: CandidateType = "both"
    max_evidence: int = Field(default=50, ge=1, le=200)
    enable_llm: bool = True

    @field_validator("disease_id", mode="before")
    @classmethod
    def normalize_disease_id(cls, value: str) -> str:
        value = str(value).strip().lower()
        if not value:
            raise ValueError("disease_id must not be empty")
        try:
            from med_research.diseases.base import Disease

            if value not in Disease.list_all():
                raise ValueError(f"unknown disease_id: {value}")
        except ImportError:
            # Keep schema construction usable in isolated tooling environments;
            # the pipeline validates the concrete disease before execution.
            pass
        return value

    @field_validator("question", mode="before")
    @classmethod
    def normalize_question(cls, value: str) -> str:
        value = str(value).strip()
        if not value:
            raise ValueError("question must not be empty")
        return value

    @field_validator("sources", mode="before")
    @classmethod
    def normalize_sources(cls, value: Any) -> tuple[str, ...]:
        if isinstance(value, str):
            value = tuple(item.strip() for item in value.split(",") if item.strip())
        value = tuple(value)
        if not value:
            raise ValueError("at least one evidence source is required")
        return value

    @model_validator(mode="after")
    def validate_dates(self) -> "ResearchRequest":
        if self.date_from and self.date_to and self.date_from > self.date_to:
            raise ValueError("date_from must be on or before date_to")
        return self


class Citation(WorkspaceModel):
    source: SourceName
    native_id: str = ""
    title: str = ""
    doi: str | None = None
    url: str
    published_date: date | None = None
    citation_quality: Literal["complete", "limited"] = "complete"

    @field_validator("url")
    @classmethod
    def normalize_url(cls, value: str) -> str:
        return _canonical_url(value)

    @model_validator(mode="after")
    def classify_quality(self) -> "Citation":
        if not self.native_id and not self.doi:
            self.citation_quality = "limited"
        return self


class EvidenceRecord(WorkspaceModel):
    evidence_id: str
    source: SourceName
    native_id: str = ""
    source_ids: list[str] = Field(default_factory=list)
    title: str
    url: str
    doi: str | None = None
    snippet: str = ""
    published_date: date | None = None
    evidence_type: str = "unknown"
    metadata: dict[str, Any] = Field(default_factory=dict)
    query_context: list[str] = Field(default_factory=list)
    retrieval_time: datetime = Field(default_factory=_utc_now)
    source_date: date | None = None
    quality_tier: Literal["tier_1", "tier_2", "tier_3", "tier_4"] = "tier_3"
    quality_score: float = Field(default=0.6, ge=0, le=1)
    quality_rationale: str = "Evidence quality is estimated from source and study type metadata."

    def _apply_quality_classification(self) -> None:
        study_type = self.evidence_type.lower().replace("-", " ").replace("_", " ")
        if self.source == "fda_labels":
            tier, score, rationale = (
                "tier_1",
                0.95,
                "Regulatory label evidence is based on an authorized product label.",
            )
        elif self.source == "clinical_trials" and any(
            term in study_type for term in ("randomized", "rct", "phase 2", "phase 3", "phase3")
        ):
            tier, score, rationale = (
                "tier_1",
                0.9,
                "Randomized or late-phase clinical trial evidence has stronger internal validity.",
            )
        elif self.source == "gwas":
            tier, score, rationale = (
                "tier_2",
                0.65,
                "GWAS evidence supports statistical association and requires causal validation.",
            )
        elif "preprint" in study_type:
            tier, score, rationale = (
                "tier_4",
                0.35,
                "Preprint evidence has not completed formal peer review.",
            )
        elif any(
            term in study_type
            for term in ("observational", "cohort", "case control", "case-control")
        ):
            tier, score, rationale = (
                "tier_2",
                0.55,
                "Observational evidence is useful for real-world outcomes but remains confounding-sensitive.",
            )
        elif self.source == "clinical_trials":
            tier, score, rationale = (
                "tier_2",
                0.7,
                "Clinical-trial registry evidence is informative but study design details may be incomplete.",
            )
        else:
            tier, score, rationale = (
                "tier_3",
                0.6,
                "Peer-reviewed biomedical evidence requires study-specific appraisal.",
            )
        object.__setattr__(self, "quality_tier", tier)
        object.__setattr__(self, "quality_score", score)
        object.__setattr__(self, "quality_rationale", rationale)

    def __setattr__(self, name: str, value: Any) -> None:
        super().__setattr__(name, value)
        if (
            name in {"source", "evidence_type"}
            and "source" in self.__dict__
            and "evidence_type" in self.__dict__
        ):
            self._apply_quality_classification()

    @field_validator("url")
    @classmethod
    def normalize_url(cls, value: str) -> str:
        return _canonical_url(value)

    @model_validator(mode="after")
    def classify_quality(self) -> "EvidenceRecord":
        self._apply_quality_classification()
        return self

    @field_validator("source_ids")
    @classmethod
    def unique_source_ids(cls, value: list[str]) -> list[str]:
        return list(dict.fromkeys(item for item in value if item))

    @model_validator(mode="after")
    def ensure_native_provenance(self) -> "EvidenceRecord":
        if self.native_id and self.native_id not in self.source_ids:
            self.source_ids.insert(0, self.native_id)
        return self


class Claim(WorkspaceModel):
    claim_id: str
    subject_id: str
    subject_type: Literal["drug", "target", "gene", "pathway", "variant", "outcome", "other"]
    subject_name: str
    relationship: ClaimRelationship
    text: str
    evidence_ids: list[str] = Field(min_length=1)
    citations: list[Citation] = Field(default_factory=list)
    supporting_snippet: str = ""
    evidence_type: str = "unknown"
    confidence: float = Field(ge=0, le=1)
    confidence_components: dict[str, float] = Field(default_factory=dict)
    extraction_method: Literal["rules", "llm"]
    model_name: str | None = None
    extracted_at: datetime = Field(default_factory=_utc_now)
    limitations: list[str] = Field(default_factory=list)
    conflict_group: str | None = None


class RankedCandidate(WorkspaceModel):
    candidate_id: str
    candidate_type: Literal["drug", "target"]
    name: str
    score: float = Field(ge=0, le=100)
    confidence_band: Literal["low", "moderate", "high"]
    component_scores: dict[str, float] = Field(default_factory=dict)
    explanation: str
    supporting_claim_ids: list[str] = Field(default_factory=list)
    contradicting_claim_ids: list[str] = Field(default_factory=list)
    citation_ids: list[str] = Field(default_factory=list)
    graph_explanation_ids: list[str] = Field(default_factory=list)


class GraphExplanation(WorkspaceModel):
    explanation_id: str
    candidate_id: str
    status: Literal["found", "no_path_found"]
    path_node_ids: list[str] = Field(default_factory=list)
    path_labels: list[str] = Field(default_factory=list)
    relationship_labels: list[str] = Field(default_factory=list)
    reason: str = ""


class SourceStatus(WorkspaceModel):
    source: SourceName
    status: Literal["ok", "warning", "error", "skipped"]
    records_found: int = 0
    warning: str | None = None
    query_terms: list[str] = Field(default_factory=list)
    retrieval_mode: Literal["cache", "live", "mixed", "unknown"] = "unknown"
    retrieved_at: datetime = Field(default_factory=_utc_now)


class EvidenceDossier(WorkspaceModel):
    schema_version: str = "1.1"
    run_id: str
    request: ResearchRequest
    search_terms: list[str] = Field(default_factory=list)
    started_at: datetime
    completed_at: datetime
    source_statuses: list[SourceStatus] = Field(default_factory=list)
    evidence: list[EvidenceRecord] = Field(default_factory=list)
    claims: list[Claim] = Field(default_factory=list)
    drug_rankings: list[RankedCandidate] = Field(default_factory=list)
    target_rankings: list[RankedCandidate] = Field(default_factory=list)
    graph_explanations: list[GraphExplanation] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    limitations: list[str] = Field(default_factory=list)
    manifest: dict[str, Any] = Field(default_factory=dict)
    disclaimer: str = (
        "For research purposes only. This computational prioritization is not medical advice "
        "and requires experimental and clinical validation."
    )


def normalize_request(request: ResearchRequest | dict[str, Any]) -> ResearchRequest:
    """Validate and normalize a request from Python or JSON-compatible input."""
    return (
        request if isinstance(request, ResearchRequest) else ResearchRequest.model_validate(request)
    )


def _dedupe_key(record: EvidenceRecord) -> tuple[str, str]:
    if record.native_id:
        return record.source, record.native_id.lower()
    if record.doi:
        return "doi", record.doi.lower()
    return "url", record.url


def deduplicate_evidence(records: list[EvidenceRecord]) -> list[EvidenceRecord]:
    """Merge duplicate source records without dropping identifiers or metadata."""
    merged: dict[tuple[str, str], EvidenceRecord] = {}
    for record in records:
        key = _dedupe_key(record)
        existing = merged.get(key)
        if existing is None:
            merged[key] = record.model_copy(deep=True)
            continue
        if len(record.snippet) > len(existing.snippet):
            existing.snippet = record.snippet
        for field in ("doi", "published_date", "source_date", "evidence_type"):
            if getattr(existing, field) in (None, "", "unknown") and getattr(record, field):
                setattr(existing, field, getattr(record, field))
        existing.source_ids = list(dict.fromkeys(existing.source_ids + record.source_ids))
        existing.query_context = list(dict.fromkeys(existing.query_context + record.query_context))
        existing.metadata = {**record.metadata, **existing.metadata}
    return list(merged.values())
