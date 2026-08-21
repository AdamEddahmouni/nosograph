"""Tests for batch strict validation reporting."""

from med_research.diseases.identifiers import CI_VALIDATED_DISEASES, REFERENCE_DISEASES
from med_research.diseases.validation_batch import (
    classify_failure,
    run_strict_validation_batch,
)


def test_ci_validated_batch_all_pass() -> None:
    report = run_strict_validation_batch(tier_filter="ci_validated")
    assert report["summary"]["total"] == len(CI_VALIDATED_DISEASES)
    assert report["summary"]["failed"] == 0


def test_reference_batch_structure() -> None:
    report = run_strict_validation_batch(tier_filter="reference")
    assert report["summary"]["total"] == len(REFERENCE_DISEASES)
    assert "entries" in report
    assert "failure_class_definitions" in report


def test_classify_schema_failure() -> None:
    assert classify_failure("genes", "invalid: bad json") == "SCHEMA"


def test_classify_missing_config() -> None:
    assert classify_failure("PUBMED_QUERIES", "empty") == "MISSING_REQUIRED_DATA"
