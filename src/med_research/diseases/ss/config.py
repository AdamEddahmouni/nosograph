"""Autoimmune disease configuration — SS (Sjögren's Syndrome (SS)).

Disease-specific parameters used by the research pipeline modules.
CAR_T_SCORES and DRUG_INDUCED_LUPUS_RISK are derived from the
disease knowledge graph (genes.json) using a documented rubric; see
scripts/populate_disease_configs.py for the scoring rules.
"""

PIPELINE_LABEL = "Sjögren's Syndrome (SS)"
DEFAULT_SAMPLE_SIZE = 50

SYMPTOMS = [
    "dry eyes", "dry mouth", "xerostomia", "xerophthalmia",
    "fatigue", "joint pain", "arthritis", "parotid gland swelling",
    "vaginal dryness", "skin dryness", "dry cough",
    "dysphagia", "dental caries", "oral candidiasis",
    "peripheral neuropathy", "Raynaud's phenomenon",
    "vasculitis", "lymphadenopathy", "interstitial lung disease",
    "renal tubular acidosis", "purpura",
]

PUBMED_QUERIES = [
    "(SS[Title/Abstract]) AND (treatment[Title/Abstract])",
    "(SS[Title/Abstract]) AND (genetics[Title/Abstract])",
    "(SS[Title/Abstract]) AND (clinical trial[Title/Abstract])",
]

CAR_T_SCORES = {
    "Autoantibody Target / Glandular Function": {
        "CHRM3": 8.5,
    },
    "B Cell / Germinal Center": {
        "AICDA": 9.0,
    },
    "B Cell / Tfh Trafficking": {
        "CXCR5": 9.0,
    },
    "B Cell Development": {
        "IKZF1": 9.0,
    },
    "B Cell Differentiation": {
        "ETS1": 9.0,
    },
    "B Cell Signaling": {
        "BANK1": 9.0,
        "BLK": 9.0,
        "CD19": 9.0,
    },
    "B Cell Survival / BAFF Signaling": {
        "BAFF": 9.0,
    },
    "Immune Complex Clearance": {
        "FCGR2A": 4.0,
    },
    "Innate Immune Sensing": {
        "MYD88": 4.5,
        "TLR7": 4.5,
        "TLR9": 4.5,
    },
    "JAK-STAT Signaling": {
        "STAT4": 6.0,
        "TYK2": 6.0,
    },
    "MHC / Antigen Presentation": {
        "HLA-DRB1": 6.5,
    },
    "NF-κB Pathway": {
        "TNFAIP3": 5.5,
        "TNIP1": 5.5,
    },
    "Pro-inflammatory Cytokine": {
        "IL6": 4.0,
    },
    "T Cell Costimulation / Tfh": {
        "CD40LG": 7.0,
        "TNFSF4": 7.0,
    },
    "T Cell Signaling": {
        "PTPN22": 6.0,
    },
    "Th1 / IL-12 Pathway": {
        "IL12A": 4.0,
    },
    "Treg / Immune Regulation": {
        "FOXP3": 8.0,
    },
    "Type I Interferon Pathway": {
        "IFNA1": 5.0,
        "IFNAR1": 5.0,
        "IRF5": 5.0,
    },
}

DRUG_INDUCED_LUPUS_RISK = {
    "high_risk": [
        "interferon-alpha",
        "interferon-beta",
        "checkpoint inhibitors (anti-CTLA-4, anti-PD-1)",
    ],
    "moderate_risk": [
        "rituximab (infusion reactions)",
        "belimumab",
        "hydroxychloroquine (retinopathy)",
    ],
    "low_risk": [
        "pilocarpine",
        "cevimeline",
        "NSAIDs",
    ],
}

# ── Clinical trials / GWAS search terms ────────────────────────────────
TRIAL_QUERY = "Sjogren's syndrome OR SS"
GWAS_SEARCH_TERMS = [
    "Sjogren's syndrome",
    "SS",
]

# Compatibility alias retained for older callers; neutral name is authoritative.
DISEASE_SPECIFIC_RISK = DRUG_INDUCED_LUPUS_RISK

SCREENING_PROFILE = {
    "strategy_id": "ss-screening-v1",
    "pathway_keywords": ["interferon", "b cell", "baff", "germinal center", "tlr", "jak-stat", "nf-kb"],
    "mechanism_keywords": ["ifn", "interferon", "b cell", "baff", "cd20", "cd40", "tlr", "jak", "tyk2", "nf-kb"],
    "reference_drug_ids": ["hydroxychloroquine", "rituximab_ss", "belimumab", "ianalumab", "iscalimab", "abatacept"],
    "weights": {"binding_estimate": 0.25, "druglikeness": 0.15, "target_complementarity": 0.35, "similarity_score": 0.15, "novelty_score": 0.10},
    "source": "curated_ss_knowledge_graph",
    "curated_inputs": ["pathways", "drugs", "screening_strategy"],
    "inferred_inputs": ["mechanism_keyword_matching", "property_based_binding_estimate"],
    "limitations": ["Property scores are heuristic prioritization signals and do not establish Sjogren syndrome efficacy."],
}
