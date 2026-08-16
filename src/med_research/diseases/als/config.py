"""Amyotrophic Lateral Sclerosis (ALS) configuration.

Disease-specific parameters used by research pipeline modules.
"""

PIPELINE_LABEL = "Amyotrophic Lateral Sclerosis"
DEFAULT_SAMPLE_SIZE = 50

# ── Symptoms (used by adverse_events/profiler.py) ────────────────────────
SYMPTOMS = [
    "progressive muscle weakness",
    "asymmetric limb weakness",
    "foot drop",
    "hand weakness",
    "loss of fine motor dexterity",
    "muscle fasciculations",
    "muscle cramps",
    "muscle atrophy",
    "spasticity",
    "hyperreflexia",
    "Babinski sign",
    "dysarthria",
    "slurred speech",
    "dysphagia",
    "swallowing difficulty",
    "tongue fasciculations",
    "pseudobulbar affect",
    "inappropriate laughing or crying",
    "dyspnea",
    "orthopnea",
    "respiratory muscle weakness",
    "respiratory insufficiency",
    "hypoventilation",
    "morning headaches",
    "excessive fatigue",
    "weight loss",
    "frontotemporal cognitive impairment",
    "executive dysfunction",
]

# ── Literature Mining ────────────────────────────────────────────────────
PUBMED_QUERIES = [
    "(Amyotrophic lateral sclerosis[Title/Abstract] OR ALS[Title/Abstract] OR motor neuron disease[Title/Abstract]) AND (treatment[Title/Abstract] OR therapy[Title/Abstract])",
    "(Amyotrophic lateral sclerosis[Title/Abstract]) AND (TDP-43[Title/Abstract] OR SOD1[Title/Abstract] OR C9orf72[Title/Abstract])",
    "(Amyotrophic lateral sclerosis[Title/Abstract]) AND (clinical trial[Title/Abstract])",
    "(Amyotrophic lateral sclerosis[Title/Abstract]) AND (biomarker[Title/Abstract] OR neurofilament[Title/Abstract])",
    "(Amyotrophic lateral sclerosis[Title/Abstract]) AND (neuroinflammation[Title/Abstract] OR excitotoxicity[Title/Abstract])",
]

# ── Clinical trials / GWAS search terms ────────────────────────────────
TRIAL_QUERY = "Amyotrophic Lateral Sclerosis OR ALS OR Motor Neuron Disease"
GWAS_SEARCH_TERMS = [
    "Amyotrophic lateral sclerosis",
    "motor neuron disease",
    "ALS",
]

# ── CAR-T & Target Scoring Tables ───────────────────────────────────────
CAR_T_SCORES = {
    "TDP43_PROTEOSTASIS": {
        "TARDBP": 10.0,
        "C9orf72": 9.5,
        "FUS": 9.5,
        "SOD1": 9.0,
        "VCP": 9.0,
        "TBK1": 8.5,
        "OPTN": 8.5,
        "SQSTM1": 8.0,
        "UBQLN2": 8.0,
        "STMN2": 7.5,
        "UNC13A": 7.5,
        "ATXN2": 7.0,
    },
    "EXCITOTOXICITY_ION_CHANNELS": {
        "SLC1A2": 10.0,
        "GRIN1": 9.5,
        "GRIN2A": 9.0,
        "GRIA2": 9.0,
        "SCN4A": 8.5,
        "CACNA1A": 8.0,
        "KCNQ2": 7.5,
    },
    "MITOCHONDRIAL_OXIDATIVE_STRESS": {
        "SOD1": 10.0,
        "ROS": 9.5,
        "HSPA5": 9.0,
        "PARK7": 8.5,
        "CHCHD10": 8.5,
        "SIGMAR1": 8.0,
        "ATAD3A": 7.5,
    },
    "NEUROINFLAMMATION_MICROGLIA": {
        "KIT": 9.5,
        "CSF1R": 9.5,
        "TREM2": 9.0,
        "NLRP3": 8.5,
        "IL1B": 8.5,
        "TNF": 8.0,
        "TGFB1": 7.5,
    },
    "TARGET_DRUGGABILITY": {
        "SOD1": 10.0,
        "SCN4A": 9.5,
        "HSPA5": 9.0,
        "KIT": 9.0,
        "ATXN2": 8.5,
        "STMN2": 8.0,
        "C9orf72": 8.0,
    },
}

# ── Drug safety & disease-specific risk ──────────────────────────────────
DRUG_SAFETY_RISK = {
    "high_risk": [
        "aminoglycosides",
        "gentamicin",
        "tobramycin",
        "fluoroquinolones",
        "ciprofloxacin",
        "neuromuscular_blockers",
        "succinylcholine",
        "botulinum_toxin",
        "baclofen_withdrawal",
    ],
    "moderate_risk": [
        "statins",
        "beta_blockers",
        "calcium_channel_blockers",
        "sedatives",
        "benzodiazepines",
        "opioids",
    ],
    "low_risk": [
        "dextromethorphan_quinidine",
        "glycopyrrolate",
        "atropine",
        "amitriptyline",
        "scopolamine",
        "gabapentin",
    ],
}
DISEASE_SPECIFIC_RISK = DRUG_SAFETY_RISK
DRUG_INDUCED_LUPUS_RISK = DRUG_SAFETY_RISK

SCREENING_PROFILE = {
    "strategy_id": "als-screening-v1",
    "pathway_keywords": [
        "motor neuron",
        "tdp-43",
        "sod1",
        "glutamate",
        "excitotoxicity",
        "oxidative stress",
        "autophagy",
        "neuroinflammation",
    ],
    "mechanism_keywords": [
        "sod1",
        "glutamate",
        "free radical",
        "er stress",
        "csf1r",
        "kinase",
        "antisense",
    ],
    "reference_drug_ids": [
        "riluzole",
        "edaravone",
        "tofersen",
        "sodium_phenylbutyrate_taurursodiol",
        "masitinib",
    ],
    "weights": {
        "binding_estimate": 0.30,
        "druglikeness": 0.20,
        "target_complementarity": 0.25,
        "similarity_score": 0.15,
        "novelty_score": 0.10,
    },
    "source": "curated_als_knowledge_graph",
    "curated_inputs": ["pathways", "drugs", "screening_strategy"],
    "inferred_inputs": ["mechanism_keyword_matching", "property_based_binding_estimate"],
    "limitations": [
        "Property scores are heuristic prioritization signals, not experimental binding affinity or efficacy."
    ],
}
