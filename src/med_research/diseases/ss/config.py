"""SS (Sjogren's Syndrome) disease configuration."""

PIPELINE_LABEL = "Sjogren's Syndrome (SS)"
DEFAULT_SAMPLE_SIZE = 40

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
    "(Sjogren's syndrome[Title/Abstract]) AND (treatment[Title/Abstract])",
    "(Sjogren's syndrome[Title/Abstract]) AND (therapy[Title/Abstract])",
    "(Sjogren's[Title/Abstract]) AND (biomarker[Title/Abstract])",
]

CAR_T_SCORES = {}
DRUG_INDUCED_LUPUS_RISK = {"high_risk": [], "moderate_risk": [], "low_risk": []}
