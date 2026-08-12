"""Persisted condition comparison orchestration."""

from __future__ import annotations

from collections.abc import Sequence

from med_research.biomed.comparison.algorithm import compare_fingerprints
from med_research.biomed.comparison.fingerprint import build_fingerprint
from med_research.biomed.comparison.hpo import build_hpo_context
from med_research.biomed.comparison.models import (
    ComparisonComponents,
    ComparisonCoverage,
    ComparisonResult,
    DimensionCoverage,
    SimilarityConfig,
)
from med_research.biomed.identifiers import fingerprint_json, normalize_curie
from med_research.biomed.models import ResearchRun, ResearchRunCreate, RunStatus
from med_research.biomed.repository import BiomedicalRepository

_SOFTWARE_VERSION = "2.0.0"
_RUN_TYPE = "condition_comparison"
_DISCLAIMER = (
    "For research and exploratory analysis only. Results summarize supporting evidence "
    "and contradictory evidence from imported biomedical sources. Not for clinical "
    "decision-making, treatment recommendations, or probability-of-disease claims."
)


class ConditionComparisonService:
    def __init__(self, repository: BiomedicalRepository) -> None:
        self._repository = repository

    def compare(
        self,
        left_curie: str,
        right_curie: str,
        config: SimilarityConfig,
    ) -> ComparisonResult:
        left = normalize_curie(left_curie)
        right = normalize_curie(right_curie)
        left_fp = build_fingerprint(self._repository, left)
        right_fp = build_fingerprint(self._repository, right)
        hpo_context = build_hpo_context(self._repository)
        result = compare_fingerprints(left_fp, right_fp, config, hpo_context)

        snapshot_ids = sorted(
            {snapshot.id for snapshot in self._repository.list_active_snapshots()},
            key=str,
        )
        claim_ids = sorted({*left_fp.claim_ids, *right_fp.claim_ids}, key=str)
        claim_set_fingerprint = fingerprint_json(
            {
                "left": left_fp.claim_set_fingerprint,
                "right": right_fp.claim_set_fingerprint,
            }
        )
        parameters = {
            "left_curie": left,
            "right_curie": right,
            "weights": config.base_weights(),
            "claim_set_fingerprint": claim_set_fingerprint,
        }
        spec = ResearchRunCreate(
            run_type=_RUN_TYPE,
            algorithm_id=config.algorithm_id,
            algorithm_version=config.algorithm_version,
            software_version=_SOFTWARE_VERSION,
            parameters=parameters,
            snapshot_ids=snapshot_ids,
            claim_ids=claim_ids,
            input_query=f"{left}|{right}",
        )
        run = self._repository.create_research_run(spec)
        if run.status is RunStatus.COMPLETED and run.result is not None:
            return _result_from_run(run)

        if run.status is RunStatus.PENDING:
            self._repository.transition_research_run(run.id, RunStatus.RUNNING)
            payload = _result_payload(result, claim_set_fingerprint, snapshot_ids)
            run = self._repository.transition_research_run(
                run.id,
                RunStatus.COMPLETED,
                result=payload,
            )

        return _result_from_run(run)


def _result_payload(
    result: ComparisonResult,
    claim_set_fingerprint: str,
    snapshot_ids: Sequence[object],
) -> dict[str, object]:
    def _dimension_payload(dimension: object) -> dict[str, object]:
        from med_research.biomed.comparison.models import DimensionCoverage

        assert isinstance(dimension, DimensionCoverage)
        return {
            "present": dimension.present,
            "count": dimension.count,
            "snapshot_ids": [str(item) for item in dimension.snapshot_ids],
        }

    coverage = {
        "left": {key: _dimension_payload(value) for key, value in result.coverage.left.items()},
        "right": {key: _dimension_payload(value) for key, value in result.coverage.right.items()},
        "comparable_dimensions": result.coverage.comparable_dimensions,
        "missing_dimensions": result.coverage.missing_dimensions,
    }
    return {
        "status": result.status,
        "left_curie": result.left_curie,
        "right_curie": result.right_curie,
        "overall_score": result.overall_score,
        "components": result.components.model_dump(),
        "effective_weights": result.effective_weights,
        "shared_entities": result.shared_entities,
        "distinguishing_entities": result.distinguishing_entities,
        "coverage": coverage,
        "claim_set_fingerprint": claim_set_fingerprint,
        "snapshot_ids": [str(item) for item in snapshot_ids],
        "algorithm_id": result.algorithm_id,
        "algorithm_version": result.algorithm_version,
        "disclaimer": _DISCLAIMER,
    }


def _result_from_run(run: ResearchRun) -> ComparisonResult:
    payload = run.result or {}
    coverage_payload = payload.get("coverage", {})
    left_coverage = {
        key: DimensionCoverage.model_validate(value)
        for key, value in dict(coverage_payload.get("left", {})).items()
    }
    right_coverage = {
        key: DimensionCoverage.model_validate(value)
        for key, value in dict(coverage_payload.get("right", {})).items()
    }
    return ComparisonResult(
        run_id=run.id,
        status=payload.get("status", "insufficient_data"),
        left_curie=str(payload.get("left_curie", "")),
        right_curie=str(payload.get("right_curie", "")),
        overall_score=payload.get("overall_score"),
        components=ComparisonComponents.model_validate(payload.get("components", {})),
        effective_weights=dict(payload.get("effective_weights", {})),
        shared_entities=dict(payload.get("shared_entities", {})),
        distinguishing_entities=dict(payload.get("distinguishing_entities", {})),
        coverage=ComparisonCoverage(
            left=left_coverage,
            right=right_coverage,
            comparable_dimensions=list(coverage_payload.get("comparable_dimensions", [])),
            missing_dimensions=list(coverage_payload.get("missing_dimensions", [])),
        ),
        snapshot_ids=run.snapshot_ids,
        claim_set_fingerprint=str(payload.get("claim_set_fingerprint", run.fingerprint)),
        algorithm_id=str(payload.get("algorithm_id", run.algorithm_id)),
        algorithm_version=str(payload.get("algorithm_version", run.algorithm_version)),
        disclaimer=str(payload.get("disclaimer", _DISCLAIMER)),
    )
