"""Domain models for evidence-aware NosoGraph condition comparison."""

from __future__ import annotations

from enum import Enum
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

CompareStatus = Literal["comparable", "insufficient_data"]

DEFAULT_DIMENSIONS = ("phenotype", "gene", "pathway", "treatment", "evidence_coverage")
LEGACY_DEFAULT_DIMENSIONS = (
    "phenotype",
    "gene",
    "mechanism",
    "treatment",
    "evidence_coverage",
)


class EntityState(str, Enum):
    PRESENT = "PRESENT"
    KNOWN_ABSENT = "KNOWN_ABSENT"
    NOT_RECORDED = "NOT_RECORDED"


class CompareWarning(BaseModel):
    model_config = ConfigDict(frozen=True)

    code: Literal["MISSING_CURATION", "ASYMMETRIC_CURATION", "CONFLICTING_ASSERTIONS"]
    dimension: str
    condition_curies: list[str] = Field(default_factory=list)
    counts: dict[str, int] = Field(default_factory=dict)
    message: str
    entity_curie: str | None = None


class ConditionCoverage(BaseModel):
    model_config = ConfigDict(frozen=True)

    positive_claim_count: int = 0
    negated_claim_count: int = 0
    claim_count: int = 0
    evidence_count: int = 0
    source_count: int = 0
    snapshot_count: int = 0
    snapshot_ids: list[UUID] = Field(default_factory=list)
    source_names: list[str] = Field(default_factory=list)


class SubsetMembership(BaseModel):
    model_config = ConfigDict(frozen=True)

    entity_curie: str
    condition_curies: list[str] = Field(default_factory=list)


class EntityStateRow(BaseModel):
    model_config = ConfigDict(frozen=True)

    entity_curie: str
    states: dict[str, EntityState] = Field(default_factory=dict)


class DimensionComparison(BaseModel):
    model_config = ConfigDict(frozen=True)

    dimension: str
    shared_by_all: list[str] = Field(default_factory=list)
    shared_by_subset: list[SubsetMembership] = Field(default_factory=list)
    unique_by_condition: dict[str, list[str]] = Field(default_factory=dict)
    entities: list[EntityStateRow] = Field(default_factory=list)
    coverage_by_condition: dict[str, ConditionCoverage] = Field(default_factory=dict)
    warnings: list[CompareWarning] = Field(default_factory=list)


class CompareV2Result(BaseModel):
    model_config = ConfigDict(frozen=True)

    run_id: UUID
    status: CompareStatus
    condition_curies: list[str] = Field(default_factory=list)
    dimensions: list[str] = Field(default_factory=list)
    dimension_results: list[DimensionComparison] = Field(default_factory=list)
    curation_warnings: list[CompareWarning] = Field(default_factory=list)
    snapshot_ids: list[UUID] = Field(default_factory=list)
    claim_set_fingerprint: str = ""
    algorithm_id: str = "nosograph-compare-v2"
    algorithm_version: str = "2.0.0"
    disclaimer: str = ""


class MissingDataReason(str, Enum):
    KNOWN_ABSENT = "KNOWN_ABSENT"
    NOT_RECORDED = "NOT_RECORDED"
    UNKNOWN = "UNKNOWN"
    NOT_APPLICABLE = "NOT_APPLICABLE"


class DimensionMissingData(BaseModel):
    model_config = ConfigDict(frozen=True)

    left: MissingDataReason = MissingDataReason.UNKNOWN
    right: MissingDataReason = MissingDataReason.UNKNOWN


class DimensionOverlap(BaseModel):
    model_config = ConfigDict(frozen=True)

    dimension: str
    shared: list[str] = Field(default_factory=list)
    unique_to_left: list[str] = Field(default_factory=list)
    unique_to_right: list[str] = Field(default_factory=list)
    missing_data: DimensionMissingData = Field(default_factory=DimensionMissingData)
    left_evidence_count: int = 0
    right_evidence_count: int = 0
    warnings: list[str] = Field(default_factory=list)


class CompareResult(BaseModel):
    model_config = ConfigDict(frozen=True)

    run_id: UUID
    status: CompareStatus
    left_curie: str
    right_curie: str
    dimensions: list[str] = Field(default_factory=list)
    overlaps: list[DimensionOverlap] = Field(default_factory=list)
    curation_warnings: list[str] = Field(default_factory=list)
    snapshot_ids: list[UUID] = Field(default_factory=list)
    claim_set_fingerprint: str = ""
    algorithm_id: str = "nosograph-compare"
    algorithm_version: str = "1.0.0"
    disclaimer: str = ""
