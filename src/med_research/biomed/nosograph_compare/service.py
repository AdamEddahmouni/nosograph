"""Evidence-aware deterministic N-way condition comparison."""

from __future__ import annotations

from uuid import UUID

from med_research import __version__ as software_version
from med_research.biomed.errors import RunTransitionError
from med_research.biomed.identifiers import fingerprint_json, normalize_curie
from med_research.biomed.models import EntityType, ResearchRun, ResearchRunCreate, RunStatus
from med_research.biomed.nosograph_compare.engine import (
    build_cohort_context,
    compare_dimension,
    dimension_has_comparable_data,
)
from med_research.biomed.nosograph_compare.models import (
    COMPARE_RESULT_SCHEMA_VERSION,
    DEFAULT_DIMENSIONS,
    LEGACY_DEFAULT_DIMENSIONS,
    CompareResult,
    CompareV2Result,
    ConditionCoverage,
    DimensionComparison,
    DimensionMissingData,
    DimensionOverlap,
    MissingDataReason,
)
from med_research.biomed.repository import BiomedicalRepository

_DISCLAIMER = (
    "For research and exploratory analysis only. Dimension overlaps summarize imported "
    "biomedical claims and evidence coverage. No universal similarity score is emitted. "
    "Not for clinical decision-making."
)
_ALGORITHM_ID = "nosograph-compare-v2"
_ALGORITHM_VERSION = "2.0.0"
_RUN_TYPE = "nosograph_compare_v2"
_LEGACY_ALIASES = {"mechanism": "pathway"}


class CompareRunNotFoundError(LookupError):
    """Raised when a persisted run is not a Compare V2 run."""


class CompareRunIncompleteError(RuntimeError):
    """Raised when a persisted Compare V2 run has no completed result."""


