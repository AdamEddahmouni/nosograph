"""Tests for L0-L3 tier model."""

from med_research.diseases.tier_model import compute_tier


def test_l3_for_curated_consensus() -> None:
    checks = {field: "ok" for field in ("genes", "drugs", "pathways", "relationships", "profile")}
    assert compute_tier("sle", checks) == "L3"


def test_l0_missing_kg() -> None:
    checks = {
        "genes": "missing",
        "drugs": "missing",
        "pathways": "missing",
        "relationships": "missing",
        "profile": "missing",
    }
    assert compute_tier("example", checks) == "L0"


def test_l2_strict_pass() -> None:
    checks = {
        "genes": "ok",
        "drugs": "ok",
        "pathways": "ok",
        "relationships": "ok",
        "profile": "ok",
        "SYMPTOMS": "ok",
        "PUBMED_QUERIES": "ok",
        "TRIAL_QUERY": "ok",
        "GWAS_SEARCH_TERMS": "ok",
        "CAR_T_SCORES": "ok",
        "DRUG_SAFETY_RISK": "ok",
    }
    assert compute_tier("example_scaffold", checks, drug_count=5, strict_pass=True) == "L2"


def test_drug_safety_not_required_without_drugs() -> None:
    checks = {
        "genes": "ok",
        "drugs": "ok",
        "pathways": "ok",
        "relationships": "ok",
        "profile": "ok",
        "SYMPTOMS": "ok",
        "PUBMED_QUERIES": "ok",
        "TRIAL_QUERY": "ok",
        "GWAS_SEARCH_TERMS": "ok",
        "CAR_T_SCORES": "ok",
    }
    assert compute_tier("rare", checks, drug_count=0, strict_pass=True) == "L2"
