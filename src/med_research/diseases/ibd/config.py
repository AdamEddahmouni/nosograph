"""Autoimmune disease configuration — IBD (Inflammatory Bowel Disease (IBD)).

Disease-specific parameters used by the research pipeline modules.
CAR_T_SCORES and DRUG_INDUCED_LUPUS_RISK are derived from the
disease knowledge graph (genes.json) using a documented rubric; see
scripts/populate_disease_configs.py for the scoring rules.
"""

PIPELINE_LABEL = "Inflammatory Bowel Disease (IBD)"
DEFAULT_SAMPLE_SIZE = 50

SYMPTOMS = [
    "abdominal pain", "diarrhea", "bloody stool",
    "rectal bleeding", "urgency", "tenesmus",
    "fatigue", "weight loss", "fever",
    "anemia", "nausea", "vomiting",
    "loss of appetite", "malabsorption",
    "fistulas", "abscesses", "strictures",
    "bowel obstruction", "extraintestinal manifestations",
    "arthritis", "uveitis", "erythema nodosum",
    "pyoderma gangrenosum", "primary sclerosing cholangitis",
    "growth failure in children",
]

PUBMED_QUERIES = [
    "(IBD[Title/Abstract]) AND (treatment[Title/Abstract])",
    "(IBD[Title/Abstract]) AND (genetics[Title/Abstract])",
    "(IBD[Title/Abstract]) AND (clinical trial[Title/Abstract])",
]

CAR_T_SCORES = {
    "Anti-inflammatory / Regulatory Cytokine": {
        "IL10": 4.0,
        "IL10RA": 4.0,
    },
    "Autophagy / Epithelial Barrier": {
        "ATG16L1": 4.0,
        "IRGM": 4.0,
    },
    "Autophagy / Innate Immunity": {
        "LRRK2": 4.5,
    },
    "Epithelial Barrier / Microbiome": {
        "FUT2": 4.0,
    },
    "Epithelial Barrier / Tight Junctions": {
        "HNF4A": 4.0,
    },
    "Epithelial Barrier / Wound Healing": {
        "MST1": 4.0,
    },
    "Epithelial Metabolism / IBD5 Locus": {
        "SLC22A5": 4.0,
    },
    "IL-23 / Th17 Axis": {
        "CCR6": 7.5,
        "IL12B": 7.5,
        "IL23R": 7.5,
    },
    "JAK-STAT Signaling": {
        "JAK2": 6.0,
        "STAT3": 6.0,
        "TYK2": 6.0,
    },
    "Lymphocyte Trafficking / Homing": {
        "NKX2-3": 4.0,
    },
    "Pattern Recognition / Epithelial Barrier": {
        "NOD2": 4.0,
    },
    "Pattern Recognition / Innate Immunity": {
        "CARD9": 4.5,
    },
    "T Cell Costimulation / GALT": {
        "ICOSLG": 7.0,
    },
    "T Cell Signaling / Autoimmunity": {
        "PTPN22": 7.0,
    },
    "TGF-beta Signaling / Fibrosis": {
        "SMAD3": 4.0,
    },
    "TNF Superfamily / Mucosal Inflammation": {
        "TNFSF15": 5.5,
    },
    "Th17 / IL-23 Pathway": {
        "IL17A": 7.5,
    },
}

DRUG_INDUCED_LUPUS_RISK = {
    "high_risk": [
        "infliximab",
        "adalimumab",
        "certolizumab",
        "ustekinumab (psoriasiform)",
    ],
    "moderate_risk": [
        "azathioprine",
        "mercaptopurine",
        "methotrexate",
        "tofacitinib",
    ],
    "low_risk": [
        "mesalamine",
        "budesonide",
        "sulfasalazine",
    ],
}
