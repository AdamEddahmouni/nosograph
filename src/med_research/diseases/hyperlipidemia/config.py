"""Hyperlipidemia & Familial Hypercholesterolemia configuration.

Disease-specific parameters used by research pipeline modules.
"""

PIPELINE_LABEL = "Hyperlipidemia & Familial Hypercholesterolemia"
DEFAULT_SAMPLE_SIZE = 50

# ── Symptoms (used by adverse_events/profiler.py) ────────────────────────
SYMPTOMS = [
    "severely elevated LDL-cholesterol (LDL-C >= 190 mg/dL)",
    "elevated total circulating cholesterol",
    "hypertriglyceridemia",
    "tendon xanthomas (especially Achilles and extensor tendons)",
    "xanthelasma palpebrarum (lipid deposits on eyelids)",
    "corneal arcus (arcus senilis before age 45)",
    "premature coronary artery disease and myocardial infarction",
    "angina pectoris on exertion",
    "intermittent claudication from peripheral artery disease",
    "eruptive cutaneous xanthomas in severe chylomicronemia",
    "acute pancreatitis risk in severe hypertriglyceridemia",
]

# ── Literature Mining ────────────────────────────────────────────────────
PUBMED_QUERIES = [
    "(hyperlipidemia[Title/Abstract] OR familial hypercholesterolemia[Title/Abstract] OR LDL-C[Title/Abstract]) AND (treatment[Title/Abstract] OR therapeutics[Title/Abstract])",
    "(hyperlipidemia[Title/Abstract]) AND (statin[Title/Abstract] OR PCSK9[Title/Abstract] OR ezetimibe[Title/Abstract] OR inclisiran[Title/Abstract])",
    "(hyperlipidemia[Title/Abstract]) AND (cardiovascular outcomes[Title/Abstract] OR atherosclerosis[Title/Abstract])",
    "(hyperlipidemia[Title/Abstract]) AND (clinical trial[Title/Abstract])",
]

# ── Clinical trials / GWAS search terms ────────────────────────────────
TRIAL_QUERY = "Hyperlipidemia OR Familial Hypercholesterolemia OR Hypercholesterolemia OR Atherogenic Dyslipidemia"
GWAS_SEARCH_TERMS = [
    "low density lipoprotein cholesterol",
    "total cholesterol",
    "triglycerides",
    "coronary artery disease",
    "apolipoprotein B",
]

# ── CAR-T & Target Scoring Tables ───────────────────────────────────────
CAR_T_SCORES = {
    "CHOLESTEROL_CLEARANCE_SYNTHESIS": {
        "PCSK9": 10.0,
        "LDLR": 10.0,
        "HMGCR": 10.0,
        "APOB": 9.5,
        "ACLY": 9.5,
        "NPC1L1": 9.5,
    },
    "TRIGLYCERIDE_LIPOPROTEIN_LIPASE": {
        "ANGPTL3": 10.0,
        "APOC3": 9.5,
        "LPL": 9.5,
        "LPA": 9.5,
        "PPARA": 9.0,
    },
    "ATHEROGENIC_LIPID_METABOLISM": {
        "CETP": 8.5,
        "CYP7A1": 8.0,
        "SREBF2": 8.5,
        "ABCA1": 8.5,
        "ABCG5": 8.0,
    },
}

# ── Drug Safety Risk Tiers ──────────────────────────────────────────────
DRUG_SAFETY_RISK = {
    "high_risk": ["Statin-Gemfibrozil combination in renal impairment (Severe Rhabdomyolysis)"],
    "moderate_risk": [
        "High-intensity Statins (Statin-associated muscle symptoms, hepatic transaminase elevations)",
        "Bempedoic Acid (Hyperuricemia, tendon rupture)",
    ],
    "low_risk": ["PCSK9 Monoclonal Antibodies (Evolocumab/Alirocumab)", "Inclisiran", "Ezetimibe"],
}
DISEASE_SPECIFIC_RISK = DRUG_SAFETY_RISK
DRUG_INDUCED_LUPUS_RISK = DRUG_SAFETY_RISK

SCREENING_PROFILE = {
    "strategy_id": "hyperlipidemia-screening-v1",
    "reference_drug_ids": [
        "atorvastatin",
        "evolocumab",
        "inclisiran",
        "ezetimibe",
        "bempedoic_acid",
    ],
    "weights": {
        "binding_estimate": 0.30,
        "druglikeness": 0.20,
        "target_complementarity": 0.25,
        "similarity_score": 0.15,
        "novelty_score": 0.10,
    },
    "source": "curated_hyperlipidemia_knowledge_graph",
    "curated_inputs": ["pathways", "drugs", "screening_strategy"],
    "inferred_inputs": ["mechanism_keyword_matching", "property_based_binding_estimate"],
    "limitations": [
        "Property scores are heuristic prioritization signals, not experimental binding affinity or efficacy."
    ],
}
