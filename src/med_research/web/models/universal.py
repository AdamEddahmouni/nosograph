"""Pydantic models for the versioned universal biomedical API."""

from __future__ import annotations

from datetime import datetime
from typing import Generic, Literal, TypeVar
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

EntityTypeLiteral = Literal[
    "condition",
    "phenotype",
    "gene",
    "pathway",
    "intervention",
    "biomarker",
    "measurement",
    "exposure",
    "outcome",
]

PredicateLiteral = Literal[
    "IS_A",
    "HAS_PHENOTYPE",
    "ASSOCIATED_WITH_GENE",
    "INVOLVES_PATHWAY",
    "TREATED_BY",
    "HAS_BIOMARKER",
    "HAS_MEASUREMENT",
    "ASSOCIATED_WITH_EXPOSURE",
    "HAS_OUTCOME",
]

EvidenceDirectionLiteral = Literal["supporting", "contradictory"]

MappingKindLiteral = Literal["exact", "close", "broad", "narrow"]

RunStatusLiteral = Literal["pending", "running", "completed", "failed"]

RESEARCH_DISCLAIMER_TEXT = (
    "For research and exploratory analysis only. Results summarize supporting evidence "
    "and contradictory evidence from imported biomedical sources. Not for clinical "
    "decision-making, treatment recommendations, or probability-of-disease claims."
)

T = TypeVar("T")


class ResearchDisclaimer(BaseModel):
    model_config = ConfigDict(frozen=True)

    text: str = Field(default=RESEARCH_DISCLAIMER_TEXT)
    schema_version: str = "1.0"


class EntitySummaryView(BaseModel):
    model_config = ConfigDict(frozen=True)

    curie: str
    label: str
    entity_type: EntityTypeLiteral


class EntityMappingView(BaseModel):
    model_config = ConfigDict(frozen=True)

    subject_curie: str
    object_curie: str
    relation: MappingKindLiteral
    can_auto_join: bool
    source_record_id: str = ""


class SnapshotSummary(BaseModel):
    model_config = ConfigDict(frozen=True)

    id: UUID
    resource_name: str
    version: str
    checksum: str
    active: bool
    imported_at: datetime | None = None
    counts: dict[str, int] = Field(default_factory=dict)


class ReadinessBadge(BaseModel):
    model_config = ConfigDict(frozen=True)

    ontology_present: bool
    legacy_curated: bool
    legacy_disease_id: str | None = None
    message: str = ""


class ConditionSummary(BaseModel):
    model_config = ConfigDict(frozen=True)

    curie: str
    label: str
    entity_type: EntityTypeLiteral
    definition: str = ""
    synonyms: list[str] = Field(default_factory=list)
    mappings: list[EntityMappingView] = Field(default_factory=list)
    snapshots: list[SnapshotSummary] = Field(default_factory=list)
    readiness: ReadinessBadge
    disclaimer: ResearchDisclaimer = Field(default_factory=ResearchDisclaimer)


class HierarchyNode(BaseModel):
    model_config = ConfigDict(frozen=True)

    curie: str
    label: str
    depth: int
    relation: Literal["self", "parent", "child"]


class ConditionHierarchy(BaseModel):
    model_config = ConfigDict(frozen=True)

    curie: str
    depth_limit: int
    nodes: list[HierarchyNode] = Field(default_factory=list)
    disclaimer: ResearchDisclaimer = Field(default_factory=ResearchDisclaimer)


class ClaimEvidenceView(BaseModel):
    model_config = ConfigDict(frozen=True)

    id: UUID
    direction: EvidenceDirectionLiteral
    snapshot_id: UUID
    source_record_id: str
    source_url: str = ""
    evidence_type: str = ""
    rationale: str = ""


class ConditionClaimView(BaseModel):
    model_config = ConfigDict(frozen=True)

    claim_id: UUID
    predicate: PredicateLiteral
    subject_curie: str
    object_curie: str
    subject_label: str
    object_label: str
    qualifiers: dict[str, object] = Field(default_factory=dict)
    supporting_evidence: list[ClaimEvidenceView] = Field(default_factory=list)
    contradictory_evidence: list[ClaimEvidenceView] = Field(default_factory=list)


class ImportReportView(BaseModel):
    model_config = ConfigDict(frozen=True)

    resource_name: str
    snapshot_id: UUID
    version: str
    checksum: str
    counts: dict[str, int] = Field(default_factory=dict)
    warnings: list[str] = Field(default_factory=list)
    fingerprint: str = ""
    disclaimer: ResearchDisclaimer = Field(default_factory=ResearchDisclaimer)


class PagedResponse(BaseModel, Generic[T]):
    model_config = ConfigDict(frozen=True)

    items: list[T]
    total: int
    limit: int
    offset: int
    disclaimer: ResearchDisclaimer = Field(default_factory=ResearchDisclaimer)


ComparisonStatusLiteral = Literal["comparable", "insufficient_data"]


class ComparisonWeights(BaseModel):
    model_config = ConfigDict(frozen=True)

    phenotype: float = 0.55
    gene: float = 0.20
    pathway: float = 0.15
    intervention: float = 0.10
    biomarker: float = 0.0


class ComparisonRequest(BaseModel):
    model_config = ConfigDict(frozen=True)

    left_curie: str = Field(min_length=1)
    right_curie: str = Field(min_length=1)
    weights: ComparisonWeights | None = None


class ComparisonComponentsView(BaseModel):
    model_config = ConfigDict(frozen=True)

    phenotype: float | None = None
    gene: float | None = None
    pathway: float | None = None
    intervention: float | None = None
    biomarker: float | None = None
    negative_phenotype: float | None = None


class DimensionCoverageView(BaseModel):
    model_config = ConfigDict(frozen=True)

    present: bool
    count: int = 0
    snapshot_ids: list[UUID] = Field(default_factory=list)


class ComparisonCoverageView(BaseModel):
    model_config = ConfigDict(frozen=True)

    left: dict[str, DimensionCoverageView] = Field(default_factory=dict)
    right: dict[str, DimensionCoverageView] = Field(default_factory=dict)
    comparable_dimensions: list[str] = Field(default_factory=list)
    missing_dimensions: list[str] = Field(default_factory=list)


class ComparisonResultView(BaseModel):
    model_config = ConfigDict(frozen=True)

    run_id: UUID
    status: ComparisonStatusLiteral
    left_curie: str
    right_curie: str
    overall_score: float | None = None
    components: ComparisonComponentsView = Field(default_factory=ComparisonComponentsView)
    effective_weights: dict[str, float] = Field(default_factory=dict)
    shared_entities: dict[str, list[str]] = Field(default_factory=dict)
    distinguishing_entities: dict[str, dict[str, list[str]]] = Field(default_factory=dict)
    coverage: ComparisonCoverageView = Field(default_factory=ComparisonCoverageView)
    snapshot_ids: list[UUID] = Field(default_factory=list)
    claim_set_fingerprint: str = ""
    algorithm_id: str = "condition-similarity"
    algorithm_version: str = "1.0.0"
    disclaimer: ResearchDisclaimer = Field(default_factory=ResearchDisclaimer)

