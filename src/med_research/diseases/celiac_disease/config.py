"""Celiac Disease configuration.

Disease-specific parameters used by research pipeline modules.
"""

PIPELINE_LABEL = "Celiac Disease"
DEFAULT_SAMPLE_SIZE = 50

# ── Symptoms (used by adverse_events/profiler.py) ────────────────────────
SYMPTOMS = [
    "chronic diarrhea",
    "steatorrhea (pale, foul-smelling, fatty stools)",
    "abdominal distension and bloating",
    "cramping abdominal pain and flatulence",
    "unexplained weight loss",
    "malabsorption of fat-soluble vitamins and calcium",
    "iron-deficiency anemia refractory to oral iron",
    "profound chronic fatigue and weakness",
    "dermatitis herpetiformis (intensely pruritic vesicular eruption on extensor surfaces)",
    "early osteopenia and osteoporosis",
    "elevated transaminases (celiac hepatitis)",
    "recurrent aphthous oral ulcerations",
    "gluten ataxia and peripheral neuropathy"
]

# ── Literature Mining ────────────────────────────────────────────────────
PUBMED_QUERIES = [
    "(celiac disease[Title/Abstract] OR coeliac disease[Title/Abstract] OR gluten enteropathy[Title/Abstract]) AND (treatment[Title/Abstract] OR therapeutics[Title/Abstract])",
    "(celiac disease[Title/Abstract]) AND (gluten-free diet[Title/Abstract] OR larazotide[Title/Abstract] OR latiglutenase[Title/Abstract] OR transglutaminase[Title/Abstract])",
    "(celiac disease[Title/Abstract]) AND (villous atrophy[Title/Abstract] OR intraepithelial lymphocytes[Title/Abstract] OR IL-15[Title/Abstract])",
    "(celiac disease[Title/Abstract]) AND (clinical trial[Title/Abstract])"
]

# ── Clinical trials / GWAS search terms ────────────────────────────────
TRIAL_QUERY = "Celiac Disease OR Coeliac Disease OR Refractory Celiac Disease OR Gluten Sensitivity"
GWAS_SEARCH_TERMS = [
    "celiac disease",
    "malabsorption",
    "type 1 diabetes",
    "autoimmune disease",
    "hemoglobin concentration"
]

# ── CAR-T & Target Scoring Tables ───────────────────────────────────────
CAR_T_SCORES = {
    "HLA_DQ_ANTIGEN_PRESENTATION": {
        "HLA-DQA1": 10.0,
        "HLA-DQB1": 10.0,
        "TGM2": 10.0,
        "CD4": 9.5,
        "IL15": 10.0,
        "IL15RA": 9.5
    },
    "INTESTINAL_EPITHELIAL_CYTOTOXICITY": {
        "NKG2D": 9.5,
        "KLRK1": 9.5,
        "MICA": 9.0,
        "IFNG": 9.5,
        "FASLG": 8.5,
        "GZMB": 9.0
    },
    "MUCOSAL_INTEGRITY_BARRIER": {
        "CLDN1": 8.5,
        "OCLN": 8.5,
        "TJP1": 8.5,
        "CDX2": 8.0,
        "MUC2": 8.0
    }
}

# ── Drug Safety Risk Tiers ──────────────────────────────────────────────
DRUG_SAFETY_RISK = {
    "high_risk": [
        "Dapsone in G6PD deficiency (Severe hemolytic anemia, Methemoglobinemia)"
    ],
    "moderate_risk": [
        "Systemic immunosuppressants in refractory celiac (Infection risk, Enteropathy-associated T-cell lymphoma surveillance)"
    ],
    "low_risk": [
        "Strict Gluten-Free Diet",
        "Oral Locally-acting Budesonide",
        "Larazotide Acetate"
    ]
}
DISEASE_SPECIFIC_RISK = DRUG_SAFETY_RISK
DRUG_INDUCED_LUPUS_RISK = DRUG_SAFETY_RISK

SCREENING_PROFILE = {
    "strategy_id": "celiac_disease-screening-v1",
    "reference_drug_ids": [
        "larazotide_acetate",
        "latiglutenase",
        "dapsone",
        "budesonide_oral"
],
    "weights": {
        "binding_estimate": 0.30,
        "druglikeness": 0.20,
        "target_complementarity": 0.25,
        "similarity_score": 0.15,
        "novelty_score": 0.10,
    },
    "source": "curated_celiac_disease_knowledge_graph",
    "curated_inputs": ["pathways", "drugs", "screening_strategy"],
    "inferred_inputs": ["mechanism_keyword_matching", "property_based_binding_estimate"],
    "limitations": [
        "Property scores are heuristic prioritization signals, not experimental binding affinity or efficacy."
    ],
}