class NosoGraphCompareService:
    def __init__(self, repository: BiomedicalRepository) -> None:
        self._repository = repository

    def compare_many(
        self,
        condition_curies: list[str],
        *,
        dimensions: list[str] | None = None,
    ) -> CompareV2Result:
        normalized = sorted({normalize_curie(item) for item in condition_curies})
        if not 2 <= len(normalized) <= 5:
            raise ValueError("Comparison requires 2 to 5 unique conditions")
        conditions = sorted({self._resolve_condition(item) for item in normalized})
        if len(conditions) < 2:
            raise ValueError("Comparison requires 2 to 5 unique conditions")
        selected = _canonical_dimensions(dimensions)
        context = build_cohort_context(self._repository, conditions)
        dimension_results = [compare_dimension(context, item) for item in selected]
        warnings = sorted(
            [warning for item in dimension_results for warning in item.warnings],
            key=lambda item: (
                item.dimension,
                item.code,
                item.entity_curie or "",
                tuple(item.condition_curies),
            ),
        )
        status = (
            "comparable"
            if any(dimension_has_comparable_data(item) for item in dimension_results)
            else "insufficient_data"
        )
        claim_set_fingerprint = fingerprint_json(
            {
                "algorithm_version": _ALGORITHM_VERSION,
                "result_schema_version": COMPARE_RESULT_SCHEMA_VERSION,
                "conditions": [
                    {
                        "curie": curie,
                        "fingerprint": context.fingerprints[curie].fingerprint,
                    }
                    for curie in conditions
                ],
                "dimensions": selected,
                "snapshot_ids": [str(item) for item in context.snapshot_ids],
            }
        )
        spec = ResearchRunCreate(
            run_type=_RUN_TYPE,
            algorithm_id=_ALGORITHM_ID,
            algorithm_version=_ALGORITHM_VERSION,
            software_version=software_version,
            parameters={
                "condition_curies": conditions,
                "dimensions": selected,
                "result_schema_version": COMPARE_RESULT_SCHEMA_VERSION,
                "condition_fingerprints": {
                    curie: context.fingerprints[curie].fingerprint for curie in conditions
                },
                "claim_set_fingerprint": claim_set_fingerprint,
            },
            snapshot_ids=list(context.snapshot_ids),
            claim_ids=context.claim_ids,
            input_query=f"{'|'.join(conditions)}::{','.join(selected)}",
        )
        payload = {
            "result_schema_version": COMPARE_RESULT_SCHEMA_VERSION,
            "status": status,
            "condition_curies": conditions,
            "condition_labels": context.condition_labels,
            "dimensions": selected,
            "dimension_results": [item.model_dump(mode="json") for item in dimension_results],
            "curation_warnings": [item.model_dump(mode="json") for item in warnings],
            "snapshot_ids": [str(item) for item in context.snapshot_ids],
            "claim_set_fingerprint": claim_set_fingerprint,
            "algorithm_id": _ALGORITHM_ID,
            "algorithm_version": _ALGORITHM_VERSION,
            "disclaimer": _DISCLAIMER,
        }
        run = self._repository.create_research_run(spec)
        if run.status is RunStatus.FAILED:
            raise RuntimeError(_failed_run_message(run))
        if run.status is RunStatus.COMPLETED:
            if run.result is None:
                raise RuntimeError(f"Completed comparison run {run.id} has no result payload")
            return _v2_result_from_run(run)
        if run.status is RunStatus.PENDING:
            try:
                run = self._repository.transition_research_run(run.id, RunStatus.RUNNING)
            except RunTransitionError:
                run = _reload_run(self._repository, run.id)
        if run.status is RunStatus.RUNNING:
            try:
                run = self._repository.transition_research_run(
                    run.id,
                    RunStatus.COMPLETED,
                    result=payload,
                )
            except RunTransitionError:
                run = _reload_run(self._repository, run.id)
        if run.status is RunStatus.FAILED:
            raise RuntimeError(_failed_run_message(run))
        if run.status is not RunStatus.COMPLETED or run.result is None:
            raise RuntimeError(f"Comparison run {run.id} did not produce a completed result")
        return _v2_result_from_run(run)

    def get_comparison(self, run_id: UUID) -> CompareV2Result:
        run = self._repository.get_research_run(run_id)
        if run is None or run.run_type != _RUN_TYPE:
            raise CompareRunNotFoundError(f"Comparison run {run_id} not found")
        if run.status is not RunStatus.COMPLETED or run.result is None:
            raise CompareRunIncompleteError(f"Comparison run {run_id} is not complete")
        return _v2_result_from_run(run)

    def compare(
        self,
        left_curie: str,
        right_curie: str,
        *,
        dimensions: list[str] | None = None,
    ) -> CompareResult:
        requested = list(LEGACY_DEFAULT_DIMENSIONS if dimensions is None else dimensions)
        if not requested:
            raise ValueError("At least one comparison dimension is required")
        unknown = [
            item for item in requested if _LEGACY_ALIASES.get(item, item) not in DEFAULT_DIMENSIONS
        ]
        if unknown:
            raise ValueError(f"Unknown comparison dimensions: {', '.join(unknown)}")
        canonical = [_LEGACY_ALIASES.get(item, item) for item in requested]
        v2 = self.compare_many([left_curie, right_curie], dimensions=canonical)
        left = self._resolve_condition(left_curie)
        right = self._resolve_condition(right_curie)
        by_dimension = {item.dimension: item for item in v2.dimension_results}
        overlaps: list[DimensionOverlap] = []
        seen: set[str] = set()
        for legacy_name, canonical_name in zip(requested, canonical, strict=True):
            if legacy_name in seen:
                continue
            seen.add(legacy_name)
            item = by_dimension[canonical_name]
            left_coverage = item.coverage_by_condition[left]
            right_coverage = item.coverage_by_condition[right]
            overlaps.append(
                DimensionOverlap(
                    dimension=legacy_name,
                    shared=item.shared_by_all,
                    unique_to_left=item.unique_by_condition[left],
                    unique_to_right=item.unique_by_condition[right],
                    missing_data=DimensionMissingData(
                        left=_legacy_missing_reason(left_coverage),
                        right=_legacy_missing_reason(right_coverage),
                    ),
                    left_evidence_count=left_coverage.evidence_count,
                    right_evidence_count=right_coverage.evidence_count,
                    warnings=[warning.message for warning in item.warnings],
                )
            )
        return CompareResult(
            run_id=v2.run_id,
            status=v2.status,
            left_curie=left,
            right_curie=right,
            dimensions=list(dict.fromkeys(requested)),
            overlaps=overlaps,
            curation_warnings=[item.message for item in v2.curation_warnings],
            snapshot_ids=v2.snapshot_ids,
            claim_set_fingerprint=v2.claim_set_fingerprint,
            algorithm_id="nosograph-compare",
            algorithm_version=v2.algorithm_version,
            disclaimer=v2.disclaimer,
        )

    def _resolve_condition(self, curie: str) -> str:
        normalized = normalize_curie(curie)
        view = self._repository.get_entity(normalized)
        if view is None:
            resolved = self._repository.resolve_exact_curie(normalized)
            if resolved is not None:
                normalized = resolved
                view = self._repository.get_entity(resolved)
        if view is None or view.entity.entity_type is not EntityType.CONDITION:
            raise ValueError(f"Unresolved condition CURIE: {normalized}")
        return normalized


