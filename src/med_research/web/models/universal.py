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
    "anatomy",
    "cell_type",
    "variant",
]

PredicateLiteral = Literal[
    "IS_A",
    "PART_OF",
    "REGULATES",
    "LOCATED_IN",
    "EXPRESSED_IN",
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


class AnalyticsStatsView(BaseModel):
    model_config = ConfigDict(frozen=True)

    total_entities: int
    total_claims: int
    total_evidence: int
    total_snapshots: int
    entity_type_distribution: dict[str, int] = Field(default_factory=dict)
    predicate_distribution: dict[str, int] = Field(default_factory=dict)
    disclaimer: ResearchDisclaimer = Field(default_factory=ResearchDisclaimer)


class AnalyticsTargetView(BaseModel):
    model_config = ConfigDict(frozen=True)

    target_curie: str
    target_name: str
    target_type: str
    supporting_count: int
    contradictory_count: int
    evidence_score: float
    pathway_count: int
    phenotype_count: int


class AnalyticsSharedMechanismView(BaseModel):
    model_config = ConfigDict(frozen=True)

    condition_a: str
    condition_b: str
    shared_pathways: list[str]
    shared_genes: list[str]
    jaccard_similarity: float
    disclaimer: ResearchDisclaimer = Field(default_factory=ResearchDisclaimer)


class AnalyticsSubgraphEdgeView(BaseModel):
    model_config = ConfigDict(frozen=True)

    source: str
    predicate: str
    target: str
    evidence_count: int


class AnalyticsSubgraphView(BaseModel):
    model_config = ConfigDict(frozen=True)

    root_curie: str
    edges: list[AnalyticsSubgraphEdgeView]
    edge_count: int
    disclaimer: ResearchDisclaimer = Field(default_factory=ResearchDisclaimer)


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


EvidenceSummaryLiteral = Literal["SUPPORTS", "CONTRADICTS", "INCONCLUSIVE", "UNASSERTED"]
EvidenceSortLiteral = Literal["newest", "oldest", "source"]


class EvidenceQualityView(BaseModel):
    model_config = ConfigDict(frozen=True)

    species_context: str = "unknown"
    study_design: str = "unknown"
    sample_size: int | None = None
    sample_size_context: str = "unknown"
    replication: str = "unknown"
    effect_direction: str = "unknown"
    statistical_quality: str = "unknown"
    directness: str = "unknown"
    source_quality: str = "unknown"
    recency: str = ""
    human_review: str = "unknown"
    contradiction_burden: str = "unknown"
    origin_class: str = "UNKNOWN_ORIGIN_CLASS"
    limitations: list[str] = Field(default_factory=list)


class ClaimProvenanceStepView(BaseModel):
    model_config = ConfigDict(frozen=True)

    stage: str
    resource_name: str = ""
    snapshot_id: UUID | None = None
    snapshot_version: str = ""
    checksum: str = ""
    source_record_id: str = ""
    source_url: str = ""
    importer: str = ""
    retrieved_at: datetime | None = None


class ClaimEvidenceDetailView(BaseModel):
    model_config = ConfigDict(frozen=True)

    id: UUID
    direction: EvidenceDirectionLiteral
    summary: EvidenceSummaryLiteral
    snapshot_id: UUID
    source_record_id: str
    source_url: str = ""
    source_name: str = ""
    evidence_type: str = ""
    population: str = ""
    confidence: float | None = None
    confidence_explanation: str = ""
    rationale: str = ""
    curator: str = ""
    extraction_method: str = ""
    publication_date: str = ""
    limitations: list[str] = Field(default_factory=list)
    quality: EvidenceQualityView = Field(default_factory=EvidenceQualityView)
    provenance: list[ClaimProvenanceStepView] = Field(default_factory=list)


class RelatedClaimView(BaseModel):
    model_config = ConfigDict(frozen=True)

    claim_id: UUID
    predicate: PredicateLiteral
    subject_curie: str
    object_curie: str
    subject_label: str
    object_label: str
    relation: str
    evidence_summary: EvidenceSummaryLiteral


class ClaimDetailView(BaseModel):
    model_config = ConfigDict(frozen=True)

    claim_id: UUID
    predicate: PredicateLiteral
    subject_curie: str
    object_curie: str
    subject_label: str
    object_label: str
    qualifiers: dict[str, object] = Field(default_factory=dict)
    evidence_summary: EvidenceSummaryLiteral
    supporting_count: int = 0
    contradictory_count: int = 0
    inconclusive_count: int = 0
    source_count: int = 0
    supporting_evidence: list[ClaimEvidenceDetailView] = Field(default_factory=list)
    contradictory_evidence: list[ClaimEvidenceDetailView] = Field(default_factory=list)
    provenance: list[ClaimProvenanceStepView] = Field(default_factory=list)
    disclaimer: ResearchDisclaimer = Field(default_factory=ResearchDisclaimer)


class NosoGraphCompareRequest(BaseModel):
    model_config = ConfigDict(frozen=True)

    left_curie: str = Field(min_length=1)
    right_curie: str = Field(min_length=1)
    dimensions: list[str] = Field(
        default_factory=lambda: ["phenotype", "gene", "mechanism", "treatment", "evidence_coverage"]
    )


class NosoGraphCompareV2Request(BaseModel):
    model_config = ConfigDict(frozen=True)

    condition_curies: list[str]
    dimensions: list[str] | None = None


class CompareWarningView(BaseModel):
    model_config = ConfigDict(frozen=True)

    code: str
    dimension: str
    condition_curies: list[str] = Field(default_factory=list)
    counts: dict[str, int] = Field(default_factory=dict)
    message: str
    entity_curie: str | None = None


class ConditionCoverageView(BaseModel):
    model_config = ConfigDict(frozen=True)

    positive_claim_count: int = 0
    negated_claim_count: int = 0
    claim_count: int = 0
    evidence_count: int = 0
    source_count: int = 0
    snapshot_count: int = 0
    snapshot_ids: list[UUID] = Field(default_factory=list)
    source_names: list[str] = Field(default_factory=list)


class SubsetMembershipView(BaseModel):
    model_config = ConfigDict(frozen=True)

    entity_curie: str
    condition_curies: list[str] = Field(default_factory=list)


class EntityStateRowView(BaseModel):
    model_config = ConfigDict(frozen=True)

    entity_curie: str
    entity_label: str = ""
    states: dict[str, str] = Field(default_factory=dict)
    claim_ids_by_condition: dict[str, list[UUID]] = Field(default_factory=dict)


class DimensionComparisonView(BaseModel):
    model_config = ConfigDict(frozen=True)

    dimension: str
    shared_by_all: list[str] = Field(default_factory=list)
    shared_by_subset: list[SubsetMembershipView] = Field(default_factory=list)
    unique_by_condition: dict[str, list[str]] = Field(default_factory=dict)
    entities: list[EntityStateRowView] = Field(default_factory=list)
    coverage_by_condition: dict[str, ConditionCoverageView] = Field(default_factory=dict)
    warnings: list[CompareWarningView] = Field(default_factory=list)


class NosoGraphCompareV2ResultView(BaseModel):
    model_config = ConfigDict(frozen=True)

    run_id: UUID
    result_schema_version: str
    status: ComparisonStatusLiteral
    condition_curies: list[str] = Field(default_factory=list)
    condition_labels: dict[str, str] = Field(default_factory=dict)
    dimensions: list[str] = Field(default_factory=list)
    dimension_results: list[DimensionComparisonView] = Field(default_factory=list)
    curation_warnings: list[CompareWarningView] = Field(default_factory=list)
    snapshot_ids: list[UUID] = Field(default_factory=list)
    claim_set_fingerprint: str = ""
    algorithm_id: str = "nosograph-compare-v2"
    algorithm_version: str = "2.0.0"
    disclaimer: ResearchDisclaimer = Field(default_factory=ResearchDisclaimer)


class DimensionMissingDataView(BaseModel):
    model_config = ConfigDict(frozen=True)

    left: str
    right: str


class DimensionOverlapView(BaseModel):
    model_config = ConfigDict(frozen=True)

    dimension: str
    shared: list[str] = Field(default_factory=list)
    unique_to_left: list[str] = Field(default_factory=list)
    unique_to_right: list[str] = Field(default_factory=list)
    missing_data: DimensionMissingDataView
    left_evidence_count: int = 0
    right_evidence_count: int = 0
    warnings: list[str] = Field(default_factory=list)


class NosoGraphCompareResultView(BaseModel):
    model_config = ConfigDict(frozen=True)

    run_id: UUID
    status: ComparisonStatusLiteral
    left_curie: str
    right_curie: str
    dimensions: list[str] = Field(default_factory=list)
    overlaps: list[DimensionOverlapView] = Field(default_factory=list)
    curation_warnings: list[str] = Field(default_factory=list)
    snapshot_ids: list[UUID] = Field(default_factory=list)
    claim_set_fingerprint: str = ""
    algorithm_id: str = "nosograph-compare"
    algorithm_version: str = "1.0.0"
    disclaimer: ResearchDisclaimer = Field(default_factory=ResearchDisclaimer)
