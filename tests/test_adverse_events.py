"""
Tests for the Adverse Event Profiling module.
"""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from med_research.pipeline.adverse_events.profiler import (
    LUPUS_SYMPTOMS,
    compute_adverse_event_score,
    count_lupus_symptom_overlap,
    get_drug_profile,
    get_safety_summary,
    load_profiles,
    score_all_drugs,
    score_chronic_safety,
    score_dil_risk,
    score_lupus_overlap,
    score_severity_burden,
)
from med_research.pipeline.adverse_events.report import escape_html, generate_html_report

pytestmark = pytest.mark.unit


# ── Fixtures ──────────────────────────────────────────────────────────────


@pytest.fixture
def safe_drug_profile():
    return {
        "drug_id": "deucravacitinib",
        "drug_name": "Deucravacitinib",
        "lupus_overlap_ae": ["headache"],
        "severity_burden": 3,
        "chronic_use_safety": 7,
        "dil_risk": 0,
        "black_box_warnings": [],
        "severe_ae": ["serious infections"],
    }


@pytest.fixture
def risky_drug_profile():
    return {
        "drug_id": "cyclophosphamide",
        "drug_name": "Cyclophosphamide",
        "lupus_overlap_ae": ["alopecia", "leukopenia"],
        "severity_burden": 9,
        "chronic_use_safety": 1,
        "dil_risk": 1,
        "black_box_warnings": [
            "Myelosuppression",
            "Hemorrhagic cystitis",
            "Secondary malignancies",
        ],
        "severe_ae": ["bone marrow failure", "bladder cancer", "pulmonary fibrosis"],
    }


# ── Unit: Lupus Symptom Overlap ──────────────────────────────────────────


def test_lupus_symptoms_list():
    assert "fatigue" in LUPUS_SYMPTOMS
    assert "arthritis" in LUPUS_SYMPTOMS
    assert "rash" in LUPUS_SYMPTOMS
    assert "nephritis" in LUPUS_SYMPTOMS


def test_count_lupus_overlap_none(safe_drug_profile):
    assert count_lupus_symptom_overlap(safe_drug_profile) >= 0


def test_count_lupus_overlap_multiple(risky_drug_profile):
    count = count_lupus_symptom_overlap(risky_drug_profile)
    assert count >= 1


def test_score_lupus_overlap_safe(safe_drug_profile):
    score = score_lupus_overlap(safe_drug_profile)
    assert score >= 6.0


def test_score_lupus_overlap_risky(risky_drug_profile):
    score = score_lupus_overlap(risky_drug_profile)
    assert score <= 8.0


# ── Unit: Severity Burden ────────────────────────────────────────────────


def test_score_severity_burden_safe(safe_drug_profile):
    score = score_severity_burden(safe_drug_profile)
    assert score >= 5.0  # 10 - 3 = 7


def test_score_severity_burden_risky(risky_drug_profile):
    score = score_severity_burden(risky_drug_profile)
    assert score <= 2.0  # 10 - 9 = 1


# ── Unit: Chronic Use Safety ─────────────────────────────────────────────


def test_score_chronic_safety(safe_drug_profile):
    score = score_chronic_safety(safe_drug_profile)
    assert score == 7.0


# ── Unit: DIL Risk ───────────────────────────────────────────────────────


def test_score_dil_risk_none():
    profile = {"dil_risk": 0}
    assert score_dil_risk(profile) == 10.0


def test_score_dil_risk_some():
    profile = {"dil_risk": 1}
    assert score_dil_risk(profile) == 5.0


def test_score_dil_risk_high():
    profile = {"dil_risk": 2}
    assert score_dil_risk(profile) == 2.0


# ── Unit: Composite Scoring ──────────────────────────────────────────────


def test_compute_adverse_event_score_safe(safe_drug_profile):
    result = compute_adverse_event_score(safe_drug_profile)
    assert result["composite_safety_score"] > 6.0
    assert "lupus_symptom_overlap_score" in result
    assert "severity_burden_score" in result
    assert "chronic_use_safety_score" in result
    assert "dil_risk_score" in result


def test_compute_adverse_event_score_risky(risky_drug_profile):
    result = compute_adverse_event_score(risky_drug_profile)
    assert result["composite_safety_score"] < 5.0
    assert len(result["black_box_warnings"]) == 3


def test_compute_adverse_event_score_range(safe_drug_profile):
    result = compute_adverse_event_score(safe_drug_profile)
    assert 0.0 <= result["composite_safety_score"] <= 10.0


# ── Integration: Profile Loading ─────────────────────────────────────────


def test_load_profiles_returns_all_drugs():
    profiles = load_profiles()
    assert len(profiles) == 26
    assert "hydroxychloroquine" in profiles
    assert "belimumab" in profiles


def test_score_all_drugs():
    results = score_all_drugs()
    assert len(results) == 26
    # Should be sorted by safety score descending
    assert results[0]["composite_safety_score"] >= results[-1]["composite_safety_score"]


