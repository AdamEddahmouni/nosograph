"""GOUT disease configuration."""

PIPELINE_LABEL = "GOUT"
DEFAULT_SAMPLE_SIZE = 50

# Minimal symptom list
SYMPTOMS = []

PUBMED_QUERIES = []
TRIAL_QUERY = "GOUT"
GWAS_SEARCH_TERMS = []

CAR_T_SCORES = {
    "NLRP3 Inflammasome Activation": {
        "IL1B": 4.3,
        "NLRP3": 4.4,
    },
    "Renal Urate Transport": {
        "ABCG2": 4.8,
        "SLC22A12": 4.6,
        "SLC2A9": 5.0,
    },
    "Uncategorized": {
        "A1CF": 4.0,
        "ABCA1": 4.0,
        "ABCA6": 4.0,
        "ADH1B": 4.0,
        "ADO": 4.0,
        "ALDH16A1": 4.0,
        "ALDH2": 4.0,
        "ATRAID": 4.0,
        "ATXN2": 4.0,
        "BCAS3": 4.0,
        "BICC1": 4.0,
        "CPS1": 4.0,
        "CUBN": 4.0,
        "CUX2": 4.0,
        "FST": 4.0,
        "GCKR": 4.0,
        "GIT2": 4.0,
        "HECTD4": 4.0,
        "HLF": 4.0,
        "HNF4A": 4.0,
        "HNF4G": 4.0,
        "IGF1R": 4.0,
        "INHBC": 4.0,
        "KDF1": 4.0,
        "LRP2": 4.0,
        "MAF": 4.0,
        "MLXIP": 4.0,
        "MLXIPL": 4.0,
        "MTX1": 4.0,
        "NR3C1": 4.0,
        "PDZK1": 4.0,
        "PKD2": 4.0,
        "PKLR": 4.0,
        "PNPLA3": 4.0,
        "PRKAG2": 4.0,
        "PTGS1": 4.0,
        "PTGS2": 4.0,
        "PTPN11": 4.0,
        "RREB1": 4.0,
        "SFMBT1": 4.0,
        "SLC16A9": 4.0,
        "SLC22A11": 4.0,
        "SLC22A6": 4.0,
        "SLC22A8": 4.0,
        "TMEM171": 4.0,
        "TUBB": 4.0,
        "TUBB1": 4.0,
        "TUBB2A": 4.0,
        "TUBB2B": 4.0,
        "TUBB3": 4.0,
        "TUBB4A": 4.0,
        "TUBB4B": 4.0,
        "TUBB6": 4.0,
        "TUBB8": 4.0,
        "WDR1": 4.0,
        "XDH": 4.0,
    },
}
DRUG_SAFETY_RISK = {
    "high_risk": [],
    "moderate_risk": [
        "allopurinol",
        "apremilast",
        "arhalofenate",
        "benzbromarone",
        "canakinumab",
        "celecoxib",
        "colchicine",
        "denosumab",
        "diclofenac",
        "febuxostat",
        "indomethacin",
        "lesinurad",
        "methotrexate",
        "methylprednisolone acetate",
        "naproxen",
        "naproxen sodium",
        "prednisone",
        "probenecid",
        "sulfinpyrazone",
        "tislelizumab",
        "triamcinolone acetonide",
        "ulodesine",
    ],
    "low_risk": [],
}

DISEASE_SPECIFIC_RISK = DRUG_SAFETY_RISK
DRUG_INDUCED_LUPUS_RISK = DRUG_SAFETY_RISK

SCREENING_PROFILE = {
    "strategy_id": "gout-screening-v1",
    "pathway_keywords": [
        "activation",
        "glucose",
        "hormone",
        "inflammasome",
        "insulin",
        "intestinal",
        "metabolism",
        "nlrp3",
        "pathway",
        "renal",
    ],
    "mechanism_keywords": [
        "activation",
        "glucose",
        "hormone",
        "inflammasome",
        "insulin",
        "intestinal",
        "metabolism",
        "nlrp3",
        "pathway",
        "renal",
    ],
    "reference_drug_ids": [
        "CHEMBL107",
        "CHEMBL1467",
        "CHEMBL1467",
        "CHEMBL154",
        "CHEMBL6",
        "CHEMBL1164729",
    ],
    "weights": {
        "binding_estimate": 0.25,
        "druglikeness": 0.15,
        "target_complementarity": 0.35,
        "similarity_score": 0.15,
        "novelty_score": 0.1,
    },
    "source": "scaffold_gout_knowledge_graph",
    "curated_inputs": [
        "pathways",
        "drugs",
        "screening_strategy",
    ],
    "inferred_inputs": [
        "mechanism_keyword_matching",
        "property_based_binding_estimate",
    ],
    "limitations": [
        "Property scores are heuristic prioritization signals and do not establish clinical efficacy or safety.",
    ],
}
