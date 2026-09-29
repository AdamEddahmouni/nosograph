"""Unit tests for the disease drug-safety scaffolding (inferred derivation)."""

import json

import pytest

from med_research.diseases.safety_scaffold import (
    RISK_TIERS,
    _unique_drugs,
    classify_drug_tier,
    derive_adverse_events_payload,
    derive_drug_safety_risk,
    match_drug_class,
    parse_adverse_effects,
)

pytestmark = pytest.mark.unit


def _drugs(*entries):
    return {"drugs": [dict(e) for e in entries]}


def test_named_agent_pattern_takes_precedence_over_class():
    """A named agent keeps its historical tier even when a class would match."""
    tier, basis = classify_drug_tier(
        {"id": "CHEMBL1", "name": "Infliximab", "mechanism": "TNF inhibitor"}
    )
    assert (tier, basis) == ("high_risk", "pattern")

    tier, basis = classify_drug_tier(
        {"id": "CHEMBL2", "name": "Budesonide", "mechanism": "Glucocorticoid receptor agonist"}
    )
    assert (tier, basis) == ("moderate_risk", "pattern")


def test_pharmacologic_class_supplies_tier_when_no_pattern_matches():
    tier, basis = classify_drug_tier(
        {"id": "CHEMBL3", "name": "Zoliflodacin", "mechanism": "Tubulin inhibitor"}
    )
    assert (tier, basis) == ("high_risk", "class")

    tier, basis = classify_drug_tier(
        {"id": "CHEMBL4", "name": "Olodaterol", "mechanism": "Adrenergic receptor agonist"}
    )
    assert (tier, basis) == ("low_risk", "class")


def test_antagonist_is_not_mistaken_for_agonist():
    """ "antagonist" contains "agonist"; the rules must not confuse them."""
    rule = match_drug_class("Adrenergic receptor beta antagonist")
    assert rule is not None and rule.name == "adrenergic_antagonist"
    rule = match_drug_class("Adrenergic receptor agonist")
    assert rule is not None and rule.name == "adrenergic_agonist"
    tier, basis = classify_drug_tier(
        {"id": "X", "name": "Propranolol-like", "mechanism": "Adrenergic receptor beta antagonist"}
    )
    assert (tier, basis) == ("moderate_risk", "class")


def test_unclassifiable_drug_is_undetermined_not_low_risk():
    tier, basis = classify_drug_tier(
        {"id": "CHEMBL5", "name": "ZZZ-99", "mechanism": "Something unrecognised"}
    )
    assert (tier, basis) == ("undetermined_risk", "undetermined")


def test_derive_risk_never_drops_a_drug():
    payload = _drugs(
        {"id": "A", "name": "Infliximab", "mechanism": "TNF inhibitor"},
        {"id": "B", "name": "ZZZ-99", "mechanism": "Something unrecognised"},
        {"id": "C", "name": "Olodaterol", "mechanism": "Adrenergic receptor agonist"},
    )
    risk = derive_drug_safety_risk(payload)
    assert set(risk) == set(RISK_TIERS)
    assert sum(len(v) for v in risk.values()) == 3
    assert risk["undetermined_risk"] == ["zzz-99"]
    assert risk["high_risk"] == ["infliximab"]
    assert risk["low_risk"] == ["olodaterol"]


def test_drug_target_rows_are_deduplicated():
    payload = _drugs(
        {
            "id": "CHEMBL1",
            "name": "ELX-02",
            "target": "RPS25",
            "mechanism": "80S Ribosome modulator",
        },
        {
            "id": "CHEMBL1",
            "name": "ELX-02",
            "target": "RPL21",
            "mechanism": "80S Ribosome modulator",
        },
        {
            "id": "CHEMBL1",
            "name": "ELX-02",
            "target": "RPS17",
            "mechanism": "80S Ribosome modulator",
        },
    )
    unique = _unique_drugs(payload)
    assert len(unique) == 1
    assert "RPL21" in unique[0]["target"]
    risk = derive_drug_safety_risk(payload)
    assert sum(len(v) for v in risk.values()) == 1


