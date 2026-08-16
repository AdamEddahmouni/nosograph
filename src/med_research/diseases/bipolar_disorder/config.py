"""Bipolar Disorder configuration.

Disease-specific parameters used by research pipeline modules.
"""

PIPELINE_LABEL = "Bipolar Disorder"
DEFAULT_SAMPLE_SIZE = 50

# ── Symptoms (used by adverse_events/profiler.py) ────────────────────────
SYMPTOMS = [
    "elevated or irritable mood",
    "grandiosity or inflated self-esteem",
    "decreased need for sleep",
    "pressured speech",
    "flight of ideas or racing thoughts",
    "distractibility",
    "psychomotor agitation",
    "impulsive or high-risk behavior",
    "depressive episodes",
    "severe anhedonia",
    "psychomotor slowing",
    "mood lability",
    "rapid cycling"
]

# ── Literature Mining ────────────────────────────────────────────────────
PUBMED_QUERIES = [
    "(bipolar disorder[Title/Abstract] OR bipolar depression[Title/Abstract] OR mania[Title/Abstract]) AND (treatment[Title/Abstract] OR therapeutics[Title/Abstract])",
    "(bipolar disorder[Title/Abstract]) AND (lithium[Title/Abstract] OR valproate[Title/Abstract] OR lamotrigine[Title/Abstract] OR quetiapine[Title/Abstract])",
    "(bipolar disorder[Title/Abstract]) AND (mood stabilizer[Title/Abstract] OR circadian rhythm[Title/Abstract])",
    "(bipolar disorder[Title/Abstract]) AND (clinical trial[Title/Abstract])"
]

# ── Clinical trials / GWAS search terms ────────────────────────────────
TRIAL_QUERY = "Bipolar Disorder OR Bipolar I Disorder OR Bipolar II Disorder OR Bipolar Depression"
GWAS_SEARCH_TERMS = [
    "bipolar disorder",
    "major depressive disorder",
    "schizophrenia",
    "sleep duration",
    "chronotype"
]

# ── CAR-T & Target Scoring Tables ───────────────────────────────────────
CAR_T_SCORES = {
    "INOSITOL_GSK3_SIGNALING": {
        "GSK3B": 10.0,
        "GSK3A": 9.0,
        "IMPA1": 9.5,
        "INPP1": 8.5,
        "AKT1": 8.5
    },
    "ION_CHANNEL_NEURONAL_EXCITABILITY": {
        "CACNA1C": 10.0,
        "CACNB2": 9.0,
        "SCN1A": 9.5,
        "SCN2A": 9.0,
        "KCNQ2": 8.0
    },
    "MONOAMINE_CIRCADIAN_REGULATION": {
        "SLC6A4": 9.0,
        "DRD2": 9.0,
        "CLOCK": 8.5,
        "ARNTL": 8.0,
        "BDNF": 9.0
    }
}

# ── Drug Safety Risk Tiers ──────────────────────────────────────────────
DRUG_SAFETY_RISK = {
    "high_risk": [
        "Lithium Toxicity (Narrow therapeutic index, Nephrogenic DI, Thyroid dysfunction)",
        "Valproate (Hepatotoxicity, Teratogenicity, Pancreatitis)"
    ],
    "moderate_risk": [
        "Lamotrigine (Stevens-Johnson syndrome rash)",
        "Atypical Antipsychotics (Metabolic syndrome)"
    ],
    "low_risk": [
        "Lurasidone",
        "Cariprazine"
    ]
}
DISEASE_SPECIFIC_RISK = DRUG_SAFETY_RISK
DRUG_INDUCED_LUPUS_RISK = DRUG_SAFETY_RISK

SCREENING_PROFILE = {
    "strategy_id": "bipolar_disorder-screening-v1",
    "reference_drug_ids": [
        "lithium",
        "valproate",
        "lamotrigine",
        "quetiapine"
],
    "weights": {
        "binding_estimate": 0.30,
        "druglikeness": 0.20,
        "target_complementarity": 0.25,
        "similarity_score": 0.15,
        "novelty_score": 0.10,
    },
    "source": "curated_bipolar_disorder_knowledge_graph",
    "curated_inputs": ["pathways", "drugs", "screening_strategy"],
    "inferred_inputs": ["mechanism_keyword_matching", "property_based_binding_estimate"],
    "limitations": [
        "Property scores are heuristic prioritization signals, not experimental binding affinity or efficacy."
    ],
}
