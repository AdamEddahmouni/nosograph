"""Glioblastoma (GBM) disease configuration.

Curated neuro-oncology parameters for Glioblastoma Multiforme.
"""

PIPELINE_LABEL = "Glioblastoma Multiforme"
DEFAULT_SAMPLE_SIZE = 50

# ── Symptoms (used by adverse_events/profiler.py) ────────────────────────
SYMPTOMS = [
    "progressive morning headaches",
    "focal neurological deficits (weakness, numbness)",
    "new-onset adult seizures",
    "cognitive decline and personality changes",
    "aphasia and speech difficulties",
    "visual field cuts and diplopia",
    "increased intracranial pressure (ICP)",
    "nausea and projectile vomiting",
    "papilledema on fundoscopic exam",
    "gait disturbance and ataxia",
    "memory loss and confusion",
    "hemiparesis or hemiplegia",
    "somnolence and altered mental status",
]

# ── Literature Mining ────────────────────────────────────────────────────
PUBMED_QUERIES = [
    "(Glioblastoma[Title/Abstract] OR GBM[Title/Abstract]) AND (treatment[Title/Abstract] OR chemotherapy[Title/Abstract])",
    "(Glioblastoma[Title/Abstract] OR GBM[Title/Abstract]) AND (temozolomide[Title/Abstract] OR MGMT[Title/Abstract] OR EGFRvIII[Title/Abstract])",
    "(Glioblastoma[Title/Abstract]) AND (blood-brain barrier[Title/Abstract] OR convection enhanced delivery[Title/Abstract])",
    "(Glioblastoma[Title/Abstract]) AND (clinical trial[Title/Abstract])",
]

# ── Clinical trials / GWAS search terms ────────────────────────────────
TRIAL_QUERY = "Glioblastoma OR Glioblastoma Multiforme OR GBM OR High-Grade Glioma"
GWAS_SEARCH_TERMS = ["glioblastoma", "glioma", "astrocytoma", "brain tumor"]

# ── CAR-T & Target Scoring Tables ───────────────────────────────────────
CAR_T_SCORES = {
    "GLIOMA_CELL_SURFACE_ANTIGENS": {
        "EGFR": 10.0,
        "IL13RA2": 10.0,
        "HER2": 9.5,
        "ERBB2": 9.5,
        "EPHA2": 9.0,
        "CD276": 9.0,
        "CSPG4": 8.5,
    },
    "TUMOR_SUPPRESSORS_AND_EPIGENETICS": {
        "MGMT": 10.0,
        "PTEN": 9.5,
        "TP53": 9.0,
        "IDH1": 9.5,
        "IDH2": 8.5,
        "TERT": 9.5,
        "ATRX": 8.5,
    },
    "RECEPTOR_TYROSINE_KINASE_DRIVERS": {
        "PDGFRA": 9.5,
        "MET": 9.0,
        "FGFR1": 8.5,
        "PIK3CA": 9.0,
        "PIK3R1": 8.5,
        "AKT1": 8.5,
    },
    "ANGIOGENIC_VASCULAR_PROLIFERATION": {
        "VEGFA": 9.5,
        "KDR": 9.0,
        "FLT1": 8.5,
        "HIF1A": 8.5,
    },
    "IMMUNOSUPPRESSIVE_MICROENVIRONMENT": {
        "TGFB1": 8.5,
        "TGFB2": 8.5,
        "CD274": 9.0,
        "STAT3": 9.0,
        "IDO1": 8.0,
    },
}

# ── Drug Safety Risk Tiers ──────────────────────────────────────────────
DRUG_SAFETY_RISK = {
    "high_risk": [
        "Temozolomide (Severe Myelosuppression / Thrombocytopenia, Pneumocystis pneumonia)",
        "Lomustine (Delayed cumulative bone marrow suppression, Pulmonary fibrosis)",
    ],
    "moderate_risk": [
        "Bevacizumab (Intracranial hemorrhage, Hypertension, Thromboembolism)",
        "Regorafenib (Severe hepatotoxicity, Hemorrhage, Hand-foot skin reaction)",
    ],
    "low_risk": [
        "Dexamethasone edema taper",
        "Levetiracetam seizure prophylaxis",
    ],
}
DISEASE_SPECIFIC_RISK = DRUG_SAFETY_RISK
DRUG_INDUCED_LUPUS_RISK = DRUG_SAFETY_RISK

SCREENING_PROFILE = {
    "strategy_id": "glioblastoma-screening-v1",
    "pathway_keywords": [
        "egfr",
        "mgmt",
        "glioma",
        "pi3k",
        "akt",
        "mtor",
        "blood-brain barrier",
        "angiogenesis",
        "vegf",
    ],
    "mechanism_keywords": [
        "alkylating agent",
        "egfr inhibitor",
        "vegf inhibitor",
        "kinase inhibitor",
        "dna methylator",
        "bbb penetrating",
    ],
    "reference_drug_ids": [
        "CHEMBL1201583",
        "CHEMBL513",
        "CHEMBL1946170",
        "CHEMBL939",
        "CHEMBL481",
    ],
    "weights": {
        "binding_estimate": 0.30,
        "druglikeness": 0.20,
        "target_complementarity": 0.25,
        "similarity_score": 0.15,
        "novelty_score": 0.10,
    },
    "source": "curated_glioblastoma_knowledge_graph",
    "curated_inputs": ["pathways", "drugs", "screening_strategy"],
    "inferred_inputs": ["mechanism_keyword_matching", "property_based_binding_estimate"],
    "limitations": [
        "Property scores are heuristic prioritization signals, not experimental binding affinity or CNS penetration."
    ],
}
