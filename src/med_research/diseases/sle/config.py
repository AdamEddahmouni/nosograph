"""SLE (Systemic Lupus Erythematosus) disease configuration.

Disease-specific parameters used by the research pipeline modules.
"""

# ── Disease Profile Overrides ────────────────────────────────────────────

PIPELINE_LABEL = "Lupus (SLE)"
DEFAULT_SAMPLE_SIZE = 50

# ── Symptoms (used by adverse_events/profiler.py) ────────────────────────

SYMPTOMS = [
    "fatigue",
    "arthralgia",
    "arthritis",
    "joint pain",
    "rash",
    "photosensitivity",
    "malar rash",
    "discoid rash",
    "renal impairment",
    "nephritis",
    "proteinuria",
    "anemia",
    "leukopenia",
    "thrombocytopenia",
    "neuropsychiatric",
    "seizure",
    "psychosis",
    "cognitive dysfunction",
    "fever",
    "weight loss",
    "myalgia",
    "serositis",
    "pleuritis",
    "pericarditis",
    "oral ulcers",
    "nasal ulcers",
    "alopecia",
    "Raynaud's phenomenon",
    "vasculitis",
    "lymphadenopathy",
    "splenomegaly",
    "hepatitis",
    "pancreatitis",
    "myocarditis",
    "pneumonitis",
    "hematuria",
    "headache",
    "mood disorder",
    "anxiety",
    "depression",
    "peripheral neuropathy",
    "cranial neuropathy",
    "transverse myelitis",
    "aseptic meningitis",
    "cerebrovascular accident",
    "venous thromboembolism",
    "pulmonary embolism",
    "deep vein thrombosis",
    "antiphospholipid syndrome",
    "livedo reticularis",
]

# ── CAR-T Scoring Tables (used by car_t_predictor/predictor.py) ──────────

