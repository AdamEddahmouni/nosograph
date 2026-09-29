"""Regression tests for disease-specific adverse-event coverage."""

import pytest

from med_research.diseases.base import Disease
from med_research.diseases.coverage import module_coverage
from med_research.pipeline.adverse_events.profiler import (
    compute_adverse_event_score,
    get_safety_summary,
    load_profiles,
    score_all_drugs,
)
from med_research.web.services.adverse_events_service import run_safety_profiling

DISEASES = ["sle", "ra", "ms", "ss", "ssc", "t1d", "ibd"]

pytestmark = pytest.mark.unit


@pytest.mark.parametrize("disease_id", DISEASES)
def test_safety_profiles_are_ready_and_scoped_to_catalog(disease_id):
    coverage = module_coverage(
        disease_id, "safety", ("symptoms", "adverse_event_profile", "safety_risk")
    )
    profiles = load_profiles(disease_id)
    catalog_ids = {drug["id"] for drug in Disease(disease_id).load_drugs()["drugs"]}
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
    assert all(result["score_status"] in {"scored", "insufficient_evidence"} for result in results)
    assert all(
        0 <= result["composite_safety_score"] <= 10
        for result in results
        if result["score_status"] == "scored"
    )
    assert all(
        result["composite_safety_score"] is None
        for result in results
        if result["score_status"] == "insufficient_evidence"
    )


def test_undetermined_drugs_have_no_numeric_safety_scores(monkeypatch):
    from types import SimpleNamespace

    from med_research.diseases import coverage

    runnable = SimpleNamespace(level="full", is_runnable=True, to_dict=lambda: {})
    monkeypatch.setattr(coverage, "module_coverage", lambda *args, **kwargs: runnable)
    monkeypatch.setattr("med_research.cache.write_json_atomic", lambda *_args, **_kwargs: None)
    profiles = load_profiles("cardiac_arrest")
    amiodarone = next(
        profile for profile in profiles.values() if profile["drug_name"].lower() == "amiodarone"
    )
    rocuronium = next(
        profile
        for profile in profiles.values()
        if profile["drug_name"].lower() == "rocuronium bromide"
    )

    score_fields = (
        "disease_symptom_overlap_score",
        "disease_overlap_score",
        "lupus_symptom_overlap_score",
        "severity_burden_score",
        "chronic_use_safety_score",
        "disease_specific_risk_score",
        "dil_risk_score",
        "composite_safety_score",
    )
    for profile in (amiodarone, rocuronium):
        assert profile["score_status"] == "insufficient_evidence"
        assert profile["profile_source"]
        assert profile["limitations"]
        score = compute_adverse_event_score(profile, disease_id="cardiac_arrest")
        assert score["score_status"] == "insufficient_evidence"
        assert all(score[field] is None for field in score_fields)

    ketamine = next(
        profile for profile in profiles.values() if profile["drug_name"].lower() == "ketamine"
    )
    assert ketamine["score_status"] == "insufficient_evidence"
    determinate = compute_adverse_event_score(profiles["CHEMBL679"], disease_id="cardiac_arrest")
    assert determinate["score_status"] == "scored"
    assert isinstance(determinate["composite_safety_score"], float)

    results = score_all_drugs(disease_id="cardiac_arrest")
    scored = [result for result in results if result["score_status"] == "scored"]
    unscored = [result for result in results if result["score_status"] == "insufficient_evidence"]
    assert scored and unscored
    assert results == scored + unscored
    assert all(
        left["composite_safety_score"] >= right["composite_safety_score"]
        for left, right in zip(scored, scored[1:], strict=False)
    )
    assert all(result["composite_safety_score"] is None for result in unscored)


def test_summary_excludes_unscored_results_from_statistics():
    results = [
        {
            "drug_name": "Safer",
            "score_status": "scored",
            "composite_safety_score": 8.0,
            "disease_specific_risk_score": 10.0,
            "black_box_warnings": [],
        },
        {
            "drug_name": "Riskier",
            "score_status": "scored",
            "composite_safety_score": 4.0,
            "disease_specific_risk_score": 5.0,
            "black_box_warnings": [],
        },
        {
            "drug_name": "Unknown",
            "score_status": "insufficient_evidence",
            "composite_safety_score": None,
            "disease_specific_risk_score": None,
            "black_box_warnings": [],
        },
    ]

    summary = get_safety_summary("sle", results)

    assert summary["total_drugs"] == 3
    assert summary["scored_drugs"] == 2
    assert summary["unscored_drugs"] == 1
    assert summary["avg_safety_score"] == 6.0
    assert summary["safest_drug"] == "Safer"
    assert summary["safest_score"] == 8.0
    assert summary["riskiest_drug"] == "Riskier"
    assert summary["riskiest_score"] == 4.0


