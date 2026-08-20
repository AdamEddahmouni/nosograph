"""Major Depressive Disorder configuration.

Disease-specific parameters used by research pipeline modules.
"""

PIPELINE_LABEL = "Major Depressive Disorder"
DEFAULT_SAMPLE_SIZE = 50

# ── Symptoms (used by adverse_events/profiler.py) ────────────────────────
SYMPTOMS = [
    "depressed mood",
    "anhedonia",
    "loss of interest or pleasure",
    "fatigue and loss of energy",
    "feelings of worthlessness or excessive guilt",
    "diminished concentration and memory",
    "indecisiveness",
    "insomnia",
    "hypersomnia",
    "psychomotor agitation or retardation",
    "significant weight loss or gain",
    "changes in appetite",
    "recurrent suicidal ideation",
    "executive dysfunction",
    "anxiety and irritability",
    "somatic pain symptoms",
]

# ── Literature Mining ────────────────────────────────────────────────────
PUBMED_QUERIES = [
    "(major depressive disorder[Title/Abstract] OR depression[Title/Abstract]) AND (treatment[Title/Abstract] OR therapeutics[Title/Abstract])",
    "(major depressive disorder[Title/Abstract]) AND (SSRI[Title/Abstract] OR SNRI[Title/Abstract] OR ketamine[Title/Abstract] OR esketamine[Title/Abstract])",
    "(major depressive disorder[Title/Abstract]) AND (neuroinflammation[Title/Abstract] OR neurogenesis[Title/Abstract] OR synaptic plasticity[Title/Abstract])",
    "(major depressive disorder[Title/Abstract]) AND (treatment resistant[Title/Abstract] OR clinical trial[Title/Abstract])",
]

# ── Clinical trials / GWAS search terms ────────────────────────────────
TRIAL_QUERY = "Major Depressive Disorder OR Treatment Resistant Depression OR Major Depression"
GWAS_SEARCH_TERMS = [
    "major depressive disorder",
    "depressive symptoms",
    "neuroticism",
    "bipolar disorder",
    "subjective well-being",
]

# ── CAR-T & Target Scoring Tables ───────────────────────────────────────
CAR_T_SCORES = {
    "MONOAMINERGIC_NEUROTRANSMISSION": {
        "SLC6A4": 10.0,
        "SLC6A2": 9.5,
        "SLC6A3": 9.0,
        "HTR1A": 9.5,
        "HTR2A": 9.0,
        "MAOA": 8.5,
    },
    "GLUTAMATERGIC_SYNAPSE_PLASTICITY": {
        "GRIN1": 9.5,
        "GRIN2B": 9.5,
        "GRIN2A": 9.0,
        "GRIA1": 8.5,
        "BDNF": 10.0,
        "NTRK2": 9.5,
    },
    "NEUROENDOCRINE_INFLAMMATION": {
        "NR3C1": 9.0,
        "FKBP5": 8.5,
        "CRHR1": 8.0,
        "IL6": 8.0,
        "TNF": 7.5,
    },
}

# ── Drug Safety Risk Tiers ──────────────────────────────────────────────
DRUG_SAFETY_RISK = {
    "high_risk": [
        "MAOIs",
        "Tricyclic Antidepressants in Overdose",
        "Serotonin Syndrome Combinations",
    ],
    "moderate_risk": ["SSRIs / SNRIs (Bleeding risk, Hyponatremia, QTc prolongation)"],
    "low_risk": ["Bupropion", "Vortioxetine", "Esketamine in controlled clinic setting"],
}
DISEASE_SPECIFIC_RISK = DRUG_SAFETY_RISK
DRUG_INDUCED_LUPUS_RISK = DRUG_SAFETY_RISK

SCREENING_PROFILE = {
    "strategy_id": "major_depressive_disorder-screening-v1",
    "reference_drug_ids": [
        "escitalopram",
        "sertraline",
        "duloxetine",
        "bupropion",
        "esketamine",
        "vortioxetine",
    ],
    "weights": {
        "binding_estimate": 0.30,
        "druglikeness": 0.20,
        "target_complementarity": 0.25,
        "similarity_score": 0.15,
        "novelty_score": 0.10,
    },
    "source": "curated_major_depressive_disorder_knowledge_graph",
    "curated_inputs": ["pathways", "drugs", "screening_strategy"],
    "inferred_inputs": ["mechanism_keyword_matching", "property_based_binding_estimate"],
    "limitations": [
        "Property scores are heuristic prioritization signals, not experimental binding affinity or efficacy."
    ],
}
