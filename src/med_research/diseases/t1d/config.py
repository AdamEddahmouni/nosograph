"""Autoimmune disease configuration — T1D (Type 1 Diabetes (T1D)).

Disease-specific parameters used by the research pipeline modules.
CAR_T_SCORES and DRUG_INDUCED_LUPUS_RISK are derived from the
disease knowledge graph (genes.json) using a documented rubric; see
scripts/populate_disease_configs.py for the scoring rules.
"""

PIPELINE_LABEL = "Type 1 Diabetes (T1D)"
DEFAULT_SAMPLE_SIZE = 50

SYMPTOMS = [
    "hyperglycemia", "polyuria", "polydipsia", "polyphagia",
    "weight loss", "fatigue", "blurred vision",
    "diabetic ketoacidosis", "nausea", "vomiting",
    "abdominal pain", "ketones in urine",
    "hypoglycemia unawareness", "neuropathy",
    "nephropathy", "retinopathy", "cardiovascular complications",
    "recurrent infections", "slow wound healing",
]

PUBMED_QUERIES = [
    "(type 1 diabetes[Title/Abstract] OR type 1 diabetes mellitus[Title/Abstract]) AND (treatment[Title/Abstract])",
    "(type 1 diabetes[Title/Abstract]) AND (genetics[Title/Abstract] OR genomics[Title/Abstract])",
    "(type 1 diabetes[Title/Abstract]) AND (clinical trial[Title/Abstract])",
    "(type 1 diabetes[Title/Abstract]) AND (biomarker[Title/Abstract])",
]

CAR_T_SCORES = {
    "Anti-inflammatory / Immune Regulation": {
        "IL10": 4.0,
    },
    "Antigen Processing / Immune Tolerance": {
        "CTSH": 4.0,
    },
    "Autophagy / Antigen Presentation": {
        "CLEC16A": 6.5,
    },
    "Growth Factor Signaling / β Cell Survival": {
        "ERBB3": 4.0,
    },
    "Immune Tolerance / B-T Cell Regulation": {
        "BACH2": 4.0,
    },
    "Innate Immunity / Complement": {
        "C1QTNF6": 4.5,
    },
    "JAK-STAT Signaling": {
        "JAK1": 6.0,
        "SH2B3": 6.0,
        "TYK2": 6.0,
    },
    "JAK-STAT Signaling / β Cell Apoptosis": {
        "PTPN2": 6.0,
    },
    "MHC / Antigen Presentation": {
        "HLA-DQA1": 6.5,
        "HLA-DQB1": 6.5,
    },
    "Pro-inflammatory Cytokine / β Cell Cytotoxicity": {
        "TNF": 4.0,
    },
    "T Cell Costimulation": {
        "CTLA4": 7.0,
    },
    "T Cell Signaling": {
        "PTPN22": 6.0,
        "UBASH3A": 6.0,
    },
    "Treg / IL-2 Pathway": {
        "IL2": 8.0,
        "IL2RA": 8.0,
    },
    "Treg / Immune Regulation": {
        "FOXP3": 8.0,
    },
    "Type I Interferon / Viral Sensing": {
        "IFIH1": 5.0,
    },
    "β Cell Autoantigen": {
        "GAD2": 8.5,
        "PTPRN": 8.5,
    },
    "β Cell Autoantigen / Immune Tolerance": {
        "INS": 8.5,
    },
    "β Cell Development / Function": {
        "GLIS3": 4.0,
    },
}

DRUG_SAFETY_RISK = {
    "high_risk": [
        "interferon-alpha",
        "interferon-beta",
        "checkpoint inhibitors (anti-PD-1, anti-CTLA-4)",
    ],
    "moderate_risk": [
        "pentamidine",
        "diazoxide",
        "thiazide diuretics",
        "glucocorticoids",
    ],
    "low_risk": [
        "metformin",
        "insulin",
        "ACE inhibitors",
    ],
}

# ── Clinical trials / GWAS search terms ────────────────────────────────
TRIAL_QUERY = "type 1 diabetes OR T1D"
GWAS_SEARCH_TERMS = [
    "type 1 diabetes",
    "T1D",
]

DISEASE_SPECIFIC_RISK = DRUG_SAFETY_RISK
DRUG_INDUCED_LUPUS_RISK = DRUG_SAFETY_RISK

SCREENING_PROFILE = {
    "strategy_id": "t1d-screening-v1",
    "pathway_keywords": ["t cell", "insulitis", "beta cell", "il-2", "treg", "interferon", "antigen presentation", "costimulation"],
    "mechanism_keywords": ["cd3", "t cell", "treg", "il-2", "beta cell", "insulin", "ctla4", "cd80", "cd86", "ifn"],
    "reference_drug_ids": ["teplizumab", "abatacept", "rituximab", "verapamil", "low_dose_il2", "gad_alum"],
    "weights": {"binding_estimate": 0.20, "druglikeness": 0.10, "target_complementarity": 0.40, "similarity_score": 0.15, "novelty_score": 0.15},
    "source": "curated_t1d_knowledge_graph",
    "curated_inputs": ["pathways", "drugs", "screening_strategy"],
    "inferred_inputs": ["mechanism_keyword_matching", "property_based_binding_estimate"],
    "limitations": ["Property scores are heuristic prioritization signals and do not establish type 1 diabetes efficacy or preservation of beta-cell function."],
}
