"""PD disease configuration."""

PIPELINE_LABEL = "PD"
DEFAULT_SAMPLE_SIZE = 50

# Minimal symptom list
SYMPTOMS = []

PUBMED_QUERIES = []
TRIAL_QUERY = "PD"
GWAS_SEARCH_TERMS = []

CAR_T_SCORES = {
    "pd_cat1": [
        "GENE1",
        "GENE2"
    ],
    "pd_cat2": [
        "GENE3",
        "GENE4"
    ],
    "pd_cat3": [
        "GENE5"
    ],
    "pd_cat4": [
        "GENE6",
        "GENE7",
        "GENE8"
    ],
    "pd_cat5": [
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
