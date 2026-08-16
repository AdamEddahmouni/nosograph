"""Tests for Advanced Multi-Omics, Virtual Screening, CRISPR CFD, ADMET, Drug Synergy, and Clinical Trials Enhancements."""

from __future__ import annotations

from med_research.pipeline.admet.engine import (
    analyze_admet,
    predict_bbb_permeability,
    predict_cyp450_profile,
    predict_herg_toxicity,
)
from med_research.pipeline.clinical_trials.tracker import (
    classify_sponsor_portfolio,
    forecast_trial_progression,
    parse_eligibility_criteria,
)
from med_research.pipeline.crispr.engine import compute_cfd_score, evaluate_crispr_feasibility
from med_research.pipeline.drug_synergy.engine import (
    compute_bliss_excess_synergy,
    compute_loewe_combination_index,
    score_drug_pair,
)
from med_research.pipeline.multi_omics.engine import (
    analyze_multi_omics,
    compute_eqtl_colocalization,
)
from med_research.pipeline.virtual_screening.screening import (
    check_pains_alerts,
    evaluate_lipinski_rule_of_five,
    generate_vina_search_box,
)


def test_eqtl_colocalization_and_multi_omics():
    """Verify eQTL colocalization heuristic and multi-omics integration."""
    coloc = compute_eqtl_colocalization("TNF", "coronary_artery_disease")
    assert "coloc_pp4" in coloc
    assert 0.0 <= coloc["coloc_pp4"] <= 1.0
    assert "coloc_tissue" in coloc
    assert isinstance(coloc["is_colocalized"], bool)

    res = analyze_multi_omics("heart_failure")
    assert res["disease_id"] == "heart_failure"
    assert "Cardiomyocytes" in res["cell_types_analyzed"]
    assert len(res["targets"]) > 0
    top = res["targets"][0]
    assert "coloc_pp4" in top
    assert "dominant_cell_type" in top
    assert "composite_score" in top


def test_virtual_screening_lipinski_and_pains():
    """Verify Lipinski Rule of 5 validation and PAINS filter."""
    # Drug-like small molecule
    aspirin = {"mw": 180.16, "logp": 1.19, "hbd": 1, "hba": 3, "rotatable_bonds": 1}
    eval_asp = evaluate_lipinski_rule_of_five(aspirin)
    assert eval_asp["is_drug_like"] is True
    assert eval_asp["num_violations"] == 0

    # Non-compliant molecule
    heavy_mol = {"mw": 650.0, "logp": 6.5, "hbd": 7, "hba": 12, "rotatable_bonds": 14}
    eval_heavy = evaluate_lipinski_rule_of_five(heavy_mol)
    assert eval_heavy["is_drug_like"] is False
    assert eval_heavy["num_violations"] >= 3

    # PAINS check
    pains_hit = check_pains_alerts("rhodanine derivative")
    assert pains_hit["has_pains_alert"] is True
    assert len(pains_hit["pains_alerts"]) > 0

    clean_mol = check_pains_alerts("atorvastatin")
    assert clean_mol["has_pains_alert"] is False

    # Vina grid box generator
    box = generate_vina_search_box(center=(12.5, -4.2, 33.1), size=(25.0, 25.0, 25.0), exhaustiveness=16)
    assert box["center_x"] == 12.5
    assert box["size_x"] == 25.0
    assert box["exhaustiveness"] == 16
    assert "center_x = 12.5" in box["config_text"]


def test_crispr_cfd_scoring_and_feasibility():
    """Verify CFD matrix calculation and CRISPR feasibility evaluation."""
    guide = "ACCGTTAGCTAGCTAGCTAG"
    perfect_match = "ACCGTTAGCTAGCTAGCTAG"
    assert compute_cfd_score(guide, perfect_match) == 1.0

    # PAM-proximal seed mismatch at position 2 has heavy penalty
    seed_mismatch = "AACGTTAGCTAGCTAGCTAG"
    cfd_seed = compute_cfd_score(guide, seed_mismatch)
    assert 0.0 < cfd_seed <= 0.20

    # Non-seed mismatch at position 20 has minor penalty
    distal_mismatch = "ACCGTTAGCTAGCTAGCTAA"
    cfd_distal = compute_cfd_score(guide, distal_mismatch)
    assert cfd_distal > cfd_seed

    # Whole disease CRISPR feasibility
    res = evaluate_crispr_feasibility("tuberculosis")
    assert res["disease_id"] == "tuberculosis"
    assert res["total_genes"] > 0
    assert len(res["candidates"]) > 0
    top = res["candidates"][0]
    assert "loef_score" in top
    assert "pli_score" in top
    assert "delivery_accessibility" in top
    assert "crispr_priority_score" in top


