"""Tests for batch strict validation reporting."""

from types import SimpleNamespace

import med_research.diseases.validation_batch as validation_batch
from med_research.diseases.identifiers import CI_VALIDATED_DISEASES, REFERENCE_DISEASES
from med_research.diseases.validation_batch import (
    EXIT_OK,
    EXIT_USAGE,
    EXIT_VALIDATION_FAILED,
    classify_failure,
    run_strict_validation_batch,
    select_validation_targets,
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


def _candidate_pool(size: int = 40) -> list[str]:
    return [f"disease_{index:02d}" for index in range(size)]


def test_sampling_is_deterministic_across_calls() -> None:
    pool = _candidate_pool()
    first, _ = select_validation_targets(disease_ids=pool, sample_size=5, sample_seed=7)
    second, _ = select_validation_targets(disease_ids=pool, sample_size=5, sample_seed=7)

    assert first == second
    assert len(first) == 5
    assert set(first) <= set(pool)


def test_sampling_changes_with_seed() -> None:
    pool = _candidate_pool()
    seeded_a, _ = select_validation_targets(disease_ids=pool, sample_size=5, sample_seed=1)
    seeded_b, _ = select_validation_targets(disease_ids=pool, sample_size=5, sample_seed=2)

    assert seeded_a != seeded_b


def test_sample_larger_than_candidate_pool_returns_all() -> None:
    pool = _candidate_pool(3)
    targets, excluded = select_validation_targets(disease_ids=pool, sample_size=10)

    assert sorted(targets) == sorted(pool)
    assert excluded == 0


def test_sample_size_zero_is_legal() -> None:
    targets, excluded = select_validation_targets(disease_ids=_candidate_pool(), sample_size=0)
    assert targets == []
    assert excluded == 0

    report = run_strict_validation_batch(tier_filter="all", disease_ids=[], sample_size=0)
    assert report["summary"]["total"] == 0
    assert report["summary"]["failed"] == 0
    assert report["summary"]["sampled"] is True


def test_blocked_slugs_excluded_from_targets() -> None:
    targets, excluded = select_validation_targets(
        disease_ids=["sle", "zz_scaffold_test", "positive_regulation_of_ovulation"]
    )

    assert targets == ["sle"]
    assert excluded == 2


def test_run_batch_reports_blocked_exclusions() -> None:
    report = run_strict_validation_batch(
        tier_filter="all",
        disease_ids=["sle", "zz_scaffold_test", "positive_regulation_of_ovulation"],
    )

    summary = report["summary"]
    assert summary["total"] == 1
    assert summary["excluded_blocked"] == 2
    assert summary["failed"] == 0
    assert [entry["disease_id"] for entry in report["entries"]] == ["sle"]


def test_failure_groups_are_grouped_and_sorted(monkeypatch) -> None:
    class _FakeDisease:
        def __init__(self, disease_id: str) -> None:
            self.disease_id = disease_id
            self.profile = SimpleNamespace(name=disease_id)

        def validate(self) -> dict[str, str]:
            return {"profile": "ok", "genes": "missing", "SYMPTOMS": "empty"}

    monkeypatch.setattr(validation_batch, "Disease", _FakeDisease)

    report = run_strict_validation_batch(tier_filter="all", disease_ids=["alpha"])
    summary = report["summary"]

    assert summary["failure_groups"] == {"SYMPTOMS": 1, "genes": 1}
    assert list(summary["failure_groups"]) == ["SYMPTOMS", "genes"]
    assert summary["failure_classes"] == {"MISSING_REQUIRED_DATA": 2}
    assert len(report["entries"][0]["failures"]) == 2


def test_sampling_metadata_is_reported() -> None:
    report = run_strict_validation_batch(
        tier_filter="all",
        disease_ids=["sle", "ra", "ibd"],
        sample_size=2,
        sample_seed=11,
    )
    summary = report["summary"]

    assert summary["sampled"] is True
    assert summary["sample_size"] == 2
    assert summary["sample_seed"] == 11
    assert summary["total"] == 2


def test_exit_codes_are_stable() -> None:
    assert (EXIT_OK, EXIT_VALIDATION_FAILED, EXIT_USAGE) == (0, 1, 2)
    assert len({EXIT_OK, EXIT_VALIDATION_FAILED, EXIT_USAGE}) == 3