def test_score_all_drugs_persists():
    score_all_drugs()
    profiles_path = (
        Path(__file__).parent.parent
        / "src"
        / "med_research"
        / "pipeline"
        / "adverse_events"
        / "data"
        / "profiles.json"
    )
    assert profiles_path.exists()


# ── Integration: Summary ─────────────────────────────────────────────────


def test_get_safety_summary():
    summary = get_safety_summary()
    assert summary["total_drugs"] == 26
    assert summary["avg_safety_score"] > 0
    assert summary["safest_drug"]
    assert summary["riskiest_drug"]


def test_get_drug_profile_known():
    profile = get_drug_profile("hydroxychloroquine")
    assert profile
    assert "composite_safety_score" in profile


def test_get_drug_profile_unknown():
    profile = get_drug_profile("nonexistent")
    assert profile == {}


# ── Report ───────────────────────────────────────────────────────────────


def test_escape_html_safety():
    assert escape_html("<b>bold</b>") == "&lt;b&gt;bold&lt;/b&gt;"
    assert escape_html("") == ""
    assert escape_html(None) == ""


def test_generate_html_report():
    results = score_all_drugs()
    path = generate_html_report(results)
    assert "report.html" in path
    assert Path(path).exists()


# ── API Service ──────────────────────────────────────────────────────────


def test_run_safety_profiling():
    from med_research.web.services.adverse_events_service import run_safety_profiling

    result = run_safety_profiling()
    assert result["total_drugs"] == 26
    assert "profiles" in result
    assert result["avg_safety_score"] > 0


def test_run_safety_profiling_single_drug():
    from med_research.web.services.adverse_events_service import run_safety_profiling

    result = run_safety_profiling(drug_id="belimumab")
    assert "composite_safety_score" in result


# ── CLI Integration ──────────────────────────────────────────────────────


def test_safety_cli_help():
    from tests.cli_helpers import cli_help_output

    help_text = cli_help_output("safety", "--help")
    assert "safety" in help_text.lower()


def test_safety_cli_single_drug(caplog):
    import logging

    from med_research.cli import cmd_safety
    from tests.cli_helpers import run_cli_handler

    with caplog.at_level(logging.INFO):
        exit_code = run_cli_handler(cmd_safety, "safety", "--disease", "sle", "--drug", "belimumab")

    assert exit_code == 0
    assert "Safety Profile" in caplog.text


def test_safety_cli_displays_insufficient_evidence(caplog, monkeypatch):
    import logging

    from med_research.cli import cmd_safety
    from med_research.pipeline.adverse_events import profiler
    from tests.cli_helpers import run_cli_handler

    monkeypatch.setattr(
        profiler,
        "get_drug_profile",
        lambda *_args, **_kwargs: {
            "drug_name": "AMIODARONE",
            "score_status": "insufficient_evidence",
            "composite_safety_score": None,
            "disease_symptom_overlap_score": None,
            "severity_burden_score": None,
            "chronic_use_safety_score": None,
            "disease_specific_risk_score": None,
            "black_box_warnings": [],
            "disease_overlap_ae": [],
        },
    )

    with caplog.at_level(logging.INFO):
        exit_code = run_cli_handler(
            cmd_safety,
            "safety",
            "--disease",
            "cardiac_arrest",
            "--drug",
            "CHEMBL633",
        )

    assert exit_code == 0
    assert "Insufficient evidence" in caplog.text
    assert "None/10" not in caplog.text


def test_safety_report_displays_unscored_drug_without_numeric_values(monkeypatch, tmp_path):
    from med_research.pipeline.adverse_events import report
    from med_research.pipeline.adverse_events.profiler import compute_adverse_event_score

    scored = compute_adverse_event_score(
        {
            "drug_id": "scored-drug",
            "drug_name": "Scored Drug",
            "severity_burden": 3,
            "chronic_use_safety": 7,
            "disease_specific_risk": 0,
            "disease_overlap_ae": [],
            "severe_ae": [],
            "black_box_warnings": [],
        },
        disease_id="cardiac_arrest",
    )
    unscored = {
        **scored,
        "drug_id": "unknown-drug",
        "drug_name": "Unknown Drug",
        "score_status": "insufficient_evidence",
    }
    for field in (
        "disease_symptom_overlap_score",
        "disease_overlap_score",
        "lupus_symptom_overlap_score",
        "severity_burden_score",
        "chronic_use_safety_score",
        "disease_specific_risk_score",
        "dil_risk_score",
        "composite_safety_score",
    ):
        unscored[field] = None

    monkeypatch.setattr(report, "report_output_dir", lambda _path: tmp_path)
    output = Path(report.generate_html_report([scored, unscored], disease_id="cardiac_arrest"))
    html = output.read_text(encoding="utf-8")
    output.unlink()

    assert "Scored Drug" in html
    assert "Unknown Drug" in html
    assert "Insufficient evidence" in html
    assert "Average Safety Score (1 scored)" in html
    assert "Insufficient Evidence (1 unscored)" in html
    assert "Total Drugs Profiled" in html
    assert "None/10" not in html
    highlights = html.split("Top 10 Safest Drugs", 1)[-1].split("Complete Safety Rankings", 1)[0]
    assert "Unknown Drug" not in highlights
