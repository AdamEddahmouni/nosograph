"""Single-Cell RNA-seq (scRNA-seq) Cell-Type Deconvolution & Specificity Module.

Provides cell-type signature reference datasets, quantitative Tau (τ) specificity index
computation, cellular composition deconvolution, and microenvironment enrichment profiling.
"""

from __future__ import annotations

import math
from typing import Any

# Curated reference marker gene sets for key biological and tumor microenvironment cell types
CELL_TYPE_MARKERS: dict[str, list[str]] = {
    "t_cell_cd4": ["CD3D", "CD3E", "CD4", "IL7R", "CCR7", "FOXP3", "IL2RA"],
    "t_cell_cd8": ["CD3D", "CD3E", "CD8A", "CD8B", "GZMB", "PRF1", "IFNG"],
    "b_cell": ["MS4A1", "CD19", "CD79A", "CD79B", "BANK1", "PAX5", "SDC1"],
    "nk_cell": ["NCAM1", "NKG7", "GNLY", "KLRD1", "KLRK1", "FCGR3A"],
    "monocyte_macrophage": ["CD14", "FCGR3A", "CD68", "CD163", "MARCO", "CSF1R", "AIF1"],
    "dendritic_cell": ["ITGAX", "HLA-DRA", "HLA-DPA1", "CLEC9A", "CD1C", "LILRA4"],
    "neutrophil": ["FCGR3B", "S100A8", "S100A9", "MPO", "ELANE", "CXCR2"],
    "endothelial": ["PECAM1", "VWF", "CDH5", "KDR", "ENG", "FLT1"],
    "fibroblast": ["COL1A1", "COL1A2", "ACTA2", "FAP", "PDGFRB", "THY1", "POSTN"],
    "epithelial": ["EPCAM", "KRT8", "KRT18", "KRT19", "CDH1", "CLDN4"],
    "tumor_malignant": ["MKI67", "TOP2A", "CCND1", "MYC", "ERBB2", "EGFR", "TP53"],
}

