"""MS (Multiple Sclerosis) disease configuration.

Disease-specific parameters used by the research pipeline modules.
"""

PIPELINE_LABEL = "Multiple Sclerosis (MS)"
DEFAULT_SAMPLE_SIZE = 50

SYMPTOMS = [
    "fatigue", "vision problems", "optic neuritis",
    "numbness", "tingling", "muscle weakness",
    "spasticity", "balance problems", "coordination problems",
    "tremor", "bladder dysfunction", "bowel dysfunction",
    "cognitive impairment", "memory problems",
    "depression", "anxiety", "pain", "dizziness",
    "speech difficulties", "swallowing difficulties",
    "heat sensitivity", "seizures", "hearing loss",
]

PUBMED_QUERIES = [
    "(multiple sclerosis[Title/Abstract]) AND (treatment[Title/Abstract])",
    "(multiple sclerosis[Title/Abstract]) AND (therapy[Title/Abstract])",
    "(multiple sclerosis[Title/Abstract]) AND (biomarker[Title/Abstract])",
    "(MS[Title/Abstract]) AND (genetics[Title/Abstract])",
    "(multiple sclerosis[Title/Abstract]) AND (clinical trial[Title/Abstract])",
]

CAR_T_SCORES = {}
DRUG_INDUCED_LUPUS_RISK = {"high_risk": [], "moderate_risk": [], "low_risk": []}
