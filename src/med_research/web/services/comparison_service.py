"""View helpers for condition comparison API responses."""

from __future__ import annotations

from uuid import UUID

from med_research.biomed.comparison.models import ComparisonResult, SimilarityConfig
from med_research.biomed.comparison.service import _result_from_run
from med_research.biomed.models import RunStatus
from med_research.biomed.repository import BiomedicalRepository
from med_research.web.models.universal import (
    ComparisonComponentsView,
    ComparisonCoverageView,
    ComparisonResultView,
    ComparisonWeights,
    DimensionCoverageView,
    ResearchDisclaimer,
)

_DISCLAIMER = ResearchDisclaimer()


def build_similarity_config(weights: ComparisonWeights | None) -> SimilarityConfig:
    if weights is None:
        return SimilarityConfig.v1_default()
    return SimilarityConfig(
        phenotype_weight=weights.phenotype,
        gene_weight=weights.gene,
        pathway_weight=weights.pathway,
        intervention_weight=weights.intervention,
        biomarker_weight=weights.biomarker,
    )


def to_comparison_view(result: ComparisonResult) -> ComparisonResultView:
    return ComparisonResultView(
        run_id=result.run_id,
        status=result.status,
        left_curie=result.left_curie,
        right_curie=result.right_curie,
        overall_score=result.overall_score,
        components=ComparisonComponentsView.model_validate(result.components.model_dump()),
        effective_weights=result.effective_weights,
        shared_entities=result.shared_entities,
        distinguishing_entities=result.distinguishing_entities,
        coverage=ComparisonCoverageView(
            left={
                key: DimensionCoverageView.model_validate(value.model_dump())
                for key, value in result.coverage.left.items()
            },
            right={
                key: DimensionCoverageView.model_validate(value.model_dump())
                for key, value in result.coverage.right.items()
            },
            comparable_dimensions=result.coverage.comparable_dimensions,
            missing_dimensions=result.coverage.missing_dimensions,
        ),
        snapshot_ids=result.snapshot_ids,
        claim_set_fingerprint=result.claim_set_fingerprint,
        algorithm_id=result.algorithm_id,
        algorithm_version=result.algorithm_version,
        disclaimer=_DISCLAIMER,
    )


def get_comparison_run(
    repository: BiomedicalRepository, run_id: UUID
) -> ComparisonResultView | None:
    run = repository.get_research_run(run_id)
    if run is None or run.run_type != "condition_comparison":
        return None
    if run.status is not RunStatus.COMPLETED or run.result is None:
        return None
    return to_comparison_view(_result_from_run(run))