# Baseline normalized expression matrix across major cell types (0.0 to 10.0 scale)
CELL_TYPE_REFERENCE_EXPRESSION: dict[str, dict[str, float]] = {
    "CD4": {
        "t_cell_cd4": 9.5,
        "t_cell_cd8": 0.2,
        "b_cell": 0.1,
        "monocyte_macrophage": 0.8,
        "fibroblast": 0.0,
    },
    "CD8A": {
        "t_cell_cd8": 9.8,
        "t_cell_cd4": 0.1,
        "nk_cell": 2.5,
        "monocyte_macrophage": 0.0,
        "fibroblast": 0.0,
    },
    "MS4A1": {
        "b_cell": 9.9,
        "t_cell_cd4": 0.0,
        "t_cell_cd8": 0.0,
        "monocyte_macrophage": 0.0,
        "fibroblast": 0.0,
    },
    "CD19": {
        "b_cell": 9.7,
        "t_cell_cd4": 0.0,
        "t_cell_cd8": 0.0,
        "monocyte_macrophage": 0.0,
        "fibroblast": 0.0,
    },
    "NCAM1": {
        "nk_cell": 8.9,
        "t_cell_cd8": 1.2,
        "t_cell_cd4": 0.1,
        "monocyte_macrophage": 0.2,
        "fibroblast": 0.0,
    },
    "CD14": {
        "monocyte_macrophage": 9.6,
        "dendritic_cell": 2.1,
        "neutrophil": 3.0,
        "t_cell_cd4": 0.1,
        "b_cell": 0.0,
    },
    "CD68": {
        "monocyte_macrophage": 9.2,
        "dendritic_cell": 3.5,
        "neutrophil": 1.8,
        "t_cell_cd4": 0.0,
        "fibroblast": 0.2,
    },
    "PECAM1": {
        "endothelial": 9.8,
        "monocyte_macrophage": 1.5,
        "t_cell_cd4": 0.1,
        "fibroblast": 0.1,
        "epithelial": 0.0,
    },
    "COL1A1": {
        "fibroblast": 9.9,
        "endothelial": 1.0,
        "epithelial": 0.2,
        "t_cell_cd4": 0.0,
        "b_cell": 0.0,
    },
    "EPCAM": {
        "epithelial": 9.8,
        "tumor_malignant": 8.5,
        "fibroblast": 0.0,
        "endothelial": 0.0,
        "t_cell_cd4": 0.0,
    },
    "TNF": {
        "monocyte_macrophage": 8.5,
        "t_cell_cd4": 6.2,
        "t_cell_cd8": 5.8,
        "nk_cell": 4.5,
        "b_cell": 1.2,
    },
    "IL6": {
        "monocyte_macrophage": 8.2,
        "fibroblast": 6.5,
        "endothelial": 4.1,
        "epithelial": 2.0,
        "t_cell_cd4": 0.5,
    },
    "JAK1": {
        "t_cell_cd4": 7.0,
        "t_cell_cd8": 6.8,
        "b_cell": 6.5,
        "monocyte_macrophage": 7.2,
        "fibroblast": 5.0,
    },
    "JAK2": {
        "monocyte_macrophage": 7.5,
        "endothelial": 5.2,
        "t_cell_cd8": 4.8,
        "fibroblast": 4.0,
        "epithelial": 3.5,
    },
    "EGFR": {
        "epithelial": 8.0,
        "tumor_malignant": 9.2,
        "fibroblast": 3.2,
        "endothelial": 2.1,
        "t_cell_cd4": 0.0,
    },
    "VEGFA": {
        "tumor_malignant": 8.8,
        "fibroblast": 7.5,
        "endothelial": 6.0,
        "monocyte_macrophage": 5.5,
        "t_cell_cd4": 0.2,
    },
    "PDCD1": {
        "t_cell_cd8": 8.5,
        "t_cell_cd4": 7.2,
        "nk_cell": 3.0,
        "b_cell": 1.0,
        "fibroblast": 0.0,
    },
    "CD274": {
        "tumor_malignant": 8.2,
        "monocyte_macrophage": 7.8,
        "dendritic_cell": 6.5,
        "endothelial": 3.0,
        "t_cell_cd4": 0.1,
    },
    "CTLA4": {
        "t_cell_cd4": 8.8,
        "t_cell_cd8": 6.5,
        "b_cell": 0.2,
        "monocyte_macrophage": 0.0,
        "fibroblast": 0.0,
    },
    "CFTR": {
        "epithelial": 9.4,
        "fibroblast": 0.5,
        "endothelial": 0.2,
        "t_cell_cd4": 0.0,
        "monocyte_macrophage": 0.0,
    },
    "HBB": {
        "neutrophil": 0.5,
        "monocyte_macrophage": 0.2,
        "endothelial": 0.0,
        "t_cell_cd4": 0.0,
        "b_cell": 0.0,
    },
    "SMN1": {
        "t_cell_cd4": 6.5,
        "monocyte_macrophage": 6.2,
        "fibroblast": 6.0,
        "epithelial": 5.8,
        "endothelial": 5.5,
    },
    "HTT": {
        "t_cell_cd4": 5.5,
        "fibroblast": 5.8,
        "epithelial": 5.2,
        "monocyte_macrophage": 5.0,
        "endothelial": 4.8,
    },
}


def calculate_tau_specificity(expression_profile: dict[str, float]) -> float:
    """Calculate the Yanai Tau (τ) tissue/cell-type specificity index.

    τ ranges from 0.0 (ubiquitously expressed across all cell types)
    to 1.0 (exclusively expressed in a single cell type).

    Formula:
        τ = Σ (1 - (x_i / x_max)) / (N - 1)
    """
    if not expression_profile or len(expression_profile) <= 1:
        return 0.0

    values = [max(0.0, float(v)) for v in expression_profile.values()]
    max_val = max(values)
    if max_val <= 1e-6:
        return 0.0

    n = len(values)
    normalized = [v / max_val for v in values]
    tau = sum(1.0 - x for x in normalized) / (n - 1)
    return round(max(0.0, min(1.0, tau)), 4)


