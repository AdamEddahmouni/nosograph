"""Screening and safety coverage for the Wave 3/4 L3 disease slice."""

from __future__ import annotations

import pytest

from med_research.diseases.base import Disease
from med_research.diseases.coverage import module_coverage
from med_research.diseases.schemas import AdverseEventsFile, validate_and_load
from med_research.pipeline.virtual_screening.screening_strategy import strategy_for_disease

L3_SLICE = (
    "nsclc",
    "pancreatic_ductal_adenocarcinoma",
    "glioblastoma",
    "cystic_fibrosis",
    "sickle_cell_anemia",
    "heart_failure",
    "non_alcoholic_fatty_liver_disease",
)

WAVE2_SLICE = (
    "melanoma",
    "colorectal_cancer",
    "triple_neg_breast_cancer",
    "breast_cancer",
    "acute_myeloid_leukemia",
    "spinal_muscular_atrophy",
    "major_depressive_disorder",
    "epilepsy",
)

L3_CHRONIC_SLICE = (
    "copd",
    "asthma",
    "t2d",
    "als",
)

pytestmark = pytest.mark.unit


@pytest.mark.parametrize("disease_id", L3_SLICE + WAVE2_SLICE + L3_CHRONIC_SLICE)
def test_l3_slice_screening_strategy_uses_catalog_drugs(disease_id):
    strategy = strategy_for_disease(disease_id)
    catalog = {drug["id"] for drug in Disease(disease_id).load_drugs()["drugs"]}
    assert strategy.disease_id == disease_id
    assert strategy.pathway_keywords
    assert strategy.mechanism_keywords
    assert strategy.reference_drug_ids
    assert set(strategy.reference_drug_ids) <= catalog
    coverage = module_coverage(
        disease_id, "screening", ("genes", "drugs", "pathways", "screening_profile")
    )
    assert coverage.status == "ready"
    assert coverage.level == "full"


@pytest.mark.parametrize("disease_id", L3_SLICE + WAVE2_SLICE + L3_CHRONIC_SLICE)
def test_l3_slice_safety_profile_is_ready(disease_id):
    disease = Disease(disease_id)
    path = disease.data_dir / "adverse_events.json"
    payload = validate_and_load(path, AdverseEventsFile)
    assert payload["disease_id"] == disease_id
    catalog = {drug["id"] for drug in disease.load_drugs()["drugs"]}
    profile_ids = {entry["drug_id"] for entry in payload["profiles"]}
    assert profile_ids <= catalog
    coverage = module_coverage(
        disease_id, "safety", ("symptoms", "adverse_event_profile", "safety_risk")
    )
    assert coverage.status == "ready"
    assert coverage.level == "full"
