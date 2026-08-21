"""Deterministic coverage and provenance summary for disease modules."""

from __future__ import annotations

import hashlib
import json

from med_research.diseases.base import Disease
from med_research.diseases.coverage import coverage_for_disease, module_coverage
from med_research.diseases.curation_tiers import tier_summary_row
from med_research.diseases.tier_model import compute_tier

DEFAULT_MODULE_INPUTS = {
    "literature": ("genes", "drugs", "pathways", "pubmed_queries"),
    "gwas": ("genes", "gwas_search_terms"),
    "enrichment": ("genes", "pathways"),
    "ppi": ("genes",),
    "screening": ("genes", "drugs", "pathways", "screening_profile"),
    "safety": ("symptoms", "adverse_event_profile", "safety_risk"),
    "car_t": ("genes", "car_t_scores"),
    "repurposing": ("genes", "drugs", "relationships"),
    "synergy": ("genes", "drugs"),
    "biomarkers": ("genes",),
    "expression": ("genes", "drugs"),
    "network_pharm": ("genes", "relationships"),
    "ml_predictor": ("genes", "relationships"),
    "clinical_trials": ("genes", "drugs", "trial_query"),
    "cross_disease": ("genes", "drugs", "pathways"),
    "semantic": ("genes", "drugs", "pubmed_queries"),
    "evidence_gather": ("genes", "drugs", "pathways", "pubmed_queries"),
    "evidence_extract": (),
    "evidence_monitor": ("genes", "pubmed_queries"),
    "kg": ("genes", "drugs", "pathways", "relationships"),
}

# Alias for API/registry consumers that prefer MODULE_INPUTS naming.
MODULE_INPUTS = DEFAULT_MODULE_INPUTS


def build_coverage_report(
    disease_id: str,
    modules: tuple[str, ...] = tuple(DEFAULT_MODULE_INPUTS),
) -> dict:
    """Build a stable report without timestamps or generated run identifiers."""
    disease = Disease(disease_id)
    checks = disease.validate()
    drug_count = len(disease.load_drugs().get("drugs", []))
    strict_pass = all(status == "ok" for status in checks.values())
    readiness_tier = compute_tier(
        disease_id, checks, drug_count=drug_count, strict_pass=strict_pass
    )
    config_gaps = [field for field, status in checks.items() if status != "ok"]
    payload = {
        "disease_id": disease_id,
        "name": disease.get_display_name(),
        **tier_summary_row(
            disease_id,
            readiness_tier,
            strict_pass=strict_pass,
            config_gaps=config_gaps,
            phenotype_curated=bool(disease.get_symptoms()),
            mechanism_curated=bool(disease.load_pathways().get("pathways")),
            treatment_curated=drug_count > 0,
        ),
        "entity_counts": {
            "genes": len(disease.load_genes().get("genes", [])),
            "drugs": len(disease.load_drugs().get("drugs", [])),
            "pathways": len(disease.load_pathways().get("pathways", [])),
            "relationships": len(disease.load_relationships().get("relationships", [])),
        },
        "core": coverage_for_disease(disease_id).to_dict(),
        "modules": {
            name: module_coverage(
                disease_id,
                name,
                DEFAULT_MODULE_INPUTS.get(name, ()),
            ).to_dict()
            for name in modules
        },
    }
    fingerprint = hashlib.sha256(
        json.dumps(payload, sort_keys=True, ensure_ascii=False).encode("utf-8")
    ).hexdigest()
    return {**payload, "fingerprint": fingerprint}
