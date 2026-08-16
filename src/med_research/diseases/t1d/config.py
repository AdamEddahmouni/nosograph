"""Type 1 Diabetes Mellitus configuration.

Disease-specific parameters used by research pipeline modules.
"""

PIPELINE_LABEL = "Type 1 Diabetes Mellitus"
DEFAULT_SAMPLE_SIZE = 50

# ── Symptoms (used by adverse_events/profiler.py) ────────────────────────
SYMPTOMS = [
    "polyuria (excessive urination)",
    "polydipsia (excessive thirst)",
    "polyphagia (constant extreme hunger)",
    "rapid unexplained weight loss",
    "diabetic ketoacidosis (DKA)",
    "kussmaul deep rapid breathing",
    "fruity acetone breath odor",
    "extreme fatigue and lethargy",
    "blurred vision",
    "nausea and abdominal pain at presentation",
    "hypoglycemic episodes during intensive insulin therapy",
    "impaired hypoglycemia awareness",
    "microalbuminuria and diabetic retinopathy long-term"
]

# ── Literature Mining ────────────────────────────────────────────────────
PUBMED_QUERIES = [
    "(type 1 diabetes[Title/Abstract] OR T1D[Title/Abstract] OR autoimmune diabetes[Title/Abstract]) AND (treatment[Title/Abstract] OR therapeutics[Title/Abstract])",
    "(type 1 diabetes[Title/Abstract]) AND (insulin[Title/Abstract] OR teplizumab[Title/Abstract] OR immunotherapy[Title/Abstract])",
    "(type 1 diabetes[Title/Abstract]) AND (beta cell preservation[Title/Abstract] OR islet autoimmunity[Title/Abstract])",
    "(type 1 diabetes[Title/Abstract]) AND (clinical trial[Title/Abstract])"
]

# ── Clinical trials / GWAS search terms ────────────────────────────────
TRIAL_QUERY = "Type 1 Diabetes OR Type 1 Diabetes Mellitus OR Autoimmune Diabetes OR T1D"
GWAS_SEARCH_TERMS = [
    "type 1 diabetes",
    "fasting glucose",
    "HbA1c",
    "autoimmune diseases"
]

# ── CAR-T & Target Scoring Tables ───────────────────────────────────────
CAR_T_SCORES = {
    "AUTOIMMUNE_T_CELL_MEDIATORS": {
        "CD3E": 10.0,
        "CD3D": 9.5,
        "CD4": 9.0,
        "CD8A": 9.5,
        "PTPN22": 10.0,
        "CTLA4": 9.5,
        "IL2RA": 9.5
    },
    "BETA_CELL_AUTOANTIGENS": {
        "INS": 10.0,
        "GAD2": 9.5,
        "IA-2": 9.0,
        "PTPRN": 9.0,
        "SLC30A8": 9.5,
        "ICA1": 8.5
    },
    "INFLAMMATORY_CYTOKINE_APOPTOSIS": {
        "IFNG": 9.0,
        "TNF": 8.5,
        "IL1B": 8.5,
        "FAS": 8.0,
        "CASP3": 8.0,
        "JAK1": 8.5
    }
}

# ── Drug Safety Risk Tiers ──────────────────────────────────────────────
DRUG_SAFETY_RISK = {
    "high_risk": [
        "Insulin overdose (Severe / Fatal Hypoglycemia)",
        "Insulin omission (Life-threatening Diabetic Ketoacidosis)"
    ],
    "moderate_risk": [
        "Teplizumab (Cytokine release syndrome, Transient lymphopenia)"
    ],
    "low_risk": [
        "Nasal Glucagon Rescue",
        "Continuous Glucose Monitor Guidance"
    ]
}
DISEASE_SPECIFIC_RISK = DRUG_SAFETY_RISK
DRUG_INDUCED_LUPUS_RISK = DRUG_SAFETY_RISK

SCREENING_PROFILE = {
    "strategy_id": "t1d-screening-v1",
    "reference_drug_ids": [
        "teplizumab",
        "insulin_glargine",
        "insulin_aspart",
        "pramlintide"
],
    "weights": {
        "binding_estimate": 0.30,
        "druglikeness": 0.20,
        "target_complementarity": 0.25,
        "similarity_score": 0.15,
        "novelty_score": 0.10,
    },
    "source": "curated_t1d_knowledge_graph",
    "curated_inputs": ["pathways", "drugs", "screening_strategy"],
    "inferred_inputs": ["mechanism_keyword_matching", "property_based_binding_estimate"],
    "limitations": [
        "Property scores are heuristic prioritization signals, not experimental binding affinity or efficacy."
    ],
}
