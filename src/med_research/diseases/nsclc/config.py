"""Non-Small Cell Lung Cancer (NSCLC) disease configuration.

Curated immuno-oncology parameters for NSCLC.
"""

PIPELINE_LABEL = "Non-Small Cell Lung Cancer"
DEFAULT_SAMPLE_SIZE = 50

# ── Symptoms (used by adverse_events/profiler.py) ────────────────────────
SYMPTOMS = [
    "persistent worsening cough",
    "hemoptysis (coughing up blood or rust-colored sputum)",
    "chest pain aggravated by deep breathing or coughing",
    "dyspnea and shortness of breath",
    "unexplained hoarseness",
    "unintentional weight loss and anorexia",
    "generalized fatigue and weakness",
    "recurrent bronchitis or pneumonia",
    "wheezing and stridor",
    "pleural effusion",
    "superior vena cava syndrome",
    "bone pain from metastatic spread",
    "neurological deficits from CNS metastasis",
    "pancoast tumor symptoms (horner syndrome, shoulder pain)",
    "clubbing of the fingers",
]

# ── Literature Mining ────────────────────────────────────────────────────
PUBMED_QUERIES = [
    "(Non-Small Cell Lung Cancer[Title/Abstract] OR NSCLC[Title/Abstract]) AND (EGFR[Title/Abstract] OR KRAS[Title/Abstract] OR ALK[Title/Abstract])",
    "(Non-Small Cell Lung Cancer[Title/Abstract] OR NSCLC[Title/Abstract]) AND (osimertinib[Title/Abstract] OR sotorasib[Title/Abstract] OR pembrolizumab[Title/Abstract])",
    "(Non-Small Cell Lung Cancer[Title/Abstract]) AND (clinical trial[Title/Abstract])",
    "(Non-Small Cell Lung Cancer[Title/Abstract]) AND (resistance mutation[Title/Abstract] OR T790M[Title/Abstract])",
]

# ── Clinical trials / GWAS search terms ────────────────────────────────
TRIAL_QUERY = "Non-Small Cell Lung Cancer OR NSCLC OR Lung Adenocarcinoma"
GWAS_SEARCH_TERMS = [
    "lung cancer",
    "non-small cell lung carcinoma",
    "lung adenocarcinoma",
    "smoking behavior",
]

# ── CAR-T & Target Scoring Tables ───────────────────────────────────────
CAR_T_SCORES = {
    "DRIVER_ONCOGENIC_KINASES": {
        "EGFR": 10.0,
        "ALK": 9.5,
        "KRAS": 10.0,
        "ROS1": 9.0,
        "RET": 9.0,
        "MET": 9.0,
        "BRAF": 8.5,
        "ERBB2": 8.5,
    },
    "CHECKPOINT_IMMUNE_EVASION": {
        "CD274": 10.0,
        "PDCD1": 9.5,
        "CTLA4": 9.0,
        "TIGIT": 8.5,
        "LAG3": 8.5,
    },
    "TUMOR_ANTIGENS_AND_EPITHELIAL_TARGETS": {
        "MSLN": 9.0,
        "EPCAM": 8.5,
        "MUC1": 9.0,
        "TACSTD2": 9.5,
        "CEACAM5": 9.0,
    },
    "ANGIOGENIC_VASCULAR_MEDIATORS": {
        "VEGFA": 9.0,
        "KDR": 9.0,
        "FLT1": 8.5,
        "ANGPT2": 8.0,
    },
    "DNA_DAMAGE_AND_APOPTOSIS": {
        "TP53": 8.5,
        "STK11": 9.0,
        "KEAP1": 8.5,
        "CDKN2A": 8.0,
        "PARP1": 8.5,
    },
}

# ── Drug Safety Risk Tiers ──────────────────────────────────────────────
DRUG_SAFETY_RISK = {
    "high_risk": [
        "Osimertinib (Interstitial lung disease / Pneumonitis, QTc prolongation)",
        "Sotorasib (Severe drug-induced liver injury / Hepatotoxicity)",
    ],
    "moderate_risk": [
        "Pembrolizumab (Immune-mediated pneumonitis, Colitis, Thyroiditis)",
        "Alectinib (Hepatotoxicity, Bradycardia, Myalgia / elevated CPK)",
    ],
    "low_risk": [
        "Supplemental oxygen therapy",
        "Prophylactic antiemetics (Ondansetron)",
    ],
}
DISEASE_SPECIFIC_RISK = DRUG_SAFETY_RISK
DRUG_INDUCED_LUPUS_RISK = DRUG_SAFETY_RISK

SCREENING_PROFILE = {
    "strategy_id": "nsclc-screening-v1",
    "pathway_keywords": [
        "egfr",
        "kras",
        "alk",
        "tyrosine kinase",
        "checkpoint",
        "pd-l1",
        "mapk",
        "pi3k",
        "mtor",
    ],
    "mechanism_keywords": [
        "egfr inhibitor",
        "kras g12c inhibitor",
        "alk inhibitor",
        "pd-l1 inhibitor",
        "vegf inhibitor",
        "kinase inhibitor",
    ],
    "reference_drug_ids": [
        "CHEMBL1079742",
        "CHEMBL1173655",
        "CHEMBL1738797",
        "CHEMBL2108738",
        "CHEMBL3707227",
        "CHEMBL3188267",
    ],
    "weights": {
        "binding_estimate": 0.30,
        "druglikeness": 0.20,
        "target_complementarity": 0.25,
        "similarity_score": 0.15,
        "novelty_score": 0.10,
    },
    "source": "curated_nsclc_knowledge_graph",
    "curated_inputs": ["pathways", "drugs", "screening_strategy"],
    "inferred_inputs": ["mechanism_keyword_matching", "property_based_binding_estimate"],
    "limitations": [
        "Property scores are heuristic prioritization signals, not experimental binding affinity."
    ],
}
