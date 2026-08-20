"""Schizophrenia configuration.

Disease-specific parameters used by research pipeline modules.
"""

PIPELINE_LABEL = "Schizophrenia"
DEFAULT_SAMPLE_SIZE = 50

# ── Symptoms (used by adverse_events/profiler.py) ────────────────────────
SYMPTOMS = [
    "auditory hallucinations",
    "delusions of reference or persecutory delusions",
    "disorganized speech and derailment",
    "formal thought disorder",
    "disorganized or catatonic behavior",
    "blunted affect and emotional flattening",
    "avolition and lack of drive",
    "alogia and poverty of speech",
    "social withdrawal and asociality",
    "cognitive impairment",
    "working memory deficits",
    "paranoia",
    "anhedonia",
    "impaired executive function",
]

# ── Literature Mining ────────────────────────────────────────────────────
PUBMED_QUERIES = [
    "(schizophrenia[Title/Abstract]) AND (antipsychotic[Title/Abstract] OR therapeutics[Title/Abstract])",
    "(schizophrenia[Title/Abstract]) AND (dopamine D2[Title/Abstract] OR muscarinic[Title/Abstract] OR KarXT[Title/Abstract])",
    "(schizophrenia[Title/Abstract]) AND (negative symptoms[Title/Abstract] OR cognitive impairment[Title/Abstract])",
    "(schizophrenia[Title/Abstract]) AND (clinical trial[Title/Abstract])",
]

# ── Clinical trials / GWAS search terms ────────────────────────────────
TRIAL_QUERY = "Schizophrenia OR Schizoaffective Disorder OR Psychosis"
GWAS_SEARCH_TERMS = [
    "schizophrenia",
    "bipolar disorder",
    "psychosis",
    "neurodevelopmental disorder",
    "cognitive performance",
]

# ── CAR-T & Target Scoring Tables ───────────────────────────────────────
CAR_T_SCORES = {
    "DOPAMINERGIC_CIRCUITS": {"DRD2": 10.0, "DRD1": 8.5, "DRD3": 8.5, "DRD4": 8.0, "COMT": 9.0},
    "GLUTAMATERGIC_NMDA_SIGNALING": {
        "GRIN2A": 10.0,
        "GRIN1": 9.5,
        "GRIN2B": 9.0,
        "DAOA": 8.0,
        "PRODH": 7.5,
    },
    "CHOLINERGIC_SEROTONERGIC_AXIS": {
        "CHRM1": 9.5,
        "CHRM4": 9.5,
        "HTR2A": 9.5,
        "HTR1A": 8.5,
        "HTR6": 8.0,
    },
}

# ── Drug Safety Risk Tiers ──────────────────────────────────────────────
DRUG_SAFETY_RISK = {
    "high_risk": [
        "Clozapine (Agranulocytosis, Myocarditis, Seizures)",
        "High-dose Haloperidol (Neuroleptic Malignant Syndrome, Tardive Dyskinesia)",
    ],
    "moderate_risk": [
        "Olanzapine (Metabolic syndrome, Weight gain)",
        "Risperidone (Hyperprolactinemia, Extrapyramidal symptoms)",
    ],
    "low_risk": ["Aripiprazole", "KarXT (Muscarinic agonist)"],
}
DISEASE_SPECIFIC_RISK = DRUG_SAFETY_RISK
DRUG_INDUCED_LUPUS_RISK = DRUG_SAFETY_RISK

SCREENING_PROFILE = {
    "strategy_id": "schizophrenia-screening-v1",
    "reference_drug_ids": ["clozapine", "risperidone", "aripiprazole", "karxt", "olanzapine"],
    "weights": {
        "binding_estimate": 0.30,
        "druglikeness": 0.20,
        "target_complementarity": 0.25,
        "similarity_score": 0.15,
        "novelty_score": 0.10,
    },
    "source": "curated_schizophrenia_knowledge_graph",
    "curated_inputs": ["pathways", "drugs", "screening_strategy"],
    "inferred_inputs": ["mechanism_keyword_matching", "property_based_binding_estimate"],
    "limitations": [
        "Property scores are heuristic prioritization signals, not experimental binding affinity or efficacy."
    ],
}
