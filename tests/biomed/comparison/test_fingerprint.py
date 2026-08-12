from __future__ import annotations

from med_research.biomed.comparison.fingerprint import build_fingerprint


def test_fingerprint_separates_positive_and_negative_phenotypes(biomed_repository) -> None:
    fp = build_fingerprint(biomed_repository, "MONDO:0007915")
    assert fp.positive_phenotypes
    assert isinstance(fp.negative_phenotypes, list)
    assert fp.claim_set_fingerprint


def test_fingerprint_records_coverage_per_dimension(biomed_repository) -> None:
    fp = build_fingerprint(biomed_repository, "MONDO:0008390")
    assert "phenotype" in fp.coverage
    assert "gene" in fp.coverage