CAR_T_SCORES = {
    "B_CELL_DEPENDENCY": {
        "CD20": 10.0, "MS4A1": 10.0, "CD19": 10.0,
        "BLK": 9.5, "BANK1": 9.0, "BTK": 9.5,
        "BAFF": 9.0, "TNFSF13B": 9.0, "PRDM1": 9.0,
        "IKZF1": 8.5, "IKZF3": 8.5,
        "PTPN22": 8.0, "UBE2L3": 7.5,
        "CD40L": 7.0, "CD40LG": 7.0, "TNFSF4": 6.5,
        "HLA-DRB1": 6.0, "IRF5": 5.5, "STAT4": 5.5,
        "TLR7": 5.0, "TLR9": 5.0, "MYD88": 4.5,
        "IRAK4": 4.5, "IRF7": 4.0, "TYK2": 4.0,
        "JAK1": 4.0, "TNFAIP3": 5.5, "TNIP1": 5.0,
        "FCGR2A": 3.0, "FCGR3A": 3.0, "ITGAM": 3.0,
        "ELMO1": 2.0, "C1QA": 1.0, "C2": 1.0, "C4A": 1.0,
        "ATG5": 3.0, "IMPDH": 6.0, "Calcineurin": 4.0,
        "Glucocorticoid Receptor": 5.0, "IFNAR1": 4.5,
    },
    "AUTOANTIBODY_ASSOCIATION": {
        "BAFF": 10.0, "TNFSF13B": 10.0, "PRDM1": 9.5,
        "CD40L": 9.0, "CD40LG": 9.0, "IKZF3": 9.0,
        "UBE2L3": 8.5, "TLR7": 8.5, "TLR9": 8.0,
        "BLK": 8.0, "BANK1": 8.0, "BTK": 8.0,
        "IKZF1": 8.0, "IRF5": 7.5, "HLA-DRB1": 7.5,
        "CD20": 7.0, "CD19": 7.0, "MS4A1": 7.0,
        "MYD88": 7.0, "IRAK4": 6.5, "TNFSF4": 7.0,
        "PTPN22": 6.5, "STAT4": 6.0, "TNFAIP3": 6.0,
        "TNIP1": 5.5, "TYK2": 5.5, "JAK1": 5.0,
        "IRF7": 5.0, "FCGR2A": 4.0, "FCGR3A": 4.0,
        "ITGAM": 3.5, "C1QA": 3.0, "C2": 3.0, "C4A": 3.0,
        "ELMO1": 2.0, "ATG5": 3.5, "IMPDH": 5.5,
        "Calcineurin": 4.0, "Glucocorticoid Receptor": 4.0,
        "IFNAR1": 5.0,
    },
    "PLASMA_CELL_RELEVANCE": {
        "PRDM1": 10.0, "IKZF3": 10.0, "IKZF1": 9.5,
        "UBE2L3": 9.0, "BAFF": 9.0, "TNFSF13B": 9.0,
        "CD19": 8.5, "CD20": 8.0, "MS4A1": 8.0,
        "BTK": 7.5, "BLK": 7.0, "CD40L": 7.0,
        "CD40LG": 7.0, "BANK1": 6.5, "TNFSF4": 6.0,
        "HLA-DRB1": 5.5, "TLR7": 5.0, "TLR9": 5.0,
        "MYD88": 4.5, "IRAK4": 4.0, "PTPN22": 5.5,
        "IMPDH": 5.0, "STAT4": 4.5, "IRF5": 4.0,
        "IRF7": 3.5, "TYK2": 3.0, "JAK1": 3.0,
        "TNFAIP3": 4.5, "TNIP1": 4.0,
        "FCGR2A": 2.0, "FCGR3A": 2.0, "ITGAM": 2.0,
        "ELMO1": 1.0, "C1QA": 1.0, "C2": 1.0, "C4A": 1.0,
        "ATG5": 2.5, "Calcineurin": 3.5,
        "Glucocorticoid Receptor": 4.0, "IFNAR1": 3.5,
    },
    "CD19_TARGETING": {
        "CD19": 10.0, "CD20": 9.5, "MS4A1": 9.5,
        "BLK": 9.0, "BTK": 9.0, "BANK1": 8.5,
        "BAFF": 8.5, "TNFSF13B": 8.5, "PRDM1": 9.0,
        "IKZF1": 8.5, "IKZF3": 8.5, "PTPN22": 8.0,
        "UBE2L3": 8.0, "CD40L": 7.5, "CD40LG": 7.5,
        "TNFSF4": 6.5, "HLA-DRB1": 6.0, "IMPDH": 6.0,
        "TLR7": 5.0, "TLR9": 5.0, "MYD88": 4.5,
        "IRAK4": 4.0, "IRF5": 5.5, "STAT4": 5.0,
        "IRF7": 4.0, "TYK2": 4.0, "JAK1": 4.0,
        "TNFAIP3": 5.5, "TNIP1": 5.0,
        "FCGR2A": 3.0, "FCGR3A": 3.0, "ITGAM": 3.0,
        "ELMO1": 2.0, "C1QA": 2.0, "C2": 2.0, "C4A": 2.0,
        "ATG5": 3.5, "Calcineurin": 4.0,
        "Glucocorticoid Receptor": 5.0, "IFNAR1": 5.5,
    },
    "CAR_T_EVIDENCE": {
        "CD19": 10.0, "CD20": 9.5, "MS4A1": 9.5,
        "PRDM1": 8.0, "BLK": 7.5, "BTK": 7.5,
        "BAFF": 7.0, "TNFSF13B": 7.0, "IKZF3": 7.0,
        "IKZF1": 6.5, "BANK1": 6.0, "PTPN22": 6.0,
        "UBE2L3": 5.5, "CD40L": 5.5, "CD40LG": 5.5,
        "HLA-DRB1": 5.0, "IMPDH": 5.0, "TNFSF4": 4.5,
        "TLR7": 4.0, "TLR9": 4.0, "IRF5": 3.5,
        "STAT4": 3.5, "IRF7": 3.0, "TYK2": 3.0,
        "JAK1": 3.0, "MYD88": 3.0, "IRAK4": 2.5,
        "TNFAIP3": 3.5, "TNIP1": 3.0,
        "FCGR2A": 2.0, "FCGR3A": 2.0, "ITGAM": 2.0,
        "ELMO1": 1.0, "C1QA": 1.0, "C2": 1.0, "C4A": 1.0,
        "ATG5": 2.0, "Calcineurin": 3.0,
        "Glucocorticoid Receptor": 4.0, "IFNAR1": 4.5,
    },
}

# ── Literature Mining ────────────────────────────────────────────────────

PUBMED_QUERIES = [
    "(systemic lupus erythematosus[Title/Abstract]) AND (treatment[Title/Abstract])",
    "(lupus nephritis[Title/Abstract]) AND (therapy[Title/Abstract])",
    "(SLE[Title/Abstract]) AND (biomarker[Title/Abstract])",
    "(lupus[Title/Abstract]) AND (genetics[Title/Abstract] OR genomics[Title/Abstract])",
    "(systemic lupus erythematosus[Title/Abstract]) AND (clinical trial[Title/Abstract])",
]

# ── Drug-Induced Lupus Risk ──────────────────────────────────────────────

DRUG_INDUCED_LUPUS_RISK = {
    "high_risk": [
        "hydralazine", "procainamide", "isoniazid", "minocycline",
        "anti-TNF", "infliximab", "adalimumab", "etanercept",
        "interferon-alpha", "interferon-beta",
    ],
    "moderate_risk": [
        "penicillamine", "methyldopa", "quinidine", "chlorpromazine",
        "carbamazepine", "phenytoin", "propylthiouracil",
        "sulfasalazine", "terbinafine",
    ],
    "low_risk": [
        "statins", "ACE inhibitors", "proton pump inhibitors",
        "oral contraceptives", "NSAIDs",
    ],
}
