"""Domain models for evidence-aware NosoGraph condition comparison."""

from __future__ import annotations

from enum import Enum
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

CompareStatus = Literal["comparable", "insufficient_data"]

DEFAULT_DIMENSIONS = ("phenotype", "gene", "mechanism", "treatment", "evidence_coverage")


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
