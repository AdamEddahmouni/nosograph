"""Harvest catalog reconciliation and CI drift checks."""

from __future__ import annotations

from med_research.diseases.harvest_registry import (
    REQUIRED_HARVEST_SLUGS,
    drift_report,
    format_drift_errors,
    proposed_harvest_entries,
    reconcile_harvest_registry,
    should_exclude_from_harvest,
)


def test_go_like_slugs_are_excluded_from_harvest() -> None:
    assert should_exclude_from_harvest("response_to_stimulus")
    assert should_exclude_from_harvest("trait_in_response_to_apixaban")
    assert should_exclude_from_harvest("heart_rate_response_to_exercise")
    assert should_exclude_from_harvest("positive_regulation_of_ovulation")
    assert not should_exclude_from_harvest("sle")
    assert not should_exclude_from_harvest("copd")


def test_reconcile_admits_ci_validated_and_skips_go_like() -> None:
    catalog = [{"id": "adult_onset_stills", "name": "Adult-onset Still disease"}]
    discoverable = ["sle", "ra", "response_to_stimulus", "copd"]
    proposed = proposed_harvest_entries(catalog, discoverable=discoverable)
    admitted = {item["id"] for item in proposed}
    assert "sle" in admitted
    assert "ra" in admitted
    assert "copd" in admitted
    assert "response_to_stimulus" not in admitted
    updated, _ = reconcile_harvest_registry(catalog, discoverable=discoverable)
    ids = {item["id"] for item in updated}
    assert "sle" in ids
    assert "response_to_stimulus" not in ids


def test_drift_report_requires_ci_and_reference_slugs() -> None:
    report = drift_report(
        entries=[{"id": "adult_onset_stills", "name": "x"}],
        discoverable=["sle", "response_to_statin"],
    )
    assert "sle" in report["required_missing"]
    assert "sle" in report["disease_like_missing"]
    assert "response_to_statin" not in report["disease_like_missing"]
    assert "response_to_statin" in report["intentional_exclusions_on_disk"]
    errors = format_drift_errors(report)
    assert any("sle" in error for error in errors)


def test_required_harvest_slugs_cover_ci_and_reference() -> None:
    from med_research.diseases.identifiers import CI_VALIDATED_DISEASES, REFERENCE_DISEASES

    assert CI_VALIDATED_DISEASES <= REQUIRED_HARVEST_SLUGS
    assert frozenset(REFERENCE_DISEASES) <= REQUIRED_HARVEST_SLUGS
