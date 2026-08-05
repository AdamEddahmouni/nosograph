"""Autoimmune disease configuration — RA (Rheumatoid Arthritis (RA)).

Disease-specific parameters used by the research pipeline modules.
CAR_T_SCORES and DRUG_INDUCED_LUPUS_RISK are derived from the
disease knowledge graph (genes.json) using a documented rubric; see
scripts/populate_disease_configs.py for the scoring rules.
"""

PIPELINE_LABEL = "Rheumatoid Arthritis (RA)"
DEFAULT_SAMPLE_SIZE = 50

SYMPTOMS = [
    "joint pain", "joint swelling", "morning stiffness",
    "fatigue", "fever", "weight loss", "rheumatoid nodules",
    "synovitis", "bone erosion", "cartilage loss",
    "decreased range of motion", "symmetrical arthritis",
    "hand deformities", "foot deformities",
    "extra-articular manifestations", "vasculitis",
    "pleuritis", "pericarditis", "interstitial lung disease",
    "anemia", "thrombocytosis", "osteoporosis",
    "cardiovascular disease", "Sjogren's syndrome",
]

PUBMED_QUERIES = [
    "(RA[Title/Abstract]) AND (treatment[Title/Abstract])",
    "(RA[Title/Abstract]) AND (genetics[Title/Abstract])",
    "(RA[Title/Abstract]) AND (clinical trial[Title/Abstract])",
]

CAR_T_SCORES = {
    "B Cell Differentiation": {
        "IKZF3": 9.0,
        "PRDM1": 9.0,
    },
    "B Cell Signaling": {
        "BANK1": 9.0,
        "BLK": 9.0,
    },
    "Bone Erosion / Osteoclast Activation": {
        "RANKL": 4.0,
    },
    "Citrullination / Autoantigen Generation": {
        "PADI4": 8.5,
    },
    "IL-6 / JAK-STAT": {
        "IL6R": 6.0,
    },
    "Immune Complex Clearance": {
        "FCGR2A": 4.0,
    },
    "JAK-STAT Signaling": {
        "STAT4": 6.0,
        "TYK2": 6.0,
    },
    "Joint Destruction / ECM Remodeling": {
        "MMP9": 4.0,
    },
    "MHC / Antigen Presentation": {
        "HLA-DRB1": 6.5,
    },
    "NF-κB Pathway": {
        "REL": 5.5,
        "TNFAIP3": 5.5,
    },
    "T Cell Costimulation": {
        "CD28": 7.0,
        "CD40": 7.0,
        "CTLA4": 7.0,
    },
    "T Cell Signaling": {
        "ANKRD55": 6.0,
        "IL2RA": 6.0,
        "IL2RB": 6.0,
        "PTPN22": 6.0,
    },
    "TNF-alpha Signaling": {
        "TNF": 5.5,
        "TRAF1_C5": 5.5,
    },
    "Th17 / IL-17 Pathway": {
        "CCR6": 4.0,
    },
    "Type I Interferon Pathway": {
        "IRF5": 5.0,
    },
}

DRUG_INDUCED_LUPUS_RISK = {
    "high_risk": [
        "infliximab",
        "adalimumab",
        "etanercept",
        "certolizumab",
        "golimumab",
    ],
    "moderate_risk": [
        "sulfasalazine",
        "minocycline",
        "levamisole",
        "gold salts",
    ],
    "low_risk": [
        "methotrexate",
        "hydroxychloroquine",
        "NSAIDs",
        "corticosteroids",
    ],
}
