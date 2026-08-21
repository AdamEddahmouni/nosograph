"""View helpers for NosoGraph Compare API responses."""

from __future__ import annotations

from med_research.biomed.nosograph_compare.models import CompareResult
from med_research.web.models.universal import (
    DimensionMissingDataView,
    DimensionOverlapView,
    NosoGraphCompareResultView,
    ResearchDisclaimer,
)

_DISCLAIMER = ResearchDisclaimer()


def to_compare_view(result: CompareResult) -> NosoGraphCompareResultView:
    return NosoGraphCompareResultView(
        run_id=result.run_id,
        status=result.status,
        left_curie=result.left_curie,
        right_curie=result.right_curie,
        dimensions=result.dimensions,
        overlaps=[
            DimensionOverlapView(
                dimension=item.dimension,
                shared=item.shared,
                unique_to_left=item.unique_to_left,
                unique_to_right=item.unique_to_right,
                missing_data=DimensionMissingDataView(
                    left=item.missing_data.left.value,
                    right=item.missing_data.right.value,
                ),
                left_evidence_count=item.left_evidence_count,
                right_evidence_count=item.right_evidence_count,
                warnings=item.warnings,
            )
            for item in result.overlaps
        ],
        curation_warnings=result.curation_warnings,
        snapshot_ids=result.snapshot_ids,
        claim_set_fingerprint=result.claim_set_fingerprint,
        algorithm_id=result.algorithm_id,
        algorithm_version=result.algorithm_version,
        disclaimer=_DISCLAIMER,
    )