def _canonical_dimensions(dimensions: list[str] | None) -> list[str]:
    if dimensions is None:
        return list(DEFAULT_DIMENSIONS)
    if not dimensions:
        raise ValueError("At least one comparison dimension is required")
    unknown = sorted({item for item in dimensions if item not in DEFAULT_DIMENSIONS})
    if unknown:
        raise ValueError(f"Unknown comparison dimensions: {', '.join(unknown)}")
    selected = set(dimensions)
    return [item for item in DEFAULT_DIMENSIONS if item in selected]


def _legacy_missing_reason(coverage: ConditionCoverage) -> MissingDataReason:
    positive = coverage.positive_claim_count
    negated = coverage.negated_claim_count
    if positive:
        return MissingDataReason.NOT_APPLICABLE
    if negated:
        return MissingDataReason.KNOWN_ABSENT
    return MissingDataReason.NOT_RECORDED


def _v2_result_from_run(run: ResearchRun) -> CompareV2Result:
    payload = dict(run.result or {})
    condition_curies = list(payload.get("condition_curies", []))
    condition_labels = dict(payload.get("condition_labels", {}))
    condition_labels = {
        curie: str(condition_labels.get(curie) or curie) for curie in condition_curies
    }
    dimension_results = []
    for stored in list(payload.get("dimension_results", [])):
        item = dict(stored)
        rows = []
        for stored_row in list(item.get("entities", [])):
            row = dict(stored_row)
            entity_curie = str(row.get("entity_curie", ""))
            row["entity_label"] = str(row.get("entity_label") or entity_curie)
            stored_claims = dict(row.get("claim_ids_by_condition", {}))
            row["claim_ids_by_condition"] = {
                curie: list(stored_claims.get(curie, [])) for curie in condition_curies
            }
            rows.append(row)
        item["entities"] = rows
        dimension_results.append(DimensionComparison.model_validate(item))
    return CompareV2Result(
        run_id=run.id,
        result_schema_version=str(payload.get("result_schema_version", "1.0")),
        status=str(payload.get("status", "insufficient_data")),
        condition_curies=condition_curies,
        condition_labels=condition_labels,
        dimensions=list(payload.get("dimensions", [])),
        dimension_results=dimension_results,
        curation_warnings=list(payload.get("curation_warnings", [])),
        snapshot_ids=run.snapshot_ids,
        claim_set_fingerprint=str(payload.get("claim_set_fingerprint", run.fingerprint)),
        algorithm_id=str(payload.get("algorithm_id", _ALGORITHM_ID)),
        algorithm_version=str(payload.get("algorithm_version", _ALGORITHM_VERSION)),
        disclaimer=str(payload.get("disclaimer", _DISCLAIMER)),
    )


def _reload_run(repository: BiomedicalRepository, run_id: UUID) -> ResearchRun:
    run = repository.get_research_run(run_id)
    if run is None:
        raise RuntimeError(f"Comparison run {run_id} disappeared during execution")
    return run


def _failed_run_message(run: ResearchRun) -> str:
    detail = "; ".join(run.warnings) or "no failure detail recorded"
    return f"Comparison run {run.id} failed: {detail}"
