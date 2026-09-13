"""Harvest catalog reconciliation and CI drift checks."""

from __future__ import annotations

import pytest

from med_research.diseases.harvest_registry import (
    CATEGORY_C_DELETE,
    ON_DISK_GO_RESPONSE_EXCLUSIONS,
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


def test_on_disk_go_response_exclusions_are_classified_and_not_category_c() -> None:
    expected = {
        "heart_rate_response_to_exercise",
        "heart_rate_response_to_recovery_post_exercise",
        "response_to_bronchodilator",
        "response_to_covid_19_vaccine",
        "response_to_paracetamol",
        "response_to_selective_serotonin_reuptake_inhibitor",
        "response_to_statin",
        "response_to_stimulus",
        "response_to_surgery",
        "response_to_vaccine",
        "response_to_xenobiotic_stimulus",
        "trait_in_response_to_apixaban",
        "trait_in_response_to_triamcinolone_acetonide",
    }
    assert set(ON_DISK_GO_RESPONSE_EXCLUSIONS) == expected
    assert not CATEGORY_C_DELETE
    classes = {klass for klass, _reason in ON_DISK_GO_RESPONSE_EXCLUSIONS.values()}
    assert classes <= {"A", "B", "C", "D", "E"}
    assert "C" not in classes
    for slug in expected:
        assert should_exclude_from_harvest(slug)


def test_live_go_like_exclusions_match_classified_table() -> None:
    report = drift_report()
    on_disk = set(report["intentional_exclusions_on_disk"])
    assert on_disk == set(ON_DISK_GO_RESPONSE_EXCLUSIONS)
    assert report["unclassified_go_like_on_disk"] == []
    assert report["category_c_on_disk"] == []
    assert format_drift_errors(report) == []


def test_scaffold_refuses_new_go_like_modules(tmp_path) -> None:
    from med_research.diseases import scaffold

    with pytest.raises(ValueError, match="Refusing to scaffold"):
        scaffold.scaffold_disease(
            "response_to_stimulus",
            name="response to stimulus",
            target_dir=tmp_path / "response_to_stimulus",
            use_cache=False,
            use_bulk=False,
        )