def get_gene_cell_specificity(gene: str) -> dict[str, Any]:
    """Retrieve single-cell expression distribution, top cell type, and Tau index for a gene."""
    gene_upper = gene.strip().upper()
    profile = CELL_TYPE_REFERENCE_EXPRESSION.get(gene_upper)

    if not profile:
        # Fallback heuristic using marker matching
        matching_cell_types = [
            ct for ct, markers in CELL_TYPE_MARKERS.items() if gene_upper in markers
        ]
        if matching_cell_types:
            top_ct = matching_cell_types[0]
            profile = {ct: 8.0 if ct == top_ct else 0.5 for ct in CELL_TYPE_MARKERS}
        else:
            profile = {ct: 3.0 for ct in list(CELL_TYPE_MARKERS.keys())[:5]}

    tau = calculate_tau_specificity(profile)
    top_cell_type = max(profile.items(), key=lambda x: x[1])[0]
    top_expression = max(profile.values())

    return {
        "gene": gene_upper,
        "tau_specificity": tau,
        "top_cell_type": top_cell_type,
        "top_expression": top_expression,
        "is_cell_type_specific": tau >= 0.60,
        "cell_type_expression": profile,
    }


def deconvolve_cell_types(
    bulk_genes: list[str],
    expression_weights: dict[str, float] | None = None,
) -> dict[str, Any]:
    """Perform marker-based cell type deconvolution from a list of bulk dysregulated genes.

    Returns estimated cellular composition fractions and enrichment scores.
    """
    if not bulk_genes:
        return {
            "proportions": {},
            "dominant_cell_type": "unknown",
            "microenvironment_score": 0.0,
            "cell_type_enrichments": {},
        }

    genes_upper = {g.strip().upper() for g in bulk_genes}
    weights = {k.upper(): float(v) for k, v in (expression_weights or {}).items()}

    cell_scores: dict[str, float] = {}
    cell_matches: dict[str, list[str]] = {}

    for cell_type, markers in CELL_TYPE_MARKERS.items():
        overlap = [m for m in markers if m in genes_upper]
        cell_matches[cell_type] = overlap
        if overlap:
            # Weighted enrichment
            score = sum(weights.get(m, 1.0) for m in overlap) / len(markers)
            cell_scores[cell_type] = score
        else:
            cell_scores[cell_type] = 0.0

    total_score = sum(cell_scores.values())
    if total_score > 0:
        proportions = {
            ct: round(score / total_score, 4) for ct, score in cell_scores.items() if score > 0
        }
    else:
        proportions = {}

    dominant_cell_type = (
        max(proportions.items(), key=lambda x: x[1])[0] if proportions else "unassigned"
    )

    # Compute microenvironment diversity / dysregulation Shannon entropy
    entropy = 0.0
    for p in proportions.values():
        if p > 0:
            entropy -= p * math.log2(p)

    return {
        "proportions": proportions,
        "dominant_cell_type": dominant_cell_type,
        "microenvironment_score": round(min(10.0, total_score * 5.0), 2),
        "cellular_entropy": round(entropy, 3),
        "cell_type_enrichments": {
            ct: {
                "score": round(score, 3),
                "matched_markers": cell_matches[ct],
                "proportion": proportions.get(ct, 0.0),
            }
            for ct, score in cell_scores.items()
            if score > 0
        },
    }


def score_cell_type_specificity_dimension(
    drug_targets: list[str],
    disease_cell_types: list[str] | None = None,
) -> float:
    """Score the Cell Type Specificity dimension (0.0 to 10.0) for drug repurposing.

    Evaluates whether drug targets act selectively within disease-relevant cellular niches
    rather than ubiquitous off-target cell populations.
    """
    if not drug_targets:
        return 5.0  # Neutral baseline

    target_scores: list[float] = []
    relevant_cts = set(disease_cell_types or [])

    for target in drug_targets:
        spec = get_gene_cell_specificity(target)
        tau = spec["tau_specificity"]
        top_ct = spec["top_cell_type"]

        # If disease-relevant cell types are specified, check alignment
        if relevant_cts:
            score = 5.0 + (tau * 5.0) if top_ct in relevant_cts else max(1.0, 5.0 - (tau * 3.0))
        else:
            # High specificity in general is rewarded
            score = 4.0 + (tau * 5.0)

        target_scores.append(score)

    avg_score = sum(target_scores) / len(target_scores)
    return round(max(0.0, min(10.0, avg_score)), 2)
