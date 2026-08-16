"""Parkinson's Disease (PD) configuration.

Disease-specific parameters used by research pipeline modules.
"""

PIPELINE_LABEL = "Parkinson's Disease"
DEFAULT_SAMPLE_SIZE = 50

# ── Symptoms (used by adverse_events/profiler.py) ────────────────────────
SYMPTOMS = [
    "resting tremor",
    "pill-rolling tremor",
    "bradykinesia",
    "slowness of movement",
    "muscle rigidity",
    "cogwheel rigidity",
    "lead-pipe rigidity",
    "postural instability",
    "shuffling gait",
    "festinating gait",
    "freezing of gait",
    "micrographia",
    "hypophonia",
    "masked facies",
    "anosmia",
    "hyposmia",
    "REM sleep behavior disorder",
    "insomnia",
    "restless legs",
    "constipation",
    "orthostatic hypotension",
    "urinary urgency",
    "excessive daytime sleepiness",
    "cognitive decline",
    "dementia",
    "executive dysfunction",
    "depression",
    "anxiety",
    "apathy",
    "visual hallucinations",
    "levodopa-induced dyskinesia",
    "motor fluctuations",
]

# ── Literature Mining ────────────────────────────────────────────────────
PUBMED_QUERIES = [
    "(Parkinson disease[Title/Abstract] OR Parkinson's disease[Title/Abstract]) AND (treatment[Title/Abstract] OR therapeutics[Title/Abstract])",
    "(Parkinson disease[Title/Abstract]) AND (alpha-synuclein[Title/Abstract] OR Lewy body[Title/Abstract])",
    "(Parkinson disease[Title/Abstract]) AND (genetics[Title/Abstract] OR LRRK2[Title/Abstract] OR GBA[Title/Abstract])",
    "(Parkinson disease[Title/Abstract]) AND (clinical trial[Title/Abstract])",
    "(Parkinson disease[Title/Abstract]) AND (biomarker[Title/Abstract] OR neuroprotection[Title/Abstract])",
]

# ── Clinical trials / GWAS search terms ────────────────────────────────
TRIAL_QUERY = "Parkinson's Disease OR Parkinson Disease OR PD"
GWAS_SEARCH_TERMS = [
    "Parkinson's disease",
    "Parkinson disease",
    "parkinsonism",
]

# ── CAR-T & Target Scoring Tables ───────────────────────────────────────
CAR_T_SCORES = {
    "SYNUCLEIN_PATHOLOGY": {
        "SNCA": 10.0,
        "LRRK2": 9.5,
        "GBA1": 9.5,
        "PRKN": 9.0,
        "PINK1": 9.0,
        "PARK7": 8.5,
        "DJ1": 8.5,
        "MAPT": 8.0,
        "UCHL1": 7.5,
        "VPS35": 7.5,
        "ATP13A2": 7.0,
        "PLA2G6": 7.0,
        "FBXO7": 6.5,
        "DNAJC6": 6.5,
        "SYNJ1": 6.0,
    },
    "DOPAMINERGIC_INTEGRITY": {
        "SLC6A3": 10.0,
        "DRD2": 9.5,
        "DRD3": 9.0,
        "DDC": 9.5,
        "TH": 9.0,
        "MAOB": 9.0,
        "COMT": 8.5,
        "SLC18A2": 8.5,
        "ALDH1A1": 7.5,
        "RET": 7.0,
        "GDNF": 7.5,
        "BDNF": 7.0,
    },
    "MITOCHONDRIAL_AUTOPHAGY": {
        "PINK1": 10.0,
        "PRKN": 10.0,
        "PARK7": 9.0,
        "GBA1": 8.5,
        "LRRK2": 8.5,
        "SNCA": 8.0,
        "HTRA2": 7.5,
        "CHCHD2": 7.0,
        "POLG": 7.0,
        "SQSTM1": 7.5,
        "OPTN": 7.0,
    },
    "NEUROINFLAMMATION": {
        "LRRK2": 9.5,
        "NLRP3": 9.0,
        "IL1B": 8.5,
        "TNF": 8.5,
        "NOS2": 8.0,
        "TLR4": 8.0,
        "TLR2": 7.5,
        "CX3CR1": 7.5,
        "C1QA": 7.0,
        "TREM2": 7.0,
    },
    "TARGET_DRUGGABILITY": {
        "MAOB": 10.0,
        "COMT": 10.0,
        "DRD2": 9.5,
        "DRD3": 9.0,
        "LRRK2": 9.5,
        "GBA1": 9.0,
        "GRIN1": 8.5,
        "ADORA2A": 8.5,
        "SNCA": 8.0,
        "NLRP3": 7.5,
    },
}

# ── Drug safety & disease-specific risk ──────────────────────────────────
DRUG_SAFETY_RISK = {
    "high_risk": [
        "haloperidol",
        "chlorpromazine",
        "fluphenazine",
        "metoclopramide",
        "prochlorperazine",
        "reserpine",
        "tetrabenazine",
        "valproate",
    ],
    "moderate_risk": [
        "risperidone",
        "olanzapine",
        "aripiprazole",
        "lithium",
        "amiodarone",
        "fluoxetine",
        "sertraline",
    ],
    "low_risk": [
        "quetiapine",
        "clozapine",
        "pimavanserin",
        "donepezil",
        "rivastigmine",
        "melatonin",
        "macrogol",
    ],
}
DISEASE_SPECIFIC_RISK = DRUG_SAFETY_RISK
DRUG_INDUCED_LUPUS_RISK = DRUG_SAFETY_RISK

SCREENING_PROFILE = {
    "strategy_id": "pd-screening-v1",
    "pathway_keywords": [
        "dopamine",
        "synuclein",
        "mitochondrial",
        "autophagy",
        "lrrk2",
        "lysosomal",
        "neuroinflammation",
    ],
    "mechanism_keywords": [
        "dopamine",
        "mao-b",
        "comt",
        "lrrk2",
        "gba",
        "synuclein",
        "nmda",
        "adenosine a2a",
    ],
    "reference_drug_ids": [
        "levodopa",
        "pramipexole",
        "rasagiline",
        "entacapone",
        "safinamide",
        "amantadine",
    ],
    "weights": {
        "binding_estimate": 0.30,
        "druglikeness": 0.20,
        "target_complementarity": 0.25,
        "similarity_score": 0.15,
        "novelty_score": 0.10,
    },
    "source": "curated_pd_knowledge_graph",
    "curated_inputs": ["pathways", "drugs", "screening_strategy"],
    "inferred_inputs": ["mechanism_keyword_matching", "property_based_binding_estimate"],
    "limitations": [
        "Property scores are heuristic prioritization signals, not experimental binding affinity or efficacy."
    ],
}
