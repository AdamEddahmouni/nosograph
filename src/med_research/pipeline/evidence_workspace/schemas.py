"""Typed contracts for the Evidence-to-Hypothesis Workspace."""

from __future__ import annotations

from datetime import date, datetime, timezone
from typing import Any, Callable, Literal, cast
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

SourceName = Literal[
    "pubmed", "clinical_trials", "gwas", "fda_labels", "opentargets", "gtex", "biorxiv", "chembl"
]
CandidateType = Literal["drugs", "targets", "both"]

# Persisted schema versions are intentionally separate from the runtime model
# classes. Runtime requests/results can evolve without making old SQLite JSON
# payloads impossible to read.
WORKSPACE_REQUEST_SCHEMA_VERSION: Literal["1.0"] = "1.0"
WORKSPACE_RESULT_SCHEMA_VERSION: Literal["1.1"] = "1.1"

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
    model: str | None = None

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
        return cast(tuple[str, ...], value)

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


class WorkspaceRequestV1(ResearchRequest):
    """Versioned request shape written to persistent run storage."""

    schema_version: Literal["1.0"] = WORKSPACE_REQUEST_SCHEMA_VERSION


class EvidenceDossier(WorkspaceModel):
    schema_version: str = WORKSPACE_RESULT_SCHEMA_VERSION
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


class WorkspaceResultV1(EvidenceDossier):
    """Versioned result shape written to persistent run storage."""

    schema_version: Literal["1.1"] = WORKSPACE_RESULT_SCHEMA_VERSION
    request: WorkspaceRequestV1


WorkspaceMigration = Callable[[dict[str, Any]], dict[str, Any]]
WorkspaceMigrationKind = Literal["request", "result"]


def _request_legacy_to_v1(payload: dict[str, Any]) -> dict[str, Any]:
    migrated = dict(payload)
    migrated["schema_version"] = WORKSPACE_REQUEST_SCHEMA_VERSION
    return migrated


def _result_legacy_to_v1(payload: dict[str, Any]) -> dict[str, Any]:
    migrated = dict(payload)
    migrated["schema_version"] = "1.0"
    return migrated


def _result_v1_to_v1_1(payload: dict[str, Any]) -> dict[str, Any]:
    migrated = dict(payload)
    migrated.setdefault("graph_explanations", [])
    migrated.setdefault("limitations", [])
    migrated["schema_version"] = WORKSPACE_RESULT_SCHEMA_VERSION
    return migrated


# Each edge is one intentionally small upgrade. Future versions append an edge
# rather than replacing old migrations, allowing legacy rows to upgrade through
# every intermediate contract in a deterministic chain.
WORKSPACE_REQUEST_MIGRATIONS: dict[tuple[str, str], WorkspaceMigration] = {
    ("legacy", WORKSPACE_REQUEST_SCHEMA_VERSION): _request_legacy_to_v1,
}
WORKSPACE_RESULT_MIGRATIONS: dict[tuple[str, str], WorkspaceMigration] = {
    ("legacy", "1.0"): _result_legacy_to_v1,
    ("1.0", WORKSPACE_RESULT_SCHEMA_VERSION): _result_v1_to_v1_1,
}


def register_workspace_migration(
    kind: WorkspaceMigrationKind,
    from_version: str,
    to_version: str,
    migration: WorkspaceMigration,
) -> None:
    """Register one immutable edge in the request/result migration graph."""
    if from_version == to_version:
        raise ValueError("Workspace migration versions must differ")
    registry = WORKSPACE_REQUEST_MIGRATIONS if kind == "request" else WORKSPACE_RESULT_MIGRATIONS
    edge = (from_version, to_version)
    if edge in registry:
        raise ValueError(f"Workspace migration already registered: {kind} {edge}")
    registry[edge] = migration


