import json
from pathlib import Path

# Load allele definitions (same as in parser)
_DEF_PATH = Path(__file__).parent / "allele_definitions.json"


def _load_definitions():
    with open(_DEF_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


DEFINITIONS = _load_definitions()


# Simplified activity score thresholds based on CPIC guidelines
def _activity_score(gene: str, alleles: list[str]) -> float:
    gene_defs = DEFINITIONS[gene]["alleles"]
    return sum(gene_defs[a]["activity"] for a in alleles)


def phenotype_from_alleles(gene: str, alleles: list[str]):
    """Return CPIC phenotype string for a gene based on allele activity scores.
    Mapping (simplified):
    - 0.0 → Poor Metabolizer
    - >0.0 and <1.0 → Intermediate Metabolizer
    - >=1.0 and <2.0 → Normal Metabolizer
    - >=2.0 and <3.0 → Rapid Metabolizer
    - >0.0 and <=1.5 → Intermediate Metabolizer
    - >1.5 and <=2.5 → Normal Metabolizer
    - >2.5 and <=3.5 → Rapid Metabolizer
    - >3.5 → Ultrarapid Metabolizer
    """
    gene = gene.upper()
    score = _activity_score(gene, alleles)
    if score == 0.0:
        return "Poor Metabolizer"
    if 0.0 < score <= 1.5:
        return "Intermediate Metabolizer"
    if 1.5 < score <= 2.5:
        return "Normal Metabolizer"
    if 2.5 < score <= 3.5:
        return "Rapid Metabolizer"
    if score > 3.5:
        return "Ultrarapid Metabolizer"
    return "Unknown"


# Simple dosing recommendation based on CPIC guidelines
_DOSING_GUIDELINES = {
    "CYP2D6": {
        "Poor Metabolizer": "Consider alternative drug or dose reduction.",
        "Intermediate Metabolizer": "Standard dose, monitor plasma levels.",
        "Normal Metabolizer": "Standard dose.",
        "Rapid Metabolizer": "Standard dose, consider increased monitoring.",
        "Ultrarapid Metabolizer": "Consider dose increase or alternative therapy.",
    },
    "CYP2C19": {
        "Poor Metabolizer": "Avoid drugs metabolized by CYP2C19; use alternative.",
        "Intermediate Metabolizer": "Standard dose, may need monitoring.",
        "Normal Metabolizer": "Standard dose.",
        "Rapid Metabolizer": "Standard dose, monitor efficacy.",
        "Ultrarapid Metabolizer": "Potential dose increase required.",
    },
    "DPYD": {
        "Poor Metabolizer": "Avoid fluoropyrimidines (5-FU/capecitabine) due to life-threatening toxicity risk.",
        "Intermediate Metabolizer": "Reduce fluoropyrimidine starting dose by 50% with therapeutic drug monitoring.",
        "Normal Metabolizer": "Standard weight-based fluoropyrimidine dosing.",
    },
    "TPMT": {
        "Poor Metabolizer": "Drastically reduce thiopurine (azathioprine/6-MP) starting dose by 90% or use alternative.",
        "Intermediate Metabolizer": "Reduce thiopurine starting dose by 30-50% and monitor CBC.",
        "Normal Metabolizer": "Standard thiopurine dosing.",
    },
    "SLCO1B1": {
        "Poor Metabolizer": "High risk of statin-induced myopathy; prescribe lower starting dose of simvastatin or use pravastatin/rosuvastatin.",
        "Intermediate Metabolizer": "Moderate statin myopathy risk; monitor CK and avoid maximum simvastatin doses.",
        "Normal Metabolizer": "Standard statin dosing.",
    },
    "HLA-B": {
        "Poor Metabolizer": "Positive HLA-B*57:01 allele confers high risk of severe hypersensitivity; abacavir contraindicated.",
        "Normal Metabolizer": "Negative HLA-B*57:01; standard abacavir initiation without elevated hypersensitivity risk.",
    },
}


def dosing_recommendation(gene: str, phenotype: str) -> str:
    return _DOSING_GUIDELINES.get(gene.upper(), {}).get(
        phenotype, "No specific recommendation available."
    )
