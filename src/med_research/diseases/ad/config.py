"""AD disease configuration."""

PIPELINE_LABEL = "AD"
DEFAULT_SAMPLE_SIZE = 50

# Minimal symptom list
SYMPTOMS = [
    "memory loss",
    "cognitive decline",
    "confusion",
    "disorientation",
    "difficulty with language",
    "behavioral changes",
]

PUBMED_QUERIES = [
    "Alzheimer's Disease therapeutics",
    "Alzheimer amyloid beta tau targets",
]
TRIAL_QUERY = "Alzheimer's Disease"
GWAS_SEARCH_TERMS = ["Alzheimer's disease", "cognitive decline"]

CAR_T_SCORES = {
    "ad_cat1": ["APP", "MAPT"],
    "ad_cat2": ["APOE", "TREM2"],
    "ad_cat3": ["PSEN1"],
    "ad_cat4": ["PSEN2", "BIN1", "CD33"],
    "ad_cat5": ["CLU"],
}
DRUG_SAFETY_RISK = {
    "high_risk": ["drugA", "drugB"],
    "moderate_risk": ["drugC", "drugD"],
    "low_risk": ["drugE"],
}
DISEASE_SPECIFIC_RISK = DRUG_SAFETY_RISK
DRUG_INDUCED_LUPUS_RISK = DRUG_SAFETY_RISK

SCREENING_PROFILE = {
    "disease_id": "ad",
    "screening_ready": True,
    "similarity_threshold": 0.5,
}
