"""T1D (Type 1 Diabetes) disease configuration."""

PIPELINE_LABEL = "Type 1 Diabetes (T1D)"
DEFAULT_SAMPLE_SIZE = 50

SYMPTOMS = [
    "hyperglycemia", "polyuria", "polydipsia", "polyphagia",
    "weight loss", "fatigue", "blurred vision",
    "diabetic ketoacidosis", "nausea", "vomiting",
    "abdominal pain", "ketones in urine",
    "hypoglycemia unawareness", "neuropathy",
    "nephropathy", "retinopathy", "cardiovascular complications",
    "recurrent infections", "slow wound healing",
]

PUBMED_QUERIES = [
    "(type 1 diabetes[Title/Abstract]) AND (treatment[Title/Abstract])",
    "(type 1 diabetes[Title/Abstract]) AND (immunotherapy[Title/Abstract])",
    "(T1D[Title/Abstract]) AND (biomarker[Title/Abstract])",
    "(type 1 diabetes[Title/Abstract]) AND (clinical trial[Title/Abstract])",
]

CAR_T_SCORES = {}
DRUG_INDUCED_LUPUS_RISK = {"high_risk": [], "moderate_risk": [], "low_risk": []}
