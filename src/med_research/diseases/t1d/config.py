"""T1D disease configuration."""

PIPELINE_LABEL = "T1D"
DEFAULT_SAMPLE_SIZE = 50

# Minimal symptom list
SYMPTOMS = []

PUBMED_QUERIES = []
TRIAL_QUERY = "T1D"
GWAS_SEARCH_TERMS = []

CAR_T_SCORES = {
    "t1d_cat1": [
        "GENE1",
        "GENE2"
    ],
    "t1d_cat2": [
        "GENE3",
        "GENE4"
    ],
    "t1d_cat3": [
        "GENE5"
    ],
    "t1d_cat4": [
        "GENE6",
        "GENE7",
        "GENE8"
    ],
    "t1d_cat5": [
        "GENE9"
    ]
}
DRUG_SAFETY_RISK = {
    "high_risk": [
        "drugA",
        "drugB"
    ],
    "moderate_risk": [
        "drugC",
        "drugD"
    ],
    "low_risk": [
        "drugE"
    ]
}
DISEASE_SPECIFIC_RISK = DRUG_SAFETY_RISK
DRUG_INDUCED_LUPUS_RISK = DRUG_SAFETY_RISK

SCREENING_PROFILE = {}
