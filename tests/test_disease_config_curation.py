"""Parametrized curation contract tests for all seven disease configs."""

import re

import pytest

from med_research.diseases.base import Disease

DISEASE_IDS = ("sle", "ra", "ms", "ibd", "ss", "ssc", "t1d", "melanoma", "nsclc", "glioblastoma")
NON_SLE = tuple(d for d in DISEASE_IDS if d != "sle")

pytestmark = pytest.mark.unit


@pytest.mark.parametrize("disease_id", DISEASE_IDS)
def test_car_t_scores_have_minimum_category_depth(disease_id):
    disease = Disease(disease_id)
    scores = disease.get_car_t_scores()
    assert scores, f"{disease_id}: CAR_T_SCORES must be populated"
    assert any(scores.values()), f"{disease_id}: CAR_T tables must contain gene scores"
    if disease_id == "sle":
        assert len(scores) >= 5
    else:
        assert len(scores) >= 5, f"{disease_id}: need >=5 pathway categories"


@pytest.mark.parametrize("disease_id", DISEASE_IDS)
def test_drug_safety_risk_tiers_populated(disease_id):
    disease = Disease(disease_id)
    config = disease.config
    assert config.get("DRUG_SAFETY_RISK"), f"{disease_id}: DRUG_SAFETY_RISK missing"
    assert config.get("DISEASE_SPECIFIC_RISK") is config["DRUG_SAFETY_RISK"]
    assert config.get("DRUG_INDUCED_LUPUS_RISK") is config["DRUG_SAFETY_RISK"]

    risk = disease.get_disease_risk_config()
    assert risk
    assert any(risk.values()), f"{disease_id}: safety tiers must list drugs"
    for tier in ("high_risk", "moderate_risk", "low_risk"):
        assert tier in risk


@pytest.mark.parametrize("disease_id", NON_SLE)
def test_non_sle_pubmed_queries_are_disease_specific(disease_id):
    disease = Disease(disease_id)
    queries = disease.config.get("PUBMED_QUERIES") or []
    assert queries, f"{disease_id}: PUBMED_QUERIES required"
    for query in queries:
        lower = query.lower()
        assert "lupus" not in lower
        assert not re.search(r"\bsle\b", lower)


@pytest.mark.parametrize("disease_id", NON_SLE)
def test_non_sle_gwas_terms_exclude_sle(disease_id):
    from med_research.pipeline.bioinformatics.gwas import disease_search_terms

    terms = disease_search_terms(disease_id)
    assert terms
    for term in terms:
        lower = term.lower()
        assert "lupus" not in lower
        assert lower != "sle"


@pytest.mark.parametrize("disease_id", NON_SLE)
def test_populate_script_structural_validation_non_sle(disease_id):
    from scripts.populate_disease_configs import validate_disease

    report = validate_disease(disease_id, rubric_strict=False)
    assert report["ok"], report["issues"]


def test_populate_script_structural_validation_sle():
    from scripts.populate_disease_configs import validate_disease

    report = validate_disease("sle", rubric_strict=False)
    assert report["ok"], report["issues"]


@pytest.mark.parametrize("disease_id", NON_SLE)
def test_literature_queries_from_disease_config(disease_id):
    from med_research.pipeline.literature_mining.miner import _disease_queries

    queries = _disease_queries(disease_id)
    assert queries == Disease(disease_id).config["PUBMED_QUERIES"]


def test_profiler_reads_drug_safety_risk_for_ra():
    from med_research.pipeline.adverse_events.profiler import _load_disease_specific_risk

    risk = _load_disease_specific_risk("ra")
    assert risk["high_risk"]
    assert any("infliximab" in item.lower() for item in risk["high_risk"])


def test_enrichment_disease_gene_list_helper():
    from med_research.pipeline.bioinformatics.enrichment import load_disease_gene_list

    genes = load_disease_gene_list("ra")
    assert genes
    assert all("symbol" in g or "gene_id" in g for g in genes)
