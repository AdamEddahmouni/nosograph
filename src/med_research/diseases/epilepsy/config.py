"""Epilepsy configuration.

Disease-specific parameters used by research pipeline modules.
"""

PIPELINE_LABEL = "Epilepsy"
DEFAULT_SAMPLE_SIZE = 50

# ── Symptoms (used by adverse_events/profiler.py) ────────────────────────
SYMPTOMS = [
    "focal onset aware seizures",
    "focal onset impaired awareness seizures",
    "generalized tonic-clonic convulsions",
    "absence seizures with staring spells",
    "myoclonic jerks and spasms",
    "atonic seizures (drop attacks)",
    "postictal confusion and lethargy",
    "sensory aura or epigastric rising sensations",
    "motor automatisms (lip smacking, swallowing)",
    "temporary loss of consciousness",
    "status epilepticus",
    "lateral tongue biting",
    "ictal urinary incontinence"
]

# ── Literature Mining ────────────────────────────────────────────────────
PUBMED_QUERIES = [
    "(epilepsy[Title/Abstract] OR seizure[Title/Abstract] OR anticonvulsant[Title/Abstract]) AND (treatment[Title/Abstract] OR therapeutics[Title/Abstract])",
    "(epilepsy[Title/Abstract]) AND (levetiracetam[Title/Abstract] OR lamotrigine[Title/Abstract] OR cenobamate[Title/Abstract] OR lacosamide[Title/Abstract])",
    "(epilepsy[Title/Abstract]) AND (sodium channel[Title/Abstract] OR SV2A[Title/Abstract] OR GABA[Title/Abstract])",
    "(epilepsy[Title/Abstract]) AND (drug resistant[Title/Abstract] OR clinical trial[Title/Abstract])"
]

# ── Clinical trials / GWAS search terms ────────────────────────────────
TRIAL_QUERY = "Epilepsy OR Refractory Epilepsy OR Focal Seizures OR Generalized Seizures"
GWAS_SEARCH_TERMS = [
    "epilepsy",
    "focal epilepsy",
    "genetic generalized epilepsy",
    "febrile seizures"
]

# ── CAR-T & Target Scoring Tables ───────────────────────────────────────
CAR_T_SCORES = {
    "SYNAPTIC_VESICLE_NEUROTRANSMISSION": {
        "SV2A": 10.0,
        "SV2B": 8.5,
        "STX1A": 8.5,
        "SNAP25": 8.0,
        "SYN1": 8.0
    },
    "VOLTAGE_GATED_ION_CHANNELS": {
        "SCN1A": 10.0,
        "SCN2A": 9.5,
        "SCN8A": 9.5,
        "KCNQ2": 9.5,
        "KCNQ3": 9.0,
        "CACNA1A": 9.5,
        "CACNA1H": 8.5
    },
    "GABAERGIC_INHIBITORY_SYSTEM": {
        "GABRA1": 10.0,
        "GABRB3": 9.5,
        "GABRG2": 9.0,
        "ABAT": 8.5,
        "SLC6A1": 9.0
    }
}

# ── Drug Safety Risk Tiers ──────────────────────────────────────────────
DRUG_SAFETY_RISK = {
    "high_risk": [
        "Valproate in pregnancy (Teratogenicity)",
        "Carbamazepine in HLA-B*1502 positive patients (SJS/TEN)",
        "Abrupt AED discontinuation (Status epilepticus)"
    ],
    "moderate_risk": [
        "Levetiracetam (Neuropsychiatric / aggression / depression)",
        "Lamotrigine (Titration-dependent rash)"
    ],
    "low_risk": [
        "Lacosamide",
        "Brivaracetam"
    ]
}
DISEASE_SPECIFIC_RISK = DRUG_SAFETY_RISK
DRUG_INDUCED_LUPUS_RISK = DRUG_SAFETY_RISK

SCREENING_PROFILE = {
    "strategy_id": "epilepsy-screening-v1",
    "reference_drug_ids": [
        "levetiracetam",
        "cenobamate",
        "lacosamide",
        "lamotrigine"
],
    "weights": {
        "binding_estimate": 0.30,
        "druglikeness": 0.20,
        "target_complementarity": 0.25,
        "similarity_score": 0.15,
        "novelty_score": 0.10,
    },
    "source": "curated_epilepsy_knowledge_graph",
    "curated_inputs": ["pathways", "drugs", "screening_strategy"],
    "inferred_inputs": ["mechanism_keyword_matching", "property_based_binding_estimate"],
    "limitations": [
        "Property scores are heuristic prioritization signals, not experimental binding affinity or efficacy."
    ],
}
