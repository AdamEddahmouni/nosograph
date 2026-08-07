"""Disease-neutral safety terminology contract tests."""

from med_research.pipeline.adverse_events.profiler import (
    compute_adverse_event_score,
    count_disease_symptom_overlap,
    count_lupus_symptom_overlap,
    get_safety_summary,
    score_disease_overlap,
    score_disease_specific_risk,
    score_dil_risk,
    score_lupus_overlap,
)


def test_neutral_scorers_are_authoritative_and_legacy_names_are_aliases():
    profile = {
        "drug_id": "fixture",
        "drug_name": "Fixture",
        "common_ae": ["diarrhea"],
        "disease_overlap_ae": ["diarrhea"],
        "severity_burden": 2,
        "chronic_use_safety": 8,
        "disease_specific_risk": 0,
        "dil_risk": 9,
        "severe_ae": [],
    }

    assert count_disease_symptom_overlap(profile, "ibd") == count_lupus_symptom_overlap(profile, "ibd")
    assert score_disease_overlap(profile, "ibd") == score_lupus_overlap(profile, "ibd")
    assert score_disease_specific_risk(profile, "ibd") == score_dil_risk(profile, "ibd")

    result = compute_adverse_event_score(profile, disease_id="ibd")
    assert result["disease_symptom_overlap_score"] == result["disease_overlap_score"]
    assert result["disease_specific_risk_score"] == result["dil_risk_score"]
    assert result["disease_overlap_ae"] == profile["disease_overlap_ae"]
    assert result["lupus_overlap_ae"] == result["disease_overlap_ae"]


def test_summary_exposes_neutral_risk_count_with_legacy_alias():
    summary = get_safety_summary("ra", results=[])
    assert "drugs_with_disease_specific_risk" in summary
    assert summary["drugs_with_disease_specific_risk"] == summary["drugs_with_dil_risk"]


def test_api_model_makes_neutral_fields_primary():
    from med_research.web.models.adverse_events import DrugSafetyProfile

    profile = DrugSafetyProfile(
        drug_id="fixture",
        drug_name="Fixture",
        disease_id="ibd",
        disease_symptom_overlap_score=8,
        disease_overlap_score=8,
        severity_burden_score=8,
        chronic_use_safety_score=8,
        disease_specific_risk_score=9,
        composite_safety_score=8.2,
        n_disease_overlap_ae=1,
    )
    assert profile.disease_specific_risk_score == 9
