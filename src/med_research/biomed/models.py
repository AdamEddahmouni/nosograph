from datetime import datetime, timezone
from enum import Enum
from typing import Any, Generic, TypeVar
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

T = TypeVar("T")


class EntityType(str, Enum):
    CONDITION = "condition"
    PHENOTYPE = "phenotype"
    GENE = "gene"
    PATHWAY = "pathway"
    INTERVENTION = "intervention"
    BIOMARKER = "biomarker"
    MEASUREMENT = "measurement"
    EXPOSURE = "exposure"
    OUTCOME = "outcome"


class MappingKind(str, Enum):
    EXACT = "exact"
    CLOSE = "close"
    BROAD = "broad"
    NARROW = "narrow"

    @property
    def can_auto_join(self) -> bool:
        return self == MappingKind.EXACT


class Predicate(str, Enum):
    IS_A = "IS_A"
    HAS_PHENOTYPE = "HAS_PHENOTYPE"
    ASSOCIATED_WITH_GENE = "ASSOCIATED_WITH_GENE"
    INVOLVES_PATHWAY = "INVOLVES_PATHWAY"
    TREATED_BY = "TREATED_BY"
    HAS_BIOMARKER = "HAS_BIOMARKER"
    HAS_MEASUREMENT = "HAS_MEASUREMENT"
    ASSOCIATED_WITH_EXPOSURE = "ASSOCIATED_WITH_EXPOSURE"
    HAS_OUTCOME = "HAS_OUTCOME"


class EvidenceDirection(str, Enum):
    SUPPORTING = "supporting"
    CONTRADICTORY = "contradictory"


class RunStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


class ResourcePolicy(BaseModel):
    model_config = ConfigDict(frozen=True)

    resource_name: str = ""
    allowed_licenses: list[str] = Field(
        default_factory=lambda: ["CC0-1.0", "CC-BY-4.0", "MIT", "Apache-2.0", "Public Domain"]
    )
    require_checksum: bool = True
    redistribution_policy: str = "permitted"
    license_id: str = "CC0-1.0"
    license_url: str = ""


class ResourceSnapshot(BaseModel):
    model_config = ConfigDict(frozen=True)

    id: UUID
    resource_name: str
    version: str
    checksum: str
    name: str | None = None
    namespace_prefix: str | None = None
    source_url: str = ""
    source_uri: str = ""
    artifact_format: str = ""
    upstream_version: str | None = None
    version_iri: str | None = None
    artifact_size: int = 0
    license_id: str = "CC0-1.0"
    license_spdx: str = "CC0-1.0"
    license_url: str = ""
    attribution: str = ""
    redistribution_policy: str = "permitted"
    retrieved_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    downloaded_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    imported_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    importer_name: str = ""
    importer_version: str = ""
    counts: dict[str, int] = Field(default_factory=dict)
    warnings: list[str] = Field(default_factory=list)
    manifest_fingerprint: str = ""
    is_active: bool = True


class Entity(BaseModel):
    model_config = ConfigDict(frozen=True)

    id: UUID
    primary_curie: str
    entity_type: EntityType
    canonical_name: str | None = None
    created_in_snapshot_id: UUID | None = None


class EntityRevision(BaseModel):
    model_config = ConfigDict(frozen=True)

    id: UUID
    entity_id: UUID
    snapshot_id: UUID
    label: str | None = None
    definition: str = ""
    description: str | None = None
    synonyms: list[str] = Field(default_factory=list)
    alt_labels: list[str] = Field(default_factory=list)
    obsolete: bool = False
    replaced_by: str | None = None
    consider: list[str] = Field(default_factory=list)
    source_record_id: str = ""
    audit: dict[str, Any] = Field(default_factory=dict)
    attributes: dict[str, Any] = Field(default_factory=dict)
    revised_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class EntityMapping(BaseModel):
    model_config = ConfigDict(frozen=True)

    id: UUID
    subject_curie: str = ""
    object_curie: str = ""
    relation: MappingKind = MappingKind.EXACT
    snapshot_id: UUID
    source_record_id: str | None = None
    notes: str = ""
    subject_entity_id: UUID | None = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    @property
    def mapping_kind(self) -> MappingKind:
        return self.relation


class Claim(BaseModel):
    model_config = ConfigDict(frozen=True)

    id: UUID
    subject_curie: str
    predicate: Predicate
    object_curie: str
    qualifiers: dict[str, Any] = Field(default_factory=dict)
    supersedes_claim_id: UUID | None = None
    subject_entity_id: UUID | None = None
    object_entity_id: UUID | None = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class ClaimEvidence(BaseModel):
    model_config = ConfigDict(frozen=True)

    id: UUID
    claim_id: UUID
    snapshot_id: UUID
    direction: EvidenceDirection
    source_record_id: str
    citation_ids: list[str] = Field(default_factory=list)
    source_url: str | None = None
    publication_date: str | None = None
    evidence_type: str | None = None
    population: str | None = None
    sample_size: int | None = None
    source_evidence_code: str | None = None
    strength_label: str | None = None
    confidence: float | None = None
    confidence_score: float | None = None
    rationale: str | None = None
    curator: str | None = None
    extraction_method: str | None = None
    importer_version: str | None = None
    extracted_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    limitations: list[str] = Field(default_factory=list)
    audit: dict[str, Any] = Field(default_factory=dict)
    snippet: str | None = None
    attributes: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class ResearchRunCreate(BaseModel):
    model_config = ConfigDict(frozen=True)

    name: str = "run"
    run_type: str = "research"
    algorithm_id: str = ""
    algorithm_version: str = ""
    software_version: str = ""
    parameters: dict[str, Any] = Field(default_factory=dict)
    snapshot_ids: list[UUID] = Field(default_factory=list)
    claim_ids: list[UUID] = Field(default_factory=list)
    input_query: str | None = None
    parent_run_id: UUID | None = None


class ResearchRun(BaseModel):
    model_config = ConfigDict(frozen=True)

    id: UUID
    name: str = "run"
    fingerprint: str
    status: RunStatus = RunStatus.PENDING
    run_type: str = "research"
    algorithm_id: str = ""
    algorithm_version: str = ""
    software_version: str = ""
    parameters: dict[str, Any] = Field(default_factory=dict)
    result: dict[str, Any] | None = None
    warnings: list[str] = Field(default_factory=list)
    snapshot_ids: list[UUID] = Field(default_factory=list)
    claim_ids: list[UUID] = Field(default_factory=list)
    input_query: str | None = None
    parent_run_id: UUID | None = None
    started_at: datetime | None = None
    finished_at: datetime | None = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class Page(BaseModel, Generic[T]):
    model_config = ConfigDict(frozen=True)

    items: list[T]
    total: int
    limit: int
    offset: int
