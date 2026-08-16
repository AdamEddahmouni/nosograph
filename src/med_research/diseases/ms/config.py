"""Autoimmune disease configuration — MS (Multiple Sclerosis (MS)).

Disease-specific parameters used by the research pipeline modules.
CAR_T_SCORES and DRUG_INDUCED_LUPUS_RISK are derived from the
disease knowledge graph (genes.json) using a documented rubric; see
scripts/populate_disease_configs.py for the scoring rules.
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
    "(multiple sclerosis[Title/Abstract]) AND (genetics[Title/Abstract] OR genomics[Title/Abstract])",
    "(multiple sclerosis[Title/Abstract]) AND (clinical trial[Title/Abstract])",
    "(multiple sclerosis[Title/Abstract]) AND (biomarker[Title/Abstract])",
]

CAR_T_SCORES = {
    "Autophagy / Immune Tolerance": {
        "CLEC16A": 4.0,
    },
    "B Cell / Tfh Trafficking": {
        "CXCR5": 9.0,
    },
    "B Cell Survival / BAFF Signaling": {
        "TNFRSF13B": 9.0,
    },
    "Cell Cycle / Remyelination": {
        "EVI5": 4.0,
    },
    "Immune Cell Trafficking": {
        "RGS1": 4.0,
    },
    "JAK-STAT Signaling": {
        "JAK1": 6.0,
        "TYK2": 6.0,
    },
    "JAK-STAT Signaling / Th17": {
        "STAT3": 6.0,
    },
    "Lymphoid Neogenesis / Inflammation": {
        "TNFSF14": 4.0,
    },
    "MAP Kinase / Remyelination": {
        "MAPK1": 4.0,
    },
    "MHC / Antigen Presentation": {
        "HLA-DRB1": 6.5,
    },
    "Myelin Autoantigen": {
        "MBP": 8.5,
        "MOG": 8.5,
    },
    "NK / CD8+ T Cell Activation": {
        "CD226": 4.0,
    },
    "T Cell / Adaptive Immunity": {
        "CD4": 4.0,
        "CD8A": 4.0,
    },
    "T Cell Activation / BBB Trafficking": {
        "CD6": 4.0,
    },
    "T Cell Costimulation": {
        "CD40": 7.0,
        "CD86": 7.0,
    },
    "T Cell Costimulation / Adhesion": {
        "CD58": 7.0,
    },
    "T Cell Signaling": {
        "IL2RA": 6.0,
    },
    "T Cell Survival / Homeostasis": {
        "IL7R": 7.5,
    },
    "T Cell Tolerance / Ubiquitination": {
        "CBLB": 4.0,
    },
    "TNF-alpha Signaling": {
        "TNFRSF1A": 5.5,
    },
    "Th17 / IL-22 Pathway": {
        "IL22RA2": 7.5,
    },
    "Th17 / IL-23 Pathway": {
        "IL23R": 7.5,
    },
    "Type I Interferon Pathway / Myeloid": {
        "IRF8": 5.0,
    },
    "Vitamin D Metabolism": {
        "CYP27B1": 4.0,
    },
}

DRUG_SAFETY_RISK = {
    "high_risk": [
        "interferon-beta",
        "natalizumab (PML)",
        "fingolimod (rebound)",
        "alemtuzumab (secondary autoimmunity)",
    ],
    "moderate_risk": [
        "dimethyl fumarate",
        "teriflunomide",
        "cladribine",
    ],
    "low_risk": [
        "glatiramer acetate",
        "methylprednisolone",
        "interferon-beta (limited)",
    ],
}

# ── Clinical trials / GWAS search terms ────────────────────────────────
TRIAL_QUERY = "multiple sclerosis OR MS"
GWAS_SEARCH_TERMS = [
    "multiple sclerosis",
    "MS",
]

DISEASE_SPECIFIC_RISK = DRUG_SAFETY_RISK
DRUG_INDUCED_LUPUS_RISK = DRUG_SAFETY_RISK

SCREENING_PROFILE = {
    "strategy_id": "ms-screening-v1",
    "pathway_keywords": ["b cell", "s1p", "integrin", "bbb", "th17", "nrf2", "interferon", "btk"],
    "mechanism_keywords": ["cd20", "b cell", "s1p", "integrin", "vla-4", "nrf2", "btk", "ifn", "th17"],
    "reference_drug_ids": ["ocrelizumab", "natalizumab", "fingolimod", "dimethyl_fumarate", "teriflunomide", "evobrutinib"],
    "weights": {"binding_estimate": 0.25, "druglikeness": 0.15, "target_complementarity": 0.35, "similarity_score": 0.15, "novelty_score": 0.10},
    "source": "curated_ms_knowledge_graph",
    "curated_inputs": ["pathways", "drugs", "screening_strategy"],
    "inferred_inputs": ["mechanism_keyword_matching", "property_based_binding_estimate"],
    "limitations": ["Property scores are heuristic prioritization signals and do not establish MS efficacy or CNS exposure."],
}
