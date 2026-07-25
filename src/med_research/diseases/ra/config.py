"""RA (Rheumatoid Arthritis) disease configuration.

Disease-specific parameters used by the research pipeline modules.
"""

PIPELINE_LABEL = "Rheumatoid Arthritis (RA)"
DEFAULT_SAMPLE_SIZE = 50

SYMPTOMS = [
    "joint pain", "joint swelling", "morning stiffness",
    "fatigue", "fever", "weight loss", "rheumatoid nodules",
    "synovitis", "bone erosion", "cartilage loss",
    "decreased range of motion", "symmetrical arthritis",
    "hand deformities", "foot deformities",
    "extra-articular manifestations", "vasculitis",
    "pleuritis", "pericarditis", "interstitial lung disease",
    "anemia", "thrombocytosis", "osteoporosis",
    "cardiovascular disease", "Sjogren's syndrome",
]

PUBMED_QUERIES = [
    "(rheumatoid arthritis[Title/Abstract]) AND (treatment[Title/Abstract])",
    "(rheumatoid arthritis[Title/Abstract]) AND (therapy[Title/Abstract])",
    "(RA[Title/Abstract]) AND (biomarker[Title/Abstract])",
    "(rheumatoid arthritis[Title/Abstract]) AND (genetics[Title/Abstract])",
    "(rheumatoid arthritis[Title/Abstract]) AND (clinical trial[Title/Abstract])",
]

CAR_T_SCORES = {}
DRUG_INDUCED_LUPUS_RISK = {"high_risk": [], "moderate_risk": [], "low_risk": []}
