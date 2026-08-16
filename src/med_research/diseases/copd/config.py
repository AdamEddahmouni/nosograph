"""Chronic Obstructive Pulmonary Disease (COPD) configuration.

Disease-specific parameters used by research pipeline modules.
"""

PIPELINE_LABEL = "Chronic Obstructive Pulmonary Disease"
DEFAULT_SAMPLE_SIZE = 50

# ── Symptoms (used by adverse_events/profiler.py) ────────────────────────
SYMPTOMS = [
    "chronic dyspnea",
    "progressive shortness of breath",
    "exertional dyspnea",
    "chronic cough",
    "sputum production",
    "mucopurulent sputum",
    "wheezing",
    "chest tightness",
    "tachypnea",
    "prolonged expiration",
    "pursed-lip breathing",
    "use of accessory muscles for breathing",
    "barrel chest deformity",
    "acute exacerbation of COPD",
    "hypoxemia",
    "cyanosis",
    "hypercapnia",
    "morning headache",
    "fatigue",
    "exercise intolerance",
    "weight loss",
    "muscle wasting",
    "peripheral edema",
    "cor pulmonale",
]

# ── Literature Mining ────────────────────────────────────────────────────
PUBMED_QUERIES = [
    "(COPD[Title/Abstract] OR chronic obstructive pulmonary disease[Title/Abstract] OR emphysema[Title/Abstract]) AND (treatment[Title/Abstract] OR bronchodilator[Title/Abstract])",
    "(COPD[Title/Abstract]) AND (alpha-1 antitrypsin[Title/Abstract] OR SERPINA1[Title/Abstract])",
    "(COPD[Title/Abstract]) AND (clinical trial[Title/Abstract])",
    "(COPD[Title/Abstract]) AND (exacerbation[Title/Abstract] OR biomarker[Title/Abstract])",
    "(COPD[Title/Abstract]) AND (airway remodeling[Title/Abstract] OR inflammation[Title/Abstract])",
]

# ── Clinical trials / GWAS search terms ────────────────────────────────
TRIAL_QUERY = "COPD OR Chronic Obstructive Pulmonary Disease OR Emphysema"
GWAS_SEARCH_TERMS = [
    "chronic obstructive pulmonary disease",
    "COPD",
    "lung function",
    "FEV1/FVC ratio",
]

# ── CAR-T & Target Scoring Tables ───────────────────────────────────────
CAR_T_SCORES = {
    "BRONCHODILATION_TARGETS": {
        "CHRM3": 10.0,
        "ADRB2": 10.0,
        "PDE4B": 9.5,
        "PDE4D": 9.0,
        "PDE3A": 8.0,
        "ADRA1A": 7.0,
    },
    "PROTEASE_ANTIPROTEASE_BALANCE": {
        "SERPINA1": 10.0,
        "MMP9": 9.5,
        "MMP12": 9.5,
        "ELANE": 9.0,
        "MMP2": 8.0,
        "TIMP1": 8.0,
        "CTSG": 7.5,
    },
    "AIRWAY_INFLAMMATION_REMODELING": {
        "TGFB1": 9.5,
        "IL4R": 9.5,
        "IL5": 9.0,
        "IL13": 9.0,
        "TNF": 8.5,
        "IL6": 8.5,
        "IL1B": 8.0,
        "CXCL8": 8.0,
        "ADAM33": 7.5,
        "SMAD3": 7.0,
    },
    "OXIDATIVE_STRESS_EPITHELIUM": {
        "NFE2L2": 9.5,
        "HMOX1": 9.0,
        "SOD2": 8.5,
        "CAT": 8.0,
        "GPX1": 8.0,
        "SIRT1": 8.5,
    },
    "TARGET_DRUGGABILITY": {
        "CHRM3": 10.0,
        "ADRB2": 10.0,
        "PDE4B": 9.5,
        "IL4R": 9.5,
        "SERPINA1": 9.0,
        "MMP12": 8.5,
        "NFE2L2": 8.0,
    },
}

# ── Drug safety & disease-specific risk ──────────────────────────────────
DRUG_SAFETY_RISK = {
    "high_risk": [
        "non_selective_beta_blockers",
        "propranolol",
        "carvedilol_high_dose",
        "sedatives",
        "benzodiazepines",
        "diazepam",
        "opioids_high_dose",
        "morphine",
        "respiratory_depressants",
    ],
    "moderate_risk": [
        "inhaled_corticosteroids_high_dose",
        "cardioselective_beta_blockers",
        "atenolol",
        "metoprolol",
        "theophylline",
        "diuretics",
    ],
    "low_risk": [
        "tiotropium",
        "ipratropium",
        "salbutamol",
        "albuterol",
        "formoterol",
        "vilanterol",
        "azithromycin_prophylaxis",
        "acetylcysteine",
    ],
}
DISEASE_SPECIFIC_RISK = DRUG_SAFETY_RISK
DRUG_INDUCED_LUPUS_RISK = DRUG_SAFETY_RISK

SCREENING_PROFILE = {
    "strategy_id": "copd-screening-v1",
    "pathway_keywords": [
        "airway smooth muscle",
        "bronchodilation",
        "protease",
        "elastase",
        "cholinergic",
        "beta adrenergic",
        "pde4",
        "neutrophilic inflammation",
    ],
    "mechanism_keywords": [
        "muscarinic",
        "beta-2 agonist",
        "pde4",
        "corticosteroid",
        "il-4",
        "il-13",
        "metalloproteinase",
    ],
    "reference_drug_ids": [
        "tiotropium",
        "roflumilast",
        "indacaterol",
        "fluticasone_salmeterol",
        "dupilumab",
    ],
    "weights": {
        "binding_estimate": 0.30,
        "druglikeness": 0.20,
        "target_complementarity": 0.25,
        "similarity_score": 0.15,
        "novelty_score": 0.10,
    },
    "source": "curated_copd_knowledge_graph",
    "curated_inputs": ["pathways", "drugs", "screening_strategy"],
    "inferred_inputs": ["mechanism_keyword_matching", "property_based_binding_estimate"],
    "limitations": [
        "Property scores are heuristic prioritization signals, not experimental binding affinity or efficacy."
    ],
}