def test_summary_with_no_scored_results_has_null_numeric_statistics():
    results = [
        {
            "drug_name": "Unknown",
            "score_status": "insufficient_evidence",
            "composite_safety_score": None,
            "disease_specific_risk_score": None,
            "black_box_warnings": [],
        },
    ]

    summary = get_safety_summary("sle", results)

    assert summary["scored_drugs"] == 0
    assert summary["unscored_drugs"] == 1
    assert summary["avg_safety_score"] is None
    assert summary["safest_drug"] == ""
    assert summary["safest_score"] is None
    assert summary["riskiest_drug"] == ""
    assert summary["riskiest_score"] is None


def test_cardiac_arrest_safety_service_preserves_insufficient_evidence(monkeypatch):
    from types import SimpleNamespace

    from med_research.diseases import coverage
    from med_research.pipeline.adverse_events.profiler import score_all_drugs
    from med_research.web.services import adverse_events_service

    runnable = SimpleNamespace(level="full", is_runnable=True, to_dict=lambda: {})
    monkeypatch.setattr(coverage, "module_coverage", lambda *args, **kwargs: runnable)
    monkeypatch.setattr(adverse_events_service, "module_coverage", lambda *args, **kwargs: runnable)
    monkeypatch.setattr("med_research.cache.write_json_atomic", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(
        adverse_events_service,
        "dispatch_sync_module",
        lambda *_args, **_kwargs: score_all_drugs(disease_id="cardiac_arrest"),
    )

    result = run_safety_profiling(disease_id="cardiac_arrest")

    assert result["total_drugs"] == result["scored_drugs"] + result["unscored_drugs"]
    assert result["unscored_drugs"] > 0
    unknown = next(
        profile
        for profile in result["profiles"]
        if profile["score_status"] == "insufficient_evidence"
    )
    assert unknown["composite_safety_score"] is None


def test_single_unknown_tier_service_profile_has_nullable_scores(monkeypatch):
    from types import SimpleNamespace

    from med_research.diseases import coverage
    from med_research.web.services import adverse_events_service

    runnable = SimpleNamespace(level="full", is_runnable=True, to_dict=lambda: {})
    monkeypatch.setattr(coverage, "module_coverage", lambda *args, **kwargs: runnable)
    monkeypatch.setattr(adverse_events_service, "module_coverage", lambda *args, **kwargs: runnable)
    profile = run_safety_profiling(drug_id="CHEMBL633", disease_id="cardiac_arrest")
    assert profile["score_status"] == "insufficient_evidence"
    assert profile["composite_safety_score"] is None


def test_safety_profiles_route_serializes_insufficient_evidence_profile(monkeypatch):
    from types import SimpleNamespace

    from fastapi.testclient import TestClient

    from med_research.diseases import coverage
    from med_research.web.main import app
    from med_research.web.services import adverse_events_service

    runnable = SimpleNamespace(level="full", is_runnable=True, to_dict=lambda: {})
    monkeypatch.setattr(coverage, "module_coverage", lambda *args, **kwargs: runnable)
    monkeypatch.setattr(adverse_events_service, "module_coverage", lambda *args, **kwargs: runnable)
    with TestClient(app) as client:
        response = client.get(
            "/api/safety/profiles",
            params={"disease": "cardiac_arrest", "drug_id": "CHEMBL633"},
        )

    assert response.status_code == 200
    profile = response.json()
    assert profile["drug_id"] == "CHEMBL633"
    assert profile["score_status"] == "insufficient_evidence"
    assert profile["composite_safety_score"] is None
    assert profile["disease_symptom_overlap_score"] is None
    assert profile["profile_source"]
    assert profile["limitations"]


def test_safety_profiles_route_summary_counts_unscored_drugs(monkeypatch):
    from types import SimpleNamespace

    from fastapi.testclient import TestClient

    from med_research.diseases import coverage
    from med_research.web.main import app
    from med_research.web.services import adverse_events_service

    runnable = SimpleNamespace(level="full", is_runnable=True, to_dict=lambda: {})
    monkeypatch.setattr(coverage, "module_coverage", lambda *args, **kwargs: runnable)
    monkeypatch.setattr(adverse_events_service, "module_coverage", lambda *args, **kwargs: runnable)
    monkeypatch.setattr("med_research.cache.write_json_atomic", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(
        adverse_events_service,
        "dispatch_sync_module",
        lambda *_args, **_kwargs: score_all_drugs(disease_id="cardiac_arrest"),
    )

    with TestClient(app) as client:
        response = client.get("/api/safety/profiles", params={"disease": "cardiac_arrest"})

    assert response.status_code == 200
    result = response.json()
    assert result["total_drugs"] == result["scored_drugs"] + result["unscored_drugs"]
    assert result["scored_drugs"] > 0
    assert result["unscored_drugs"] > 0
    assert result["avg_safety_score"] is not None
    profiles = result["profiles"]
    unknown = next(
        profile for profile in profiles if profile["score_status"] == "insufficient_evidence"
    )
    assert unknown["composite_safety_score"] is None
    assert all(
        profile["composite_safety_score"] is not None
        for profile in profiles
        if profile["score_status"] == "scored"
    )


def test_safety_profiles_route_summary_with_no_scored_drugs(monkeypatch):
    from types import SimpleNamespace

    from fastapi.testclient import TestClient

    from med_research.diseases import coverage
    from med_research.web.main import app
    from med_research.web.services import adverse_events_service

    runnable = SimpleNamespace(level="full", is_runnable=True, to_dict=lambda: {})
    monkeypatch.setattr(coverage, "module_coverage", lambda *args, **kwargs: runnable)
    monkeypatch.setattr(adverse_events_service, "module_coverage", lambda *args, **kwargs: runnable)
    monkeypatch.setattr("med_research.cache.write_json_atomic", lambda *_args, **_kwargs: None)
    score_fields = (
        "disease_symptom_overlap_score",
        "disease_overlap_score",
        "lupus_symptom_overlap_score",
        "severity_burden_score",
        "chronic_use_safety_score",
        "disease_specific_risk_score",
        "dil_risk_score",
        "composite_safety_score",
    )

    def all_unscored_results(*_args, **_kwargs):
        results = score_all_drugs(disease_id="cardiac_arrest")
        for result in results:
            result.update({"score_status": "insufficient_evidence", **dict.fromkeys(score_fields)})
        return results

    monkeypatch.setattr(adverse_events_service, "dispatch_sync_module", all_unscored_results)

    with TestClient(app) as client:
        response = client.get("/api/safety/profiles", params={"disease": "cardiac_arrest"})

    assert response.status_code == 200
    result = response.json()
    assert result["total_drugs"] > 0
    assert result["scored_drugs"] == 0
    assert result["unscored_drugs"] == result["total_drugs"]
    assert result["avg_safety_score"] is None
    assert result["safest_drug"] == ""
    assert result["safest_score"] is None
    assert result["riskiest_drug"] == ""
    assert result["riskiest_score"] is None
    assert all(
        profile["score_status"] == "insufficient_evidence"
        and all(profile[field] is None for field in score_fields)
        for profile in result["profiles"]
    )


def test_safety_models_accept_nullable_scores():

    from med_research.web.models.adverse_events import DrugSafetyProfile, SafetySummaryResponse

    profile = DrugSafetyProfile(
        drug_id="CHEMBL633",
        drug_name="AMIODARONE",
        disease_id="cardiac_arrest",
        score_status="insufficient_evidence",
        disease_symptom_overlap_score=None,
        disease_overlap_score=None,
        lupus_symptom_overlap_score=None,
        severity_burden_score=None,
        chronic_use_safety_score=None,
        disease_specific_risk_score=None,
        dil_risk_score=None,
        composite_safety_score=None,
    )
    summary = SafetySummaryResponse(
        disease_id="cardiac_arrest",
        total_drugs=1,
        scored_drugs=0,
        unscored_drugs=1,
        avg_safety_score=None,
        safest_drug="",
        safest_score=None,
        riskiest_drug="",
        riskiest_score=None,
        drugs_with_bbw=0,
        drugs_with_disease_specific_risk=0,
    )

    assert profile.score_status == "insufficient_evidence"
    assert profile.composite_safety_score is None
    assert summary.unscored_drugs == 1
    assert summary.avg_safety_score is None


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
    from med_research.cli import cmd_safety
    from tests.cli_helpers import run_cli_handler

    exit_code = run_cli_handler(
        cmd_safety,
        "safety",
        "--disease",
        "ra",
        "--drug",
        "not-a-drug",
    )
    assert exit_code != 0
