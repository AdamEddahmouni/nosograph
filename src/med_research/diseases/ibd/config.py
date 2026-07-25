"""IBD (Inflammatory Bowel Disease) disease configuration."""

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
    "(inflammatory bowel disease[Title/Abstract]) AND (treatment[Title/Abstract])",
    "(Crohn's disease[Title/Abstract]) AND (therapy[Title/Abstract])",
    "(ulcerative colitis[Title/Abstract]) AND (biomarker[Title/Abstract])",
    "(IBD[Title/Abstract]) AND (clinical trial[Title/Abstract])",
]

CAR_T_SCORES = {}
DRUG_INDUCED_LUPUS_RISK = {"high_risk": [], "moderate_risk": [], "low_risk": []}
