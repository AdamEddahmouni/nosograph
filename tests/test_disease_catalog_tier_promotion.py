"""Tests for Disease Catalog Curation & Tier Promotion."""

from __future__ import annotations

import pytest

from med_research.diseases.base import Disease
from med_research.diseases.tier_model import compute_tier

PROMOTED_DISEASES = [
    # Oncology
    "colorectal_cancer",
    "acute_myeloid_leukemia",
    "glioblastoma",
    "melanoma",
    "breast_cancer",
    # Neurodegenerative
    "pd",
    "als",
    "huntington_disease",
    # Rare Metabolic
    "gaucher_disease",
    "fabry_disease",
    "phenylketonuria",
    "wilson_disease",
    # Respiratory & Metabolic
    "copd",
    "asthma",
    "t2d",
    # Cardiovascular
    "coronary_artery_disease",
    "heart_failure",
    "dilated_cardiomyopathy",
    "essential_hypertension",
    "coronary_atherosclerosis",
    "atherosclerosis",
    # Infectious & Immune Subtypes
    "tuberculosis",
    "hiv",
    "hiv_1_infection",
    "lupus_nephritis",
    "sjogren_syndrome",
    # Psychiatric & CNS (Wave 3)
    "major_depressive_disorder",
    "schizophrenia",
    "bipolar_disorder",
    "epilepsy",
    # Metabolic & Hepatic (Wave 3)
    "non_alcoholic_fatty_liver_disease",
    "obesity",
    "t1d",
    "hyperlipidemia",
    # Connective Tissue & Dermatology (Wave 3)
    "scleroderma",
    "systemic_scleroderma",
    "alopecia_areata",
    "vitiligo",
    "celiac_disease",
    # Solid Oncology & Rare Neuromuscular (Wave 4)
    "nsclc",
    "triple_neg_breast_cancer",
    "pancreatic_ductal_adenocarcinoma",
    "cystic_fibrosis",
    "sickle_cell_anemia",
    "spinal_muscular_atrophy",
]


@pytest.mark.parametrize("disease_id", PROMOTED_DISEASES)
def test_promoted_disease_validation(disease_id: str):
    """Verify that every promoted disease passes strict schema validation with 0 gaps."""
    d = Disease(disease_id)
    checks = d.validate()

    assert checks["genes"] == "ok", f"{disease_id} genes check failed: {checks.get('genes')}"
    assert checks["drugs"] == "ok", f"{disease_id} drugs check failed: {checks.get('drugs')}"
    assert checks["pathways"] == "ok", (
        f"{disease_id} pathways check failed: {checks.get('pathways')}"
    )
    assert checks["relationships"] == "ok", (
        f"{disease_id} relationships check failed: {checks.get('relationships')}"
    )
    assert checks["profile"] == "ok", f"{disease_id} profile check failed: {checks.get('profile')}"

    assert checks["SYMPTOMS"] == "ok", f"{disease_id} symptoms empty"
    assert checks["PUBMED_QUERIES"] == "ok", f"{disease_id} pubmed queries empty"
    assert checks["TRIAL_QUERY"] == "ok", f"{disease_id} trial query empty"
    assert checks["GWAS_SEARCH_TERMS"] == "ok", f"{disease_id} gwas search terms empty"
    assert checks["CAR_T_SCORES"] == "ok", f"{disease_id} car-t scores empty"
    assert checks["DRUG_SAFETY_RISK"] == "ok", f"{disease_id} drug safety risk empty"

    d_count = len(d.load_drugs().get("drugs", []))
    strict_pass = all(s == "ok" for s in checks.values())
    assert strict_pass is True

    tier = compute_tier(disease_id, checks, drug_count=d_count, strict_pass=strict_pass)
    assert tier in ("L2", "L3"), f"{disease_id} tier is {tier}, expected L2 or L3"


@pytest.mark.parametrize("disease_id", PROMOTED_DISEASES)
def test_promoted_disease_entities_loaded(disease_id: str):
    """Verify that genes, drugs, and symptoms are accessible via Disease helpers."""
    d = Disease(disease_id)
    genes = d.load_genes().get("genes", [])
    drugs = d.load_drugs().get("drugs", [])
    symptoms = d.get_symptoms()
    risk = d.get_disease_risk_config()

    assert len(genes) > 0
    assert len(drugs) > 0
    assert len(symptoms) >= 5
    assert isinstance(risk, dict)
    assert "high_risk" in risk
