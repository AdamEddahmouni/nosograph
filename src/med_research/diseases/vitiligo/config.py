"""Vitiligo configuration.

Disease-specific parameters used by research pipeline modules.
"""

PIPELINE_LABEL = "Vitiligo"
DEFAULT_SAMPLE_SIZE = 50

# ── Symptoms (used by adverse_events/profiler.py) ────────────────────────
SYMPTOMS = [
    "completely depigmented chalk-white macules and patches",
    "poliosis (premature whitening of hair, eyebrows, eyelashes)",
    "koebner phenomenon (isomorphic response to friction/trauma)",
    "generalized symmetric bilateral depigmentation",
    "segmental dermatomal unilateral depigmentation",
    "trichrome vitiligo lesions with intermediate hypopigmented zones",
    "mucosal depigmentation (lips, oral mucosa, genitalia)",
    "pruritus and erythema at actively spreading margins",
    "increased sensitivity to sunburn in amelanotic skin",
]

# ── Literature Mining ────────────────────────────────────────────────────
PUBMED_QUERIES = [
    "(vitiligo[Title/Abstract] OR leukoderma[Title/Abstract]) AND (treatment[Title/Abstract] OR therapeutics[Title/Abstract])",
    "(vitiligo[Title/Abstract]) AND (ruxolitinib[Title/Abstract] OR JAK inhibitor[Title/Abstract] OR phototherapy[Title/Abstract] OR calcineurin[Title/Abstract])",
    "(vitiligo[Title/Abstract]) AND (melanocyte[Title/Abstract] OR CXCL10[Title/Abstract] OR repigmentation[Title/Abstract])",
    "(vitiligo[Title/Abstract]) AND (clinical trial[Title/Abstract])",
]

# ── Clinical trials / GWAS search terms ────────────────────────────────
TRIAL_QUERY = "Vitiligo OR Nonsegmental Vitiligo OR Segmental Vitiligo"
GWAS_SEARCH_TERMS = ["vitiligo", "autoimmune disease", "alopecia areata", "Hashimoto thyroiditis"]

# ── CAR-T & Target Scoring Tables ───────────────────────────────────────
CAR_T_SCORES = {
    "IFN_GAMMA_JAK_STAT_PATHWAY": {
        "JAK1": 10.0,
        "JAK2": 9.5,
        "STAT1": 9.5,
        "IFNG": 10.0,
        "CXCL9": 9.5,
        "CXCL10": 10.0,
        "CXCR3": 9.5,
    },
    "MELANOCYTE_ANTIGENS_APOPTOSIS": {
        "TYR": 9.5,
        "MLANA": 9.0,
        "PMEL": 9.0,
        "DCT": 8.5,
        "CD8A": 9.5,
        "GZMB": 9.0,
        "FAS": 8.5,
    },
    "MELANOGENESIS_SURVIVAL_RECEPTORS": {
        "MC1R": 9.5,
        "MITF": 9.5,
        "KIT": 9.0,
        "WNT1": 8.5,
        "SOX10": 8.5,
    },
}

# ── Drug Safety Risk Tiers ──────────────────────────────────────────────
DRUG_SAFETY_RISK = {
    "high_risk": [
        "Long-term continuous oral corticosteroid therapy (Systemic adrenal suppression)"
    ],
    "moderate_risk": [
        "Prolonged high-potency topical corticosteroids (Cutaneous atrophy, Striae)",
        "High-dose Narrowband UVB (Erythema, Phototoxicity)",
    ],
    "low_risk": ["Topical Ruxolitinib", "Topical Tacrolimus", "Topical Pimecrolimus"],
}
DISEASE_SPECIFIC_RISK = DRUG_SAFETY_RISK
DRUG_INDUCED_LUPUS_RISK = DRUG_SAFETY_RISK

SCREENING_PROFILE = {
    "strategy_id": "vitiligo-screening-v1",
    "reference_drug_ids": ["ruxolitinib_topical", "tacrolimus_topical", "clobetasol_propionate"],
    "weights": {
        "binding_estimate": 0.30,
        "druglikeness": 0.20,
        "target_complementarity": 0.25,
        "similarity_score": 0.15,
        "novelty_score": 0.10,
    },
    "source": "curated_vitiligo_knowledge_graph",
    "curated_inputs": ["pathways", "drugs", "screening_strategy"],
    "inferred_inputs": ["mechanism_keyword_matching", "property_based_binding_estimate"],
    "limitations": [
        "Property scores are heuristic prioritization signals, not experimental binding affinity or efficacy."
    ],
}
