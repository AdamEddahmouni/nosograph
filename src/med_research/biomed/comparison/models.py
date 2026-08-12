"""Domain models for condition fingerprinting and similarity."""

from __future__ import annotations

from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator

ComparisonStatus = Literal["comparable", "insufficient_data"]

_DIMENSIONS = ("phenotype", "gene", "pathway", "intervention", "biomarker")


class DimensionCoverage(BaseModel):
    model_config = ConfigDict(frozen=True)

    present: bool
    count: int = 0
    snapshot_ids: list[UUID] = Field(default_factory=list)


class ConditionFingerprint(BaseModel):
    model_config = ConfigDict(frozen=True)

    condition_curie: str
    positive_phenotypes: list[str] = Field(default_factory=list)
    negative_phenotypes: list[str] = Field(default_factory=list)
    genes: list[str] = Field(default_factory=list)
    pathways: list[str] = Field(default_factory=list)
    interventions: list[str] = Field(default_factory=list)
    biomarkers: list[str] = Field(default_factory=list)
    coverage: dict[str, DimensionCoverage] = Field(default_factory=dict)
    claim_ids: list[UUID] = Field(default_factory=list)
    claim_set_fingerprint: str = ""


class SimilarityConfig(BaseModel):
    model_config = ConfigDict(frozen=True)

    algorithm_id: str = "condition-similarity"
    algorithm_version: str = "1.0.0"
    phenotype_weight: float = 0.55
    gene_weight: float = 0.20
    pathway_weight: float = 0.15
    intervention_weight: float = 0.10
    biomarker_weight: float = 0.0

    @model_validator(mode="after")
    def _validate_weights(self) -> SimilarityConfig:
        total = (
            self.phenotype_weight
            + self.gene_weight
            + self.pathway_weight
            + self.intervention_weight
            + self.biomarker_weight
        )
        if abs(total - 1.0) > 1e-6:
            msg = f"Similarity weights must sum to 1.0, got {total}"
            raise ValueError(msg)
        return self

    @classmethod
    def v1_default(cls) -> SimilarityConfig:
        return cls()

    def base_weights(self) -> dict[str, float]:
        return {
            "phenotype": self.phenotype_weight,
            "gene": self.gene_weight,
            "pathway": self.pathway_weight,
            "intervention": self.intervention_weight,
            "biomarker": self.biomarker_weight,
        }


class ComparisonComponents(BaseModel):
    model_config = ConfigDict(frozen=True)

    phenotype: float | None = None
    gene: float | None = None
    pathway: float | None = None
    intervention: float | None = None
    biomarker: float | None = None
    negative_phenotype: float | None = None


class ComparisonCoverage(BaseModel):
    model_config = ConfigDict(frozen=True)

    left: dict[str, DimensionCoverage] = Field(default_factory=dict)
    right: dict[str, DimensionCoverage] = Field(default_factory=dict)
    comparable_dimensions: list[str] = Field(default_factory=list)
    missing_dimensions: list[str] = Field(default_factory=list)


class ComparisonResult(BaseModel):
    model_config = ConfigDict(frozen=True)

    run_id: UUID
    status: ComparisonStatus
    left_curie: str
    right_curie: str
    overall_score: float | None = None
    components: ComparisonComponents = Field(default_factory=ComparisonComponents)
    effective_weights: dict[str, float] = Field(default_factory=dict)
    shared_entities: dict[str, list[str]] = Field(default_factory=dict)
    distinguishing_entities: dict[str, dict[str, list[str]]] = Field(default_factory=dict)
    coverage: ComparisonCoverage = Field(default_factory=ComparisonCoverage)
    snapshot_ids: list[UUID] = Field(default_factory=list)
    claim_set_fingerprint: str = ""
    algorithm_id: str = "condition-similarity"
    algorithm_version: str = "1.0.0"
    disclaimer: str = ""
