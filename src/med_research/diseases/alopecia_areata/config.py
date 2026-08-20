"""Alopecia Areata configuration.

Disease-specific parameters used by research pipeline modules.
"""

PIPELINE_LABEL = "Alopecia Areata"
DEFAULT_SAMPLE_SIZE = 50

# ── Symptoms (used by adverse_events/profiler.py) ────────────────────────
SYMPTOMS = [
    "well-demarcated patchy non-scarring scalp hair loss",
    "exclamation point hairs at active patch periphery",
    "alopecia totalis (100% loss of scalp hair)",
    "alopecia universalis (complete loss of all scalp and body hair)",
    "nail dystrophy, pitting, and trachyonychia",
    "loss of eyelashes and eyebrows",
    "spontaneous hair shedding and partial regrowth cycles",
    "pruritus or burning dysesthesia of scalp prior to shedding",
    "severe psychological and emotional distress",
]

# ── Literature Mining ────────────────────────────────────────────────────
PUBMED_QUERIES = [
    "(alopecia areata[Title/Abstract] OR alopecia totalis[Title/Abstract] OR alopecia universalis[Title/Abstract]) AND (treatment[Title/Abstract] OR therapeutics[Title/Abstract])",
    "(alopecia areata[Title/Abstract]) AND (baricitinib[Title/Abstract] OR ritlecitinib[Title/Abstract] OR JAK inhibitor[Title/Abstract])",
    "(alopecia areata[Title/Abstract]) AND (immune privilege[Title/Abstract] OR NKG2D[Title/Abstract] OR IFN-gamma[Title/Abstract])",
    "(alopecia areata[Title/Abstract]) AND (clinical trial[Title/Abstract])",
]

# ── Clinical trials / GWAS search terms ────────────────────────────────
TRIAL_QUERY = "Alopecia Areata OR Alopecia Totalis OR Alopecia Universalis OR Severe Alopecia"
GWAS_SEARCH_TERMS = ["alopecia areata", "vitiligo", "autoimmune disease", "rheumatoid arthritis"]

# ── CAR-T & Target Scoring Tables ───────────────────────────────────────
CAR_T_SCORES = {
    "JAK_STAT_IFN_SIGNALING": {
        "JAK1": 10.0,
        "JAK2": 9.5,
        "JAK3": 10.0,
        "TYK2": 9.0,
        "STAT1": 9.5,
        "IFNG": 10.0,
        "IL15": 9.5,
    },
    "NKG2D_CYTOTOXIC_T_CELLS": {
        "KLRK1": 10.0,
        "MICA": 9.0,
        "MICB": 9.0,
        "ULBP3": 9.0,
        "CD8A": 9.5,
        "PRF1": 8.5,
    },
    "FOLLICULAR_IMMUNE_PRIVILEGE": {
        "TGFB1": 8.5,
        "IL10": 8.0,
        "HLA-A": 9.0,
        "HLA-B": 9.0,
        "FASLG": 8.0,
    },
}

# ── Drug Safety Risk Tiers ──────────────────────────────────────────────
DRUG_SAFETY_RISK = {
    "high_risk": [
        "Prolonged systemic high-dose corticosteroids (Adrenal suppression, Osteoporosis, Cushingoid syndrome)"
    ],
    "moderate_risk": [
        "Oral JAK Inhibitors (Serious infections, Herpes zoster, Thrombosis black box warning)",
        "Oral Cyclosporine (Renal toxicity, Hypertension)",
    ],
    "low_risk": [
        "Intralesional Triamcinolone Acetonide",
        "Topical Clobetasol Propionate",
        "Topical Minoxidil",
    ],
}
DISEASE_SPECIFIC_RISK = DRUG_SAFETY_RISK
DRUG_INDUCED_LUPUS_RISK = DRUG_SAFETY_RISK

SCREENING_PROFILE = {
    "strategy_id": "alopecia_areata-screening-v1",
    "reference_drug_ids": ["baricitinib", "ritlecitinib", "triamcinolone_acetonide"],
    "weights": {
        "binding_estimate": 0.30,
        "druglikeness": 0.20,
        "target_complementarity": 0.25,
        "similarity_score": 0.15,
        "novelty_score": 0.10,
    },
    "source": "curated_alopecia_areata_knowledge_graph",
    "curated_inputs": ["pathways", "drugs", "screening_strategy"],
    "inferred_inputs": ["mechanism_keyword_matching", "property_based_binding_estimate"],
    "limitations": [
        "Property scores are heuristic prioritization signals, not experimental binding affinity or efficacy."
    ],
}