def test_admet_bbb_cyp_and_herg():
    """Verify quantitative ADMET heuristics: BBB permeability, CYP profiles, and hERG risk."""
    # CNS active molecule
    cns_mol = predict_bbb_permeability(mw=240.0, logp=2.8, psa=35.0, hbd=1)
    assert cns_mol["bbb_category"] == "High (CNS Penetrant)"
    assert cns_mol["is_cns_active"] is True
    assert cns_mol["log_bb"] > 0.0

    # Peripheral large polar molecule
    polar_mol = predict_bbb_permeability(mw=550.0, logp=-1.2, psa=160.0, hbd=6)
    assert polar_mol["bbb_category"] == "Low (Peripheral Only)"
    assert polar_mol["is_cns_active"] is False

    # CYP450 profile
    cyp_small = predict_cyp450_profile("atorvastatin", "Small molecule")
    assert "inhibited_isozymes" in cyp_small
    assert "ddi_liability" in cyp_small
    assert isinstance(cyp_small["inhibited_isozymes"], list)

    cyp_bio = predict_cyp450_profile("evolocumab", "Monoclonal antibody")
    assert len(cyp_bio["inhibited_isozymes"]) == 0
    assert "Low" in cyp_bio["ddi_liability"]

    # hERG cardiotoxicity
    herg_safe = predict_herg_toxicity(logp=1.5, mw=250.0, basic_nitrogen_count=0)
    assert herg_safe["herg_risk_category"] == "Low"
    assert herg_safe["cardiotoxicity_warning"] is False

    herg_risky = predict_herg_toxicity(logp=5.2, mw=520.0, basic_nitrogen_count=2)
    assert herg_risky["herg_risk_category"] == "High"
    assert herg_risky["cardiotoxicity_warning"] is True

    # Full disease ADMET run
    res = analyze_admet("major_depressive_disorder")
    assert res["disease_id"] == "major_depressive_disorder"
    assert len(res["profiles"]) > 0
    top = res["profiles"][0]
    assert "composite_safety_score" in top
    assert "bbb_permeability" in top
    assert "cyp_inhibition_profile" in top


def test_drug_synergy_loewe_and_bliss():
    """Verify quantitative Loewe Combination Index and Bliss Independence synergy models."""
    # Synergistic pair
    loewe_syn = compute_loewe_combination_index(eff_a=8.5, eff_b=9.0, composite_score=8.5)
    assert loewe_syn["combination_index"] < 0.80
    assert loewe_syn["is_synergistic"] is True
    assert "Synergy" in loewe_syn["interpretation"]

    # Additive / lower score pair
    loewe_add = compute_loewe_combination_index(eff_a=3.0, eff_b=4.0, composite_score=3.5)
    assert loewe_add["combination_index"] >= 0.80

    # Bliss Independence
    bliss_syn = compute_bliss_excess_synergy(eff_a=4.0, eff_b=4.0, observed_synergy=9.0)
    assert bliss_syn["delta_bliss"] > 0.0
    assert bliss_syn["is_synergistic"] is True

    # Scored pair dictionary integration
    drug_a = {
        "id": "belimumab",
        "name": "Belimumab",
        "type": "Monoclonal Antibody",
        "target": "TNFSF13B",
        "category": "Biologic - B Cell Depletion",
        "mechanism": "BAFF inhibitor",
        "approval": "FDA Approved for SLE",
    }
    drug_b = {
        "id": "baricitinib",
        "name": "Baricitinib",
        "type": "Small Molecule",
        "target": "JAK1/JAK2",
        "category": "Targeted Synthetic - JAK Inhibitor",
        "mechanism": "JAK1 and JAK2 inhibitor",
        "approval": "FDA Approved",
    }
    pair = score_drug_pair(drug_a, drug_b)
    assert "loewe_combination_index" in pair
    assert "bliss_excess" in pair
    assert pair["composite_score"] > 5.0


def test_clinical_trials_eligibility_and_forecasting():
    """Verify ClinicalTrials eligibility parsing, phase duration forecasting, and sponsor portfolio."""
    raw_criteria = """
    Inclusion Criteria:
    - Age 18 to 75 years
    - Confirmed diagnosis of Type 2 Diabetes
    - HbA1c between 7.5% and 10.5%
    - On stable metformin therapy for >= 3 months

    Exclusion Criteria:
    - eGFR < 30 mL/min/1.73m2
    - Active severe diabetic ketoacidosis
    - History of pancreatitis
    - Pregnancy or breastfeeding
    Minimum Age: 18 Years
    Maximum Age: 75 Years
    Sex: All
    """
    elig = parse_eligibility_criteria(raw_criteria)
    assert elig["minimum_age"] == "18 Years"
    assert elig["maximum_age"] == "75 Years"
    assert elig["gender"] == "ALL"
    assert len(elig["inclusion_criteria"]) >= 3
    assert len(elig["exclusion_criteria"]) >= 3

    # Phase duration and PTRS forecasting
    fc1 = forecast_trial_progression("PHASE1")
    assert fc1["estimated_phase_duration_years"] == 1.5
    assert fc1["phase_transition_probability"] == 0.60
    assert "Phase 2" in fc1["next_milestone"]

    fc3 = forecast_trial_progression("PHASE3")
    assert fc3["estimated_phase_duration_years"] == 3.0
    assert fc3["ptrs_to_approval"] > 0.50

    # Sponsor portfolio aggregation
    mock_trials = [
        {"sponsor_class": "INDUSTRY", "primary_phase": "PHASE3"},
        {"sponsor_class": "INDUSTRY", "primary_phase": "PHASE2"},
        {"sponsor_class": "NIH", "primary_phase": "PHASE1"},
        {"sponsor_class": "OTHER", "primary_phase": "PHASE2"},
    ]
    portfolio = classify_sponsor_portfolio(mock_trials)
    assert portfolio["total_trials"] == 4
    assert portfolio["industry_sponsored_count"] == 2
    assert portfolio["industry_percentage"] == 50.0
    assert portfolio["nih_academic_count"] == 2
