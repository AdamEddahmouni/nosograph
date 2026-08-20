"""Melanoma (MELANOMA) disease configuration.

Curated immuno-oncology parameters for Cutaneous Melanoma.
"""

PIPELINE_LABEL = "Cutaneous Melanoma"
DEFAULT_SAMPLE_SIZE = 50

# ── Symptoms (used by adverse_events/profiler.py) ────────────────────────
SYMPTOMS = [
    "asymmetrical pigmented skin lesion",
    "irregular or notched borders",
    "color variegation within mole",
    "diameter greater than 6mm",
    "evolving size, shape, or color of nevus",
    "ABCDE melanoma signs",
    "itching or pruritus of nevus",
    "lesion tenderness or pain",
    "ulceration of skin lesion",
    "bleeding or oozing from mole",
    "satellite pigment lesions",
    "amelanotic pink or red nodule",
    "regional lymphadenopathy",
    "palpable lymph nodes",
    "in-transit metastases",
    "fatigue",
    "unexplained weight loss",
    "bone pain",
    "neurological symptoms from brain metastasis",
]

# ── Literature Mining ────────────────────────────────────────────────────
PUBMED_QUERIES = [
    "(Melanoma[Title/Abstract]) AND (treatment[Title/Abstract] OR immunotherapy[Title/Abstract])",
    "(Melanoma[Title/Abstract]) AND (BRAF[Title/Abstract] OR MEK[Title/Abstract] OR PD-1[Title/Abstract])",
    "(Melanoma[Title/Abstract]) AND (clinical trial[Title/Abstract])",
    "(Melanoma[Title/Abstract]) AND (biomarker[Title/Abstract] OR resistance[Title/Abstract])",
]

# ── Clinical trials / GWAS search terms ────────────────────────────────
TRIAL_QUERY = "Melanoma OR Cutaneous Melanoma OR Metastatic Melanoma"
GWAS_SEARCH_TERMS = ["melanoma", "cutaneous melanoma", "skin pigmentation", "nevus count"]

# ── CAR-T & Target Scoring Tables ───────────────────────────────────────
CAR_T_SCORES = {
    "MELANOCYTE_LINEAGE_TARGETS": {
        "TYR": 9.0,
        "MLANA": 9.5,
        "PMEL": 9.5,
        "MITF": 8.5,
        "BAP1": 8.0,
    },
    "CHECKPOINT_IMMUNOMODULATORS": {
        "CD274": 10.0,
        "PDCD1": 10.0,
        "CTLA4": 9.5,
        "LAG3": 9.0,
        "HAVCR2": 8.5,
        "TIGIT": 8.5,
    },
    "MAPK_PATHWAY_TARGETS": {
        "BRAF": 10.0,
        "NRAS": 9.5,
        "MAP2K1": 9.0,
        "MAP2K2": 8.5,
        "KIT": 9.0,
        "NF1": 8.0,
    },
    "CANCER_TESTIS_ANTIGENS": {
        "NY-ESO-1": 9.5,
        "MAGEA3": 9.0,
        "MAGEA4": 9.0,
        "PRAME": 9.5,
    },
    "TUMOR_MICROENVIRONMENT_STROMAL": {
        "VEGFA": 8.5,
        "KDR": 8.5,
        "TGFB1": 8.0,
        "CXCL8": 8.0,
    },
}

# ── Drug Safety Risk Tiers ──────────────────────────────────────────────
DRUG_SAFETY_RISK = {
    "high_risk": [
        "Ipilimumab (Severe Immune-Mediated Enterocolitis / Hypophysitis)",
        "BRAF/MEK combo (Pyrexia, Cardiomyopathy, Retinal vein occlusion)",
    ],
    "moderate_risk": [
        "Nivolumab / Pembrolizumab (Immune-related thyroiditis, Rash, Pneumonitis)",
        "Dabrafenib + Trametinib (Skin papillomas, Photosensitivity)",
    ],
    "low_risk": [
        "Topical Imiquimod (Local erythema)",
        "Sunscreen photoprotection regimen",
    ],
}
DISEASE_SPECIFIC_RISK = DRUG_SAFETY_RISK
DRUG_INDUCED_LUPUS_RISK = DRUG_SAFETY_RISK

SCREENING_PROFILE = {
    "strategy_id": "melanoma-screening-v1",
    "pathway_keywords": [
        "mapk",
        "braf",
        "ras",
        "checkpoint",
        "pd-1",
        "ctla-4",
        "melanogenesis",
        "apoptosis",
    ],
    "mechanism_keywords": [
        "braf inhibitor",
        "mek inhibitor",
        "checkpoint inhibitor",
        "pd-1 blocker",
        "ctla-4 antagonist",
        "tyrosine kinase",
    ],
    "reference_drug_ids": [
        "vemurafenib",
        "dabrafenib",
        "trametinib",
        "pembrolizumab",
        "nivolumab",
        "ipilimumab",
    ],
    "weights": {
        "binding_estimate": 0.30,
        "druglikeness": 0.20,
        "target_complementarity": 0.25,
        "similarity_score": 0.15,
        "novelty_score": 0.10,
    },
    "source": "curated_melanoma_knowledge_graph",
    "curated_inputs": ["pathways", "drugs", "screening_strategy"],
    "inferred_inputs": ["mechanism_keyword_matching", "property_based_binding_estimate"],
    "limitations": [
        "Property scores are heuristic prioritization signals, not experimental binding affinity."
    ],
}
