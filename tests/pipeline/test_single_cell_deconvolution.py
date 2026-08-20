from __future__ import annotations

from med_research.pipeline.gene_expression.single_cell import (
    calculate_tau_specificity,
    deconvolve_cell_types,
    get_gene_cell_specificity,
    score_cell_type_specificity_dimension,
)


def test_calculate_tau_specificity_extremes():
    """Verify Tau specificity calculation across edge cases and extremes."""
    # Ubiquitous expression across all cell types -> Tau = 0.0
    ubiquitous = {"type_a": 5.0, "type_b": 5.0, "type_c": 5.0, "type_d": 5.0}
    tau_ubiq = calculate_tau_specificity(ubiquitous)
    assert tau_ubiq == 0.0

    # Exclusive expression in a single cell type -> Tau = 1.0
    exclusive = {"type_a": 10.0, "type_b": 0.0, "type_c": 0.0, "type_d": 0.0}
    tau_excl = calculate_tau_specificity(exclusive)
    assert tau_excl == 1.0

    # Empty or single-item profile
    assert calculate_tau_specificity({}) == 0.0
    assert calculate_tau_specificity({"type_a": 8.0}) == 0.0


def test_get_gene_cell_specificity_canonical():
    """Verify cell specificity lookup for canonical lineage markers."""
    # CD4 should be highly specific to CD4+ T cells
    cd4_spec = get_gene_cell_specificity("CD4")
    assert cd4_spec["gene"] == "CD4"
    assert cd4_spec["top_cell_type"] == "t_cell_cd4"
    assert cd4_spec["tau_specificity"] >= 0.80
    assert cd4_spec["is_cell_type_specific"] is True

    # MS4A1 (CD20) should be highly specific to B cells
    ms4a1_spec = get_gene_cell_specificity("MS4A1")
    assert ms4a1_spec["top_cell_type"] == "b_cell"
    assert ms4a1_spec["tau_specificity"] >= 0.90

    # PECAM1 should be specific to endothelial cells
    pecam_spec = get_gene_cell_specificity("PECAM1")
    assert pecam_spec["top_cell_type"] == "endothelial"


def test_deconvolve_cell_types_mixture():
    """Verify deconvolution and microenvironment composition from gene lists."""
    # Test immune-enriched gene list
    immune_genes = ["CD3D", "CD4", "MS4A1", "CD19", "NCAM1", "CD14", "CD68"]
    result = deconvolve_cell_types(immune_genes)

    assert "proportions" in result
    assert "t_cell_cd4" in result["proportions"]
    assert "b_cell" in result["proportions"]
    assert "monocyte_macrophage" in result["proportions"]
    assert result["microenvironment_score"] > 0.0
    assert result["cellular_entropy"] > 0.0

    # Empty list
    empty_res = deconvolve_cell_types([])
    assert empty_res["dominant_cell_type"] == "unknown"
    assert empty_res["microenvironment_score"] == 0.0


def test_score_cell_type_specificity_dimension():
    """Verify drug target cell-type specificity dimension calculation."""
    # Specific targets (CD4, MS4A1) should score high
    high_score = score_cell_type_specificity_dimension(["CD4", "MS4A1"])
    assert high_score >= 7.0

    # Empty targets return baseline 5.0
    assert score_cell_type_specificity_dimension([]) == 5.0

    # Targeted alignment with disease cell types
    aligned_score = score_cell_type_specificity_dimension(["MS4A1"], disease_cell_types=["b_cell"])
    unaligned_score = score_cell_type_specificity_dimension(
        ["MS4A1"], disease_cell_types=["endothelial"]
    )
    assert aligned_score > unaligned_score
