"""SSc (Systemic Sclerosis/Scleroderma) disease configuration."""

PIPELINE_LABEL = "Systemic Sclerosis (SSc)"
DEFAULT_SAMPLE_SIZE = 40

SYMPTOMS = [
    "skin thickening", "skin tightening", "Raynaud's phenomenon",
    "digital ulcers", "telangiectasia", "calcinosis",
    "interstitial lung disease", "pulmonary fibrosis",
    "pulmonary arterial hypertension", "scleroderma renal crisis",
    "gastroesophageal reflux", "dysphagia",
    "esophageal dysmotility", "gastric antral vascular ectasia",
    "arthralgia", "myalgia", "muscle weakness",
    "joint contractures", "fatigue", "weight loss",
    "cardiomyopathy", "heart failure", "arrhythmias",
    "pericarditis", "sicca symptoms",
]

PUBMED_QUERIES = [
    "(systemic sclerosis[Title/Abstract]) AND (treatment[Title/Abstract])",
    "(scleroderma[Title/Abstract]) AND (therapy[Title/Abstract])",
    "(systemic sclerosis[Title/Abstract]) AND (biomarker[Title/Abstract])",
    "(scleroderma[Title/Abstract]) AND (clinical trial[Title/Abstract])",
]

CAR_T_SCORES = {}
DRUG_INDUCED_LUPUS_RISK = {"high_risk": [], "moderate_risk": [], "low_risk": []}
