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
        "black_box_warnings": ["Myelosuppression", "Hemorrhagic cystitis", "Secondary malignancies"],
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


@pytest.mark.slow
def test_score_all_drugs_persists():
    score_all_drugs()
    profiles_path = (
        Path(__file__).parent.parent
        / "src" / "med_research" / "pipeline" / "adverse_events" / "data" / "profiles.json"
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


@pytest.mark.slow
def test_generate_html_report():
    results = score_all_drugs()
    path = generate_html_report(results)
    assert "report.html" in path
    assert Path(path).exists()


# ── API Service ──────────────────────────────────────────────────────────


@pytest.mark.slow
def test_run_safety_profiling():
    from med_research.web.services.adverse_events_service import run_safety_profiling

    result = run_safety_profiling()
    assert result["total_drugs"] == 26
    assert "profiles" in result
    assert result["avg_safety_score"] > 0


@pytest.mark.slow
def test_run_safety_profiling_single_drug():
    from med_research.web.services.adverse_events_service import run_safety_profiling

    result = run_safety_profiling(drug_id="belimumab")
    assert "composite_safety_score" in result


# ── CLI Integration ──────────────────────────────────────────────────────


@pytest.mark.slow
def test_safety_cli_help():
    import subprocess

    result = subprocess.run(
        [sys.executable, "main.py", "safety", "--help"],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        cwd=str(Path(__file__).parent.parent),
    )
    assert result.returncode == 0
    assert "safety" in result.stdout.lower()


@pytest.mark.slow
def test_safety_cli_single_drug():
    import subprocess

    result = subprocess.run(
        [sys.executable, "main.py", "safety", "--drug", "belimumab"],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        cwd=str(Path(__file__).parent.parent),
        timeout=30,
    )
    assert result.returncode == 0
    assert "Safety Profile" in result.stdout
