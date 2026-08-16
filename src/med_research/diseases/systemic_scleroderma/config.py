"""Systemic Sclerosis (Scleroderma) configuration.

Disease-specific parameters used by research pipeline modules.
"""

PIPELINE_LABEL = "Systemic Sclerosis (Scleroderma)"
DEFAULT_SAMPLE_SIZE = 50

# ── Symptoms (used by adverse_events/profiler.py) ────────────────────────
SYMPTOMS = [
    "raynaud's phenomenon with severe cold-induced vasospasm",
    "sclerodactyly (tightening and thickening of finger skin)",
    "diffuse or limited cutaneous skin induration",
    "painful digital ischemic ulcers and pitting scars",
    "subcutaneous calcinosis cutis",
    "cutaneous telangiectasias (face, hands, lips)",
    "esophageal dysmotility, dysphagia, and reflux",
    "interstitial lung disease (SSc-ILD) with progressive dyspnea",
    "pulmonary arterial hypertension (PAH)",
    "scleroderma renal crisis with malignant hypertension",
    "tendon friction rubs on wrists and ankles",
    "generalized arthralgia and joint contractures"
]

# ── Literature Mining ────────────────────────────────────────────────────
PUBMED_QUERIES = [
    "(systemic sclerosis[Title/Abstract] OR scleroderma[Title/Abstract]) AND (treatment[Title/Abstract] OR therapeutics[Title/Abstract])",
    "(systemic sclerosis[Title/Abstract]) AND (nintedanib[Title/Abstract] OR tocilizumab[Title/Abstract] OR mycophenolate[Title/Abstract] OR rituximab[Title/Abstract])",
    "(systemic sclerosis[Title/Abstract]) AND (interstitial lung disease[Title/Abstract] OR pulmonary hypertension[Title/Abstract] OR fibrosis[Title/Abstract])",
    "(systemic sclerosis[Title/Abstract]) AND (clinical trial[Title/Abstract])"
]

# ── Clinical trials / GWAS search terms ────────────────────────────────
TRIAL_QUERY = "Systemic Sclerosis OR Scleroderma OR SSc-ILD OR Diffuse Cutaneous Scleroderma"
GWAS_SEARCH_TERMS = [
    "systemic sclerosis",
    "interstitial lung disease",
    "pulmonary fibrosis",
    "autoimmune disease",
    "Raynaud phenomenon"
]

# ── CAR-T & Target Scoring Tables ───────────────────────────────────────
CAR_T_SCORES = {
    "PRO_FIBROTIC_GROWTH_FACTORS": {
        "TGFB1": 10.0,
        "TGFBR1": 9.5,
        "TGFBR2": 9.5,
        "PDGFRB": 9.5,
        "FGFR1": 9.0,
        "CTGF": 9.0
    },
    "IMMUNE_CYTOKINE_DRIVERS": {
        "IL6R": 10.0,
        "IL6": 9.5,
        "CD20": 9.5,
        "MS4A1": 9.5,
        "IL4": 8.5,
        "IL13": 8.5,
        "JAK1": 9.0
    },
    "ENDOTHELIAL_VASCULOPATHY": {
        "EDNRA": 9.5,
        "EDNRB": 9.0,
        "PDE5A": 9.5,
        "PTGIR": 9.0,
        "VEGFA": 8.5
    }
}

# ── Drug Safety Risk Tiers ──────────────────────────────────────────────
DRUG_SAFETY_RISK = {
    "high_risk": [
        "High-dose Corticosteroids (Triggers life-threatening Scleroderma Renal Crisis)",
        "Cyclophosphamide (Myelosuppression, Hemorrhagic cystitis)"
    ],
    "moderate_risk": [
        "Nintedanib (Diarrhea, Liver enzyme elevations)",
        "Mycophenolate Mofetil (Cytopenias, Teratogenicity)"
    ],
    "low_risk": [
        "Tocilizumab",
        "Phosphodiesterase-5 Inhibitors (Sildenafil)",
        "Endothelin Receptor Antagonists"
    ]
}
DISEASE_SPECIFIC_RISK = DRUG_SAFETY_RISK
DRUG_INDUCED_LUPUS_RISK = DRUG_SAFETY_RISK

SCREENING_PROFILE = {
    "strategy_id": "systemic_scleroderma-screening-v1",
    "reference_drug_ids": [
        "nintedanib",
        "tocilizumab",
        "mycophenolate_mofetil",
        "bosentan"
],
    "weights": {
        "binding_estimate": 0.30,
        "druglikeness": 0.20,
        "target_complementarity": 0.25,
        "similarity_score": 0.15,
        "novelty_score": 0.10,
    },
    "source": "curated_systemic_scleroderma_knowledge_graph",
    "curated_inputs": ["pathways", "drugs", "screening_strategy"],
    "inferred_inputs": ["mechanism_keyword_matching", "property_based_binding_estimate"],
    "limitations": [
        "Property scores are heuristic prioritization signals, not experimental binding affinity or efficacy."
    ],
}