def _apply_workspace_migration_chain(
    payload: dict[str, Any],
    *,
    kind: WorkspaceMigrationKind,
    from_version: str,
    to_version: str,
) -> dict[str, Any]:
    """Apply registered migration edges until the target version is reached."""
    if from_version == to_version:
        return dict(payload)
    registry = WORKSPACE_REQUEST_MIGRATIONS if kind == "request" else WORKSPACE_RESULT_MIGRATIONS
    current = from_version
    migrated = dict(payload)
    visited: set[str] = set()
    while current != to_version:
        if current in visited:
            raise ValueError(f"Workspace {kind} migration cycle at version {current}")
        visited.add(current)
        edges = [
            (destination, step)
            for (source, destination), step in registry.items()
            if source == current
        ]
        if not edges:
            raise ValueError(f"Unsupported Workspace {kind} schema version: {from_version}")
        if len(edges) > 1:
            raise ValueError(f"Ambiguous Workspace {kind} migrations from version {current}")
        destination, step = edges[0]
        migrated = step(migrated)
        if migrated.get("schema_version") != destination:
            raise ValueError(f"Workspace {kind} migration did not produce version {destination}")
        current = destination
    return migrated


def normalize_request(request: ResearchRequest | dict[str, Any]) -> ResearchRequest:
    """Validate and normalize a request from Python or JSON-compatible input."""
    return (
        request if isinstance(request, ResearchRequest) else ResearchRequest.model_validate(request)
    )


def serialize_workspace_request(
    request: ResearchRequest | dict[str, Any],
) -> dict[str, Any]:
    """Serialize a request with its migration version marker."""
    normalized = normalize_request(request)
    return WorkspaceRequestV1.model_validate(normalized.model_dump(mode="json")).model_dump(
        mode="json"
    )


def migrate_workspace_request(payload: ResearchRequest | dict[str, Any]) -> ResearchRequest:
    """Load current or legacy persisted request JSON into the runtime model."""
    if isinstance(payload, ResearchRequest):
        return payload
    if not isinstance(payload, dict):
        raise TypeError("Workspace request payload must be a mapping")

    raw: dict[str, Any] = dict(payload)
    version = raw.pop("schema_version", None) or "legacy"
    migrated = _apply_workspace_migration_chain(
        raw,
        kind="request",
        from_version=str(version),
        to_version=WORKSPACE_REQUEST_SCHEMA_VERSION,
    )
    migrated.pop("schema_version", None)
    return ResearchRequest.model_validate(migrated)


def serialize_workspace_result(dossier: EvidenceDossier) -> dict[str, Any]:
    """Serialize a dossier with its migration version marker."""
    versioned = WorkspaceResultV1.model_validate(dossier.model_dump(mode="json"))
    for target, source in zip(versioned.evidence, dossier.evidence, strict=True):
        for field in ("quality_tier", "quality_score", "quality_rationale"):
            object.__setattr__(target, field, getattr(source, field))
    return versioned.model_dump(mode="json")


def migrate_workspace_result(payload: EvidenceDossier | dict[str, Any]) -> EvidenceDossier:
    """Migrate a persisted dossier into the current result model.

    Version ``1.0`` and unversioned payloads are accepted as legacy results;
    fields introduced in the current result contract are populated by their
    model defaults before the payload is returned as version ``1.1``.
    """
    if isinstance(payload, EvidenceDossier):
        return payload
    if not isinstance(payload, dict):
        raise TypeError("Workspace result payload must be a mapping")

    raw: dict[str, Any] = dict(payload)
    version = raw.get("schema_version") or "legacy"
    raw = _apply_workspace_migration_chain(
        raw,
        kind="result",
        from_version=str(version),
        to_version=WORKSPACE_RESULT_SCHEMA_VERSION,
    )

    nested_request = raw.get("request")
    if isinstance(nested_request, dict):
        raw["request"] = migrate_workspace_request(nested_request).model_dump(mode="json")

    migrated = EvidenceDossier.model_validate(raw)
    # Result validation classifies evidence quality for newly created records;
    # migration must preserve persisted analyst/source quality values exactly.
    for record, raw_record in zip(migrated.evidence, raw.get("evidence", []), strict=True):
        if not isinstance(raw_record, dict):
            continue
        for field in ("quality_tier", "quality_score", "quality_rationale"):
            if field in raw_record:
                object.__setattr__(record, field, raw_record[field])
    return migrated


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
