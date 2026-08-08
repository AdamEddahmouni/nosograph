"""Autoimmune disease configuration — SSC (Systemic Sclerosis (SSc)).

Disease-specific parameters used by the research pipeline modules.
CAR_T_SCORES and DRUG_INDUCED_LUPUS_RISK are derived from the
disease knowledge graph (genes.json) using a documented rubric; see
scripts/populate_disease_configs.py for the scoring rules.
"""

PIPELINE_LABEL = "Systemic Sclerosis (SSc)"
DEFAULT_SAMPLE_SIZE = 50

SYMPTOMS = [
    "skin thickening", "skin tightening", "Raynaud's phenomenon",
    "digital ulcers", "telangiectasia", "calcinosis",
    "interstitial lung disease", "pulmonary fibrosis",
    "pulmonary arterial hypertension", "scleroderma renal crisis",
    "gastroesophageal reflux", "dysphagia",
    "esophageal dysmotility", "gastric antral vascular ectasia",
    "arthralgia", "myalgia", "muscle weakness",
    "joint contractures", "fatigue", "weight loss",
    "cardiomyopathy", "heart failure", "arrhythmias",
    "pericarditis", "sicca symptoms",
]

PUBMED_QUERIES = [
    "(systemic sclerosis[Title/Abstract] OR scleroderma[Title/Abstract]) AND (treatment[Title/Abstract])",
    "(systemic sclerosis[Title/Abstract]) AND (genetics[Title/Abstract] OR genomics[Title/Abstract])",
    "(systemic sclerosis[Title/Abstract]) AND (clinical trial[Title/Abstract])",
    "(systemic sclerosis[Title/Abstract]) AND (biomarker[Title/Abstract])",
]

CAR_T_SCORES = {
    "Apoptotic Clearance / Innate Immunity": {
        "DNASE1L3": 4.5,
    },
    "B Cell Signaling": {
        "BANK1": 9.0,
        "BLK": 9.0,
        "FCGR2B": 9.0,
    },
    "Cytokine / Tfh-B Cell Axis": {
        "IL21": 9.0,
    },
    "Cytokine / Th1 Polarization": {
        "IL12A": 4.0,
    },
    "Fibrosis / Adipogenesis": {
        "PPARG": 4.0,
    },
    "Fibrosis / ECM Component": {
        "COL1A1": 4.0,
    },
    "Fibrosis / ECM Remodeling": {
        "SERPINE1": 4.0,
    },
    "Fibrosis / TGF-β Signaling": {
        "CTGF": 4.0,
        "SMAD3": 4.0,
        "TGFB1": 4.0,
    },
    "IL-6 / JAK-STAT": {
        "IL6": 6.0,
    },
    "Innate Immune / TLR Signaling": {
        "TLR2": 4.5,
        "TLR7": 4.5,
    },
    "JAK-STAT Signaling": {
        "STAT4": 6.0,
        "TYK2": 6.0,
    },
    "MHC / Antigen Presentation": {
        "HLA-DPB1": 6.5,
    },
    "NF-κB Pathway": {
        "TNFAIP3": 5.5,
        "TNIP1": 5.5,
    },
    "T Cell Costimulation": {
        "CTLA4": 7.0,
        "TNFSF4": 7.0,
    },
    "T Cell Signaling": {
        "CD247": 6.0,
        "PTPN22": 6.0,
    },
    "Treg / Immune Regulation": {
        "FOXP3": 8.0,
    },
    "Type I Interferon Pathway": {
        "IRF5": 5.0,
        "IRF8": 5.0,
    },
}

DRUG_SAFETY_RISK = {
    "high_risk": [
        "bleomycin",
        "interferon-alpha",
        "checkpoint inhibitors",
        "paclitaxel (scleroderma-like)",
    ],
    "moderate_risk": [
        "gemcitabine",
        "penicillamine",
        "bromocriptine",
    ],
    "low_risk": [
        "proton pump inhibitors",
        "calcium channel blockers",
        "iloprost",
    ],
}

# ── Clinical trials / GWAS search terms ────────────────────────────────
TRIAL_QUERY = "systemic sclerosis OR scleroderma OR SSc"
GWAS_SEARCH_TERMS = [
    "systemic sclerosis",
    "scleroderma",
    "SSc",
]

DISEASE_SPECIFIC_RISK = DRUG_SAFETY_RISK
DRUG_INDUCED_LUPUS_RISK = DRUG_SAFETY_RISK

SCREENING_PROFILE = {
    "strategy_id": "ssc-screening-v1",
    "pathway_keywords": ["tgf", "fibrosis", "endothelin", "vasculopathy", "il-6", "jak-stat", "b cell", "tlr"],
    "mechanism_keywords": ["tgf", "fibrosis", "endothelin", "pde5", "il-6", "jak", "cd20", "b cell", "tlr", "antifibrotic"],
    "reference_drug_ids": ["nintedanib", "tocilizumab", "mycophenolate", "bosentan", "sildenafil", "rituximab"],
    "weights": {"binding_estimate": 0.25, "druglikeness": 0.15, "target_complementarity": 0.35, "similarity_score": 0.15, "novelty_score": 0.10},
    "source": "curated_ssc_knowledge_graph",
    "curated_inputs": ["pathways", "drugs", "screening_strategy"],
    "inferred_inputs": ["mechanism_keyword_matching", "property_based_binding_estimate"],
    "limitations": ["Property scores are heuristic prioritization signals and do not establish systemic sclerosis efficacy."],
}
