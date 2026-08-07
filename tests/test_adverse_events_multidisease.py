"""Regression tests for disease-specific adverse-event coverage."""

import pytest

from med_research.diseases.coverage import module_coverage
from med_research.diseases.base import Disease
from med_research.pipeline.adverse_events.profiler import (
    get_drug_profile,
    load_profiles,
    score_all_drugs,
)
from med_research.web.services.adverse_events_service import run_safety_profiling

DISEASES = ["sle", "ra", "ms", "ss", "ssc", "t1d", "ibd"]


@pytest.mark.parametrize("disease_id", DISEASES)
def test_safety_profiles_are_ready_and_scoped_to_catalog(disease_id):
    coverage = module_coverage(
        disease_id, "safety", ("symptoms", "adverse_event_profile", "safety_risk")
    )
    profiles = load_profiles(disease_id)
    catalog_ids = {
        drug["id"] for drug in Disease(disease_id).load_drugs()["drugs"]
    }
    assert coverage.status == "ready"
    assert profiles
    assert set(profiles) == catalog_ids
    assert all(profile["disease_id"] == disease_id for profile in profiles.values())
    assert all(profile["profile_source"] for profile in profiles.values())
    assert all(profile["limitations"] for profile in profiles.values())


@pytest.mark.parametrize("disease_id", DISEASES)
def test_all_diseases_produce_safety_scores_with_neutral_metadata(disease_id):
    results = score_all_drugs(disease_id=disease_id)
    assert results
    assert {result["disease_id"] for result in results} == {disease_id}
    assert all("disease_symptom_overlap_score" in result for result in results)
    assert all("disease_specific_risk_score" in result for result in results)
    assert all(0 <= result["composite_safety_score"] <= 10 for result in results)


def test_non_sle_profile_does_not_use_shared_sle_cache():
    ra_profiles = load_profiles("ra")
    assert "belimumab" not in ra_profiles
    assert "methotrexate" in ra_profiles
    assert all(profile["disease_id"] == "ra" for profile in ra_profiles.values())


def test_single_drug_service_exposes_profile_provenance():
    result = run_safety_profiling(drug_id="methotrexate", disease_id="ra")
    assert result["status"] == "ready"
    assert result["disease_id"] == "ra"
    assert result["coverage"]["module"] == "safety"
    assert result["profile_source"]
    assert result["limitations"]
    assert "disease_overlap_ae" in result


def test_safety_service_summary_exposes_profile_provenance():
    result = run_safety_profiling(disease_id="ibd")
    assert result["status"] == "ready"
    assert result["disease_id"] == "ibd"
    assert result["total_drugs"] == len(Disease("ibd").load_drugs()["drugs"])
    assert result["profile_source"]
    assert result["profile_inferred_inputs"]
    assert result["limitations"]


def test_invalid_profile_drug_reference_is_blocked(monkeypatch):
    original = Disease.get_adverse_event_profile

    def invalid_profile(self):
        payload = original(self)
        if self.disease_id == "ra":
            return {**payload, "profiles": [{"drug_id": "not-in-catalog"}]}
        return payload

    monkeypatch.setattr(Disease, "get_adverse_event_profile", invalid_profile)
    with pytest.raises(ValueError, match="unknown drugs"):
        from med_research.pipeline.adverse_events import profiler
        profiler._load_disease_profile_payload("ra")


def test_profiler_cli_unknown_drug_returns_nonzero():
    import subprocess
    import sys

    result = subprocess.run(
        [sys.executable, "-m", "med_research.pipeline.adverse_events.profiler", "--disease", "ra", "--drug", "not-a-drug"],
        capture_output=True,
        text=True,
        cwd=".",
    )
    assert result.returncode != 0
