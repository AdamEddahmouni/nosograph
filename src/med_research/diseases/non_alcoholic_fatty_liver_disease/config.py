"""Non-Alcoholic Steatohepatitis (MASH / NASH) configuration.

Disease-specific parameters used by research pipeline modules.
"""

PIPELINE_LABEL = "Non-Alcoholic Steatohepatitis (MASH / NASH)"
DEFAULT_SAMPLE_SIZE = 50

# ── Symptoms (used by adverse_events/profiler.py) ────────────────────────
SYMPTOMS = [
    "hepatic steatosis (lipid accumulation in hepatocytes)",
    "right upper quadrant abdominal discomfort",
    "fatigue and malaise",
    "hepatomegaly",
    "elevated ALT and AST transaminases",
    "insulin resistance and dyslipidemia",
    "hepatocyte ballooning and lobular inflammation",
    "progressive pericellular and bridging hepatic fibrosis",
    "cirrhosis progression",
    "portal hypertension",
    "spider angiomas and palmar erythema in advanced disease",
    "ascites in decompensated cirrhosis",
]

# ── Literature Mining ────────────────────────────────────────────────────
PUBMED_QUERIES = [
    "(nonalcoholic fatty liver disease[Title/Abstract] OR NAFLD[Title/Abstract] OR NASH[Title/Abstract] OR MASH[Title/Abstract]) AND (treatment[Title/Abstract] OR therapeutics[Title/Abstract])",
    "(NASH[Title/Abstract] OR MASH[Title/Abstract]) AND (resmetirom[Title/Abstract] OR semaglutide[Title/Abstract] OR lanifibranor[Title/Abstract] OR FXR[Title/Abstract])",
    "(NASH[Title/Abstract] OR MASH[Title/Abstract]) AND (liver fibrosis[Title/Abstract] OR steatohepatitis[Title/Abstract])",
    "(NASH[Title/Abstract] OR MASH[Title/Abstract]) AND (clinical trial[Title/Abstract])",
]

# ── Clinical trials / GWAS search terms ────────────────────────────────
TRIAL_QUERY = "NASH OR MASH OR Non-Alcoholic Steatohepatitis OR NAFLD"
GWAS_SEARCH_TERMS = [
    "non-alcoholic fatty liver disease",
    "alanine aminotransferase",
    "liver fat content",
    "cirrhosis",
]

# ── CAR-T & Target Scoring Tables ───────────────────────────────────────
CAR_T_SCORES = {
    "NUCLEAR_RECEPTORS_METABOLISM": {
        "THRB": 10.0,
        "PPARA": 9.5,
        "PPARG": 9.5,
        "PPARD": 9.0,
        "NR1H4": 9.5,
        "NR1H3": 8.5,
    },
    "FIBROGENESIS_STEATOSIS_MEDIATORS": {
        "PNPLA3": 10.0,
        "TM6SF2": 9.5,
        "HSD17B13": 9.0,
        "FGF21": 9.5,
        "FGFR1": 9.0,
        "KLB": 8.5,
    },
    "INFLAMMATORY_CELL_INJURY": {
        "CCR2": 9.0,
        "CCR5": 9.0,
        "ASK1": 8.5,
        "MAP3K5": 8.5,
        "CASP3": 8.0,
        "NLRP3": 8.5,
    },
}

# ── Drug Safety Risk Tiers ──────────────────────────────────────────────
DRUG_SAFETY_RISK = {
    "high_risk": ["Obeticholic Acid in decompensated cirrhosis (Severe hepatotoxicity warning)"],
    "moderate_risk": [
        "Resmetirom (Mild gastrointestinal distress, CYP2C8 interactions)",
        "Pioglitazone (Fluid retention, Weight gain)",
    ],
    "low_risk": ["Semaglutide", "Vitamin E (monitored)"],
}
DISEASE_SPECIFIC_RISK = DRUG_SAFETY_RISK
DRUG_INDUCED_LUPUS_RISK = DRUG_SAFETY_RISK

SCREENING_PROFILE = {
    "strategy_id": "non_alcoholic_fatty_liver_disease-screening-v1",
    "reference_drug_ids": ["resmetirom", "semaglutide", "pioglitazone", "lanifibranor"],
    "weights": {
        "binding_estimate": 0.30,
        "druglikeness": 0.20,
        "target_complementarity": 0.25,
        "similarity_score": 0.15,
        "novelty_score": 0.10,
    },
    "source": "curated_non_alcoholic_fatty_liver_disease_knowledge_graph",
    "curated_inputs": ["pathways", "drugs", "screening_strategy"],
    "inferred_inputs": ["mechanism_keyword_matching", "property_based_binding_estimate"],
    "limitations": [
        "Property scores are heuristic prioritization signals, not experimental binding affinity or efficacy."
    ],
}
