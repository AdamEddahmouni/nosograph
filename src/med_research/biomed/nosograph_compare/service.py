"""Evidence-aware condition comparison without universal similarity scores."""

from __future__ import annotations

from med_research.biomed.identifiers import fingerprint_json, normalize_curie
from med_research.biomed.models import ResearchRunCreate, RunStatus
from med_research.biomed.nosograph_compare.dimensions import (
    DIMENSION_REGISTRY,
    build_dimension_context,
)
from med_research.biomed.nosograph_compare.models import (
    DEFAULT_DIMENSIONS,
    CompareResult,
    DimensionOverlap,
)
from med_research.biomed.repository import BiomedicalRepository

_DISCLAIMER = (
    "For research and exploratory analysis only. Dimension overlaps summarize imported "
    "biomedical claims and evidence coverage. No universal similarity score is emitted. "
    "Not for clinical decision-making."
)
_ALGORITHM_ID = "nosograph-compare"
_ALGORITHM_VERSION = "1.0.0"
_RUN_TYPE = "nosograph_compare"


class NosoGraphCompareService:
    def __init__(self, repository: BiomedicalRepository) -> None:
        self._repository = repository

    def compare(
        self,
        left_curie: str,
        right_curie: str,
        *,
        dimensions: list[str] | None = None,
    ) -> CompareResult:
        left = normalize_curie(left_curie)
        right = normalize_curie(right_curie)
        selected = dimensions or list(DEFAULT_DIMENSIONS)
        unknown = [item for item in selected if item not in DIMENSION_REGISTRY]
        if unknown:
            raise ValueError(f"Unknown comparison dimensions: {', '.join(unknown)}")

        context = build_dimension_context(self._repository, left, right)
        overlaps: list[DimensionOverlap] = []
        curation_warnings: list[str] = []
        comparable_dimensions = 0

        for name in selected:
            overlap = DIMENSION_REGISTRY[name].compare(context)
            overlaps.append(overlap)
            if overlap.shared or overlap.unique_to_left or overlap.unique_to_right:
                comparable_dimensions += 1
            curation_warnings.extend(overlap.warnings)

        left_readiness = self._repository.list_claims(left)
        right_readiness = self._repository.list_claims(right)
        if len(left_readiness) > 2 * max(len(right_readiness), 1):
            curation_warnings.append(
                f"{left} has substantially more curated claims than {right}; comparisons may be asymmetric."
            )
        elif len(right_readiness) > 2 * max(len(left_readiness), 1):
            curation_warnings.append(
                f"{right} has substantially more curated claims than {left}; comparisons may be asymmetric."
            )

        status = "comparable" if comparable_dimensions >= 1 else "insufficient_data"
        snapshot_ids = sorted(
            {snapshot.id for snapshot in self._repository.list_active_snapshots()},
            key=str,
        )
        claim_set_fingerprint = fingerprint_json(
            {
                "left": context.left_fp.claim_set_fingerprint,
                "right": context.right_fp.claim_set_fingerprint,
                "dimensions": selected,
            }
        )
        spec = ResearchRunCreate(
            run_type=_RUN_TYPE,
            algorithm_id=_ALGORITHM_ID,
            algorithm_version=_ALGORITHM_VERSION,
            software_version="2.0.0",
            parameters={
                "left_curie": left,
                "right_curie": right,
                "dimensions": selected,
                "claim_set_fingerprint": claim_set_fingerprint,
            },
            snapshot_ids=snapshot_ids,
            claim_ids=sorted({*context.left_fp.claim_ids, *context.right_fp.claim_ids}, key=str),
            input_query=f"{left}|{right}|{','.join(selected)}",
        )
        run = self._repository.create_research_run(spec)
        if run.status is RunStatus.PENDING:
            self._repository.transition_research_run(run.id, RunStatus.RUNNING)
            payload = {
                "status": status,
                "left_curie": left,
                "right_curie": right,
                "dimensions": selected,
                "overlaps": [item.model_dump() for item in overlaps],
                "curation_warnings": curation_warnings,
                "claim_set_fingerprint": claim_set_fingerprint,
                "snapshot_ids": [str(item) for item in snapshot_ids],
                "algorithm_id": _ALGORITHM_ID,
                "algorithm_version": _ALGORITHM_VERSION,
                "disclaimer": _DISCLAIMER,
            }
            run = self._repository.transition_research_run(
                run.id,
                RunStatus.COMPLETED,
                result=payload,
            )

        return _result_from_run(run)


def _result_from_run(run: object) -> CompareResult:
    from med_research.biomed.models import ResearchRun

    assert isinstance(run, ResearchRun)
    payload = run.result or {}
    overlaps = [DimensionOverlap.model_validate(item) for item in list(payload.get("overlaps", []))]
    return CompareResult(
        run_id=run.id,
        status=str(payload.get("status", "insufficient_data")),
        left_curie=str(payload.get("left_curie", "")),
        right_curie=str(payload.get("right_curie", "")),
        dimensions=list(payload.get("dimensions", [])),
        overlaps=overlaps,
        curation_warnings=list(payload.get("curation_warnings", [])),
        snapshot_ids=run.snapshot_ids,
        claim_set_fingerprint=str(payload.get("claim_set_fingerprint", run.fingerprint)),
        algorithm_id=str(payload.get("algorithm_id", _ALGORITHM_ID)),
        algorithm_version=str(payload.get("algorithm_version", _ALGORITHM_VERSION)),
        disclaimer=str(payload.get("disclaimer", _DISCLAIMER)),
    )
