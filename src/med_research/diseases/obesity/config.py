"""Obesity configuration.

Disease-specific parameters used by research pipeline modules.
"""

PIPELINE_LABEL = "Obesity"
DEFAULT_SAMPLE_SIZE = 50

# ── Symptoms (used by adverse_events/profiler.py) ────────────────────────
SYMPTOMS = [
    "excessive adiposity",
    "elevated body mass index (BMI >= 30 kg/m2)",
    "increased waist circumference and visceral adiposity",
    "dyspnea on exertion",
    "obstructive sleep apnea",
    "daytime hypersomnolence",
    "weight-bearing joint arthralgia and osteoarthritis",
    "impaired glucose tolerance and hyperinsulinemia",
    "systemic arterial hypertension",
    "mixed atherogenic dyslipidemia",
    "gastroesophageal reflux disease (GERD)",
    "acanthosis nigricans in intertriginous folds"
]

# ── Literature Mining ────────────────────────────────────────────────────
PUBMED_QUERIES = [
    "(obesity[Title/Abstract] OR overweight[Title/Abstract]) AND (treatment[Title/Abstract] OR therapeutics[Title/Abstract])",
    "(obesity[Title/Abstract]) AND (tirzepatide[Title/Abstract] OR semaglutide[Title/Abstract] OR GLP-1[Title/Abstract] OR GIP[Title/Abstract])",
    "(obesity[Title/Abstract]) AND (weight loss[Title/Abstract] OR satiety[Title/Abstract] OR adiposity[Title/Abstract])",
    "(obesity[Title/Abstract]) AND (clinical trial[Title/Abstract])"
]

# ── Clinical trials / GWAS search terms ────────────────────────────────
TRIAL_QUERY = "Obesity OR Overweight OR Weight Loss OR Adiposity"
GWAS_SEARCH_TERMS = [
    "body mass index",
    "obesity",
    "waist-to-hip ratio",
    "body fat percentage",
    "leptin"
]

# ── CAR-T & Target Scoring Tables ───────────────────────────────────────
CAR_T_SCORES = {
    "INCRETIN_APPETITE_CIRCUITS": {
        "GLP1R": 10.0,
        "GIPR": 9.5,
        "GCGR": 9.0,
        "MC4R": 10.0,
        "POMC": 9.5,
        "LEPR": 9.5,
        "LEP": 9.0
    },
    "ENERGY_EXPENDITURE_THERMOGENESIS": {
        "ADRB3": 9.0,
        "UCP1": 9.0,
        "PRKAA1": 9.0,
        "PPARA": 8.5,
        "FGF21": 9.0
    },
    "LIPOGENESIS_FAT_STORAGE": {
        "FASN": 8.5,
        "ACACA": 8.5,
        "DGAT1": 8.0,
        "SREBF1": 8.0,
        "PNLIP": 8.5
    }
}

# ── Drug Safety Risk Tiers ──────────────────────────────────────────────
DRUG_SAFETY_RISK = {
    "high_risk": [
        "Phentermine-Topiramate in pregnancy (Teratogenicity, Tachycardia)"
    ],
    "moderate_risk": [
        "GLP-1 / GIP agonists (GI adverse events, Cholelithiasis)",
        "Bupropion-Naltrexone (Seizure threshold reduction)"
    ],
    "low_risk": [
        "Setmelanotide in monogenic obesity",
        "Orlistat (Local GI effects)"
    ]
}
DISEASE_SPECIFIC_RISK = DRUG_SAFETY_RISK
DRUG_INDUCED_LUPUS_RISK = DRUG_SAFETY_RISK

SCREENING_PROFILE = {
    "strategy_id": "obesity-screening-v1",
    "reference_drug_ids": [
        "tirzepatide",
        "semaglutide",
        "setmelanotide",
        "phentermine_topiramate"
],
    "weights": {
        "binding_estimate": 0.30,
        "druglikeness": 0.20,
        "target_complementarity": 0.25,
        "similarity_score": 0.15,
        "novelty_score": 0.10,
    },
    "source": "curated_obesity_knowledge_graph",
    "curated_inputs": ["pathways", "drugs", "screening_strategy"],
    "inferred_inputs": ["mechanism_keyword_matching", "property_based_binding_estimate"],
    "limitations": [
        "Property scores are heuristic prioritization signals, not experimental binding affinity or efficacy."
    ],
}
