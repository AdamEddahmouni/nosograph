"""Type 2 Diabetes Mellitus (T2D) configuration.

Disease-specific parameters used by research pipeline modules.
"""

PIPELINE_LABEL = "Type 2 Diabetes Mellitus"
DEFAULT_SAMPLE_SIZE = 50

# ── Symptoms (used by adverse_events/profiler.py) ────────────────────────
SYMPTOMS = [
    "polyuria",
    "excessive urination",
    "nocturia",
    "polydipsia",
    "excessive thirst",
    "polyphagia",
    "increased hunger",
    "unexplained weight loss",
    "fatigue",
    "malaise",
    "blurred vision",
    "slow-healing sores or cuts",
    "frequent infections",
    "recurrent candidiasis",
    "peripheral neuropathy",
    "numbness and tingling in hands or feet",
    "acanthosis nigricans",
    "diabetic retinopathy",
    "diabetic nephropathy",
    "microalbuminuria",
    "erectile dysfunction",
    "diabetic ketoacidosis",
    "hyperosmolar hyperglycemic state",
]

# ── Literature Mining ────────────────────────────────────────────────────
PUBMED_QUERIES = [
    "(type 2 diabetes[Title/Abstract] OR T2D[Title/Abstract] OR non-insulin-dependent diabetes[Title/Abstract]) AND (treatment[Title/Abstract] OR therapeutics[Title/Abstract])",
    "(type 2 diabetes[Title/Abstract]) AND (GLP-1[Title/Abstract] OR SGLT2[Title/Abstract] OR metformin[Title/Abstract])",
    "(type 2 diabetes[Title/Abstract]) AND (insulin resistance[Title/Abstract] OR beta-cell dysfunction[Title/Abstract])",
    "(type 2 diabetes[Title/Abstract]) AND (clinical trial[Title/Abstract])",
    "(type 2 diabetes[Title/Abstract]) AND (cardiovascular outcomes[Title/Abstract] OR diabetic kidney disease[Title/Abstract])",
]

# ── Clinical trials / GWAS search terms ────────────────────────────────
TRIAL_QUERY = "Type 2 Diabetes OR Type 2 Diabetes Mellitus OR T2D"
GWAS_SEARCH_TERMS = [
    "type 2 diabetes",
    "fasting glucose",
    "fasting insulin",
    "HbA1c",
    "glycated hemoglobin",
]

# ── CAR-T & Target Scoring Tables ───────────────────────────────────────
CAR_T_SCORES = {
    "INCRETIN_HORMONAL_AXIS": {
        "GLP1R": 10.0,
        "GIPR": 9.5,
        "DPP4": 9.5,
        "GCGR": 9.0,
        "FFAR1": 8.0,
        "GPR119": 7.5,
    },
    "INSULIN_SENSITIVITY_METABOLISM": {
        "PRKAA1": 10.0,
        "PRKAA2": 9.5,
        "PPARG": 9.5,
        "INSR": 9.0,
        "IRS1": 8.5,
        "IRS2": 8.5,
        "SLC2A4": 9.0,
        "AKT2": 8.5,
        "PIK3CA": 8.0,
    },
    "RENAL_GLUCOSE_HANDLING": {
        "SLC5A2": 10.0,
        "SLC5A1": 8.5,
        "SLC2A2": 8.0,
    },
    "BETA_CELL_SECRETION_GENETICS": {
        "KCNJ11": 9.5,
        "ABCC8": 9.5,
        "TCF7L2": 9.5,
        "SLC30A8": 9.0,
        "HNF1A": 8.5,
        "HNF4A": 8.5,
        "GCK": 9.0,
        "INS": 8.5,
    },
    "TARGET_DRUGGABILITY": {
        "GLP1R": 10.0,
        "SLC5A2": 10.0,
        "PRKAA1": 9.5,
        "DPP4": 9.5,
        "GIPR": 9.0,
        "PPARG": 9.0,
        "KCNJ11": 8.5,
    },
}

# ── Drug safety & disease-specific risk ──────────────────────────────────
DRUG_SAFETY_RISK = {
    "high_risk": [
        "corticosteroids_systemic",
        "prednisone",
        "dexamethasone",
        "atypical_antipsychotics",
        "olanzapine",
        "clozapine",
        "thiazide_diuretics_high_dose",
        "niacin_high_dose",
        "protease_inhibitors",
    ],
    "moderate_risk": [
        "beta_blockers_non_selective",
        "statins_high_intensity",
        "calcineurin_inhibitors",
        "tacrolimus",
        "cyclosporine",
        "fluoroquinolones",
    ],
    "low_risk": [
        "metformin",
        "semaglutide",
        "empagliflozin",
        "dapagliflozin",
        "tirzepatide",
        "sitagliptin",
        "linagliptin",
        "pioglitazone",
        "glimepiride",
    ],
}
DISEASE_SPECIFIC_RISK = DRUG_SAFETY_RISK
DRUG_INDUCED_LUPUS_RISK = DRUG_SAFETY_RISK

SCREENING_PROFILE = {
    "strategy_id": "t2d-screening-v1",
    "pathway_keywords": [
        "incretin",
        "glp-1",
        "sglt2",
        "ampk",
        "insulin sensitivity",
        "beta cell",
        "glucose transport",
        "gluconeogenesis",
    ],
    "mechanism_keywords": [
        "glp-1 agonist",
        "sglt2 inhibitor",
        "ampk activator",
        "dpp-4 inhibitor",
        "pparg agonist",
        "sulfonylurea",
    ],
    "reference_drug_ids": [
        "metformin",
        "semaglutide",
        "empagliflozin",
        "tirzepatide",
        "sitagliptin",
    ],
    "weights": {
        "binding_estimate": 0.30,
        "druglikeness": 0.20,
        "target_complementarity": 0.25,
        "similarity_score": 0.15,
        "novelty_score": 0.10,
    },
    "source": "curated_t2d_knowledge_graph",
    "curated_inputs": ["pathways", "drugs", "screening_strategy"],
    "inferred_inputs": ["mechanism_keyword_matching", "property_based_binding_estimate"],
    "limitations": [
        "Property scores are heuristic prioritization signals, not experimental binding affinity or efficacy."
    ],
}
