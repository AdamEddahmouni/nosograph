from __future__ import annotations

from med_research.biomed.nosograph_compare.service import NosoGraphCompareService


def test_nosograph_compare_returns_dimension_overlaps_without_score(biomed_repository) -> None:
    service = NosoGraphCompareService(biomed_repository)
    result = service.compare(
        "MONDO:0007915",
        "MONDO:0008390",
        dimensions=["phenotype", "gene", "evidence_coverage"],
    )
    assert result.overlaps
    assert all(item.dimension for item in result.overlaps)
    assert not hasattr(result, "overall_score")
    assert result.claim_set_fingerprint


def test_nosograph_compare_missing_data_reasons_present(biomed_repository) -> None:
    result = NosoGraphCompareService(biomed_repository).compare(
        "MONDO:0007915",
        "MONDO:0008390",
        dimensions=["mechanism"],
    )
    overlap = result.overlaps[0]
    assert overlap.missing_data.left.value in {
        "UNKNOWN",
        "NOT_RECORDED",
        "NOT_APPLICABLE",
        "KNOWN_ABSENT",
    }
    assert overlap.missing_data.right.value in {
        "UNKNOWN",
        "NOT_RECORDED",
        "NOT_APPLICABLE",
        "KNOWN_ABSENT",
    }


def test_nosograph_compare_deterministic_ordering(biomed_repository) -> None:
    first = NosoGraphCompareService(biomed_repository).compare(
        "MONDO:0007915",
        "MONDO:0008390",
        dimensions=["gene", "phenotype"],
    )
    second = NosoGraphCompareService(biomed_repository).compare(
        "MONDO:0007915",
        "MONDO:0008390",
        dimensions=["gene", "phenotype"],
    )
    assert first.claim_set_fingerprint == second.claim_set_fingerprint
    assert [item.shared for item in first.overlaps] == [item.shared for item in second.overlaps]