def test_drugs_without_id_are_ignored():
    payload = _drugs(
        {"name": "anonymous"}, {"id": "A", "name": "Infliximab", "mechanism": "TNF inhibitor"}
    )
    assert sum(len(v) for v in derive_drug_safety_risk(payload).values()) == 1


def test_parse_adverse_effects_splits_and_normalises():
    assert parse_adverse_effects("Headache; nausea, Dizziness") == [
        "headache",
        "nausea",
        "dizziness",
    ]
    assert parse_adverse_effects("") == []
    assert parse_adverse_effects("ab") == []


def test_match_drug_class_finds_class_in_mechanism_text():
    rule = match_drug_class("Glucocorticoid receptor agonist")
    assert rule is not None and rule.name == "corticosteroid"
    assert rule.severe_ae
    assert match_drug_class("Something unrecognised") is None


def test_adverse_events_payload_satisfies_profiler_contract():
    payload = derive_adverse_events_payload(
        "demo_disease",
        _drugs(
            {"id": "CHEMBL1", "name": "Infliximab", "mechanism": "TNF inhibitor"},
            {"id": "CHEMBL2", "name": "ZZZ-99", "mechanism": "Something unrecognised"},
        ),
        symptoms=["fatigue", "arthritis"],
    )
    assert payload["disease_id"] == "demo_disease"
    assert payload["source"], "source must be non-empty"
    assert payload["limitations"], "limitations must be non-empty"

    defaults = payload["default_profile"]
    required = {
        "common_ae",
        "severe_ae",
        "disease_overlap_ae",
        "severity_burden",
        "chronic_use_safety",
        "disease_specific_risk",
        "monitoring_required",
        "evidence_grade",
    }
    assert required <= set(defaults)
    for field in ("severity_burden", "chronic_use_safety", "disease_specific_risk"):
        assert 0 <= defaults[field] <= 10
    for field in ("common_ae", "severe_ae", "disease_overlap_ae", "black_box_warnings"):
        assert isinstance(defaults[field], list)

    catalog = {"CHEMBL1", "CHEMBL2"}
    assert all(p["drug_id"] in catalog for p in payload["profiles"])
    # every tier bucket is recorded, including the undetermined one
    assert set(payload["drug_safety_tiers"]) == set(RISK_TIERS)
    assert payload["drug_safety_tiers"]["undetermined_risk"] == ["zzz-99"]


def test_unresolved_drugs_are_reported_as_a_limitation():
    payload = derive_adverse_events_payload(
        "demo_disease",
        _drugs({"id": "CHEMBL2", "name": "ZZZ-99", "mechanism": "Something unrecognised"}),
    )
    joined = " ".join(payload["limitations"])
    assert "unclassified" in joined or "undetermined" in joined or "not known" in joined
    # an empty AE list must not read as "no adverse events"
    assert not payload["profiles"]


def test_class_level_adverse_events_are_inferred():
    payload = derive_adverse_events_payload(
        "demo_disease",
        _drugs({"id": "CHEMBL9", "name": "Zoliflodacin", "mechanism": "Tubulin inhibitor"}),
        symptoms=["neuropathy"],
    )
    assert payload["profiles"], "class match should yield a per-drug profile"
    profile = payload["profiles"][0]
    assert profile["evidence_grade"] == "inferred_class_default"
    assert profile["severe_ae"]
    # symptom overlap is computed against the module's own symptom list
    assert profile["disease_overlap_ae"]
    assert payload["source"] == "class_level_inference_from_disease_drug_catalog"
    assert "drug_class_adverse_event_patterns" in payload["inferred_inputs"]


def test_payload_round_trips_through_json():
    payload = derive_adverse_events_payload(
        "demo_disease", _drugs({"id": "A", "name": "Infliximab", "mechanism": "TNF inhibitor"})
    )
    assert json.loads(json.dumps(payload)) == payload
