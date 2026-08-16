"""Unit and integration tests for AlphaFold 3D structure and pocket characterization."""

from __future__ import annotations

from fastapi.testclient import TestClient

from med_research.pipeline.structure_3d.engine import (
    KNOWN_UNIPROT_MAP,
    analyze_structure_3d,
    get_target_3d_structure,
    resolve_uniprot_id,
)
from med_research.web.main import app

client = TestClient(app)


def test_resolve_uniprot_id():
    name, uid = resolve_uniprot_id("UNIPROT:P01375")
    assert uid == "P01375"
    assert name == "TNF"

    name, uid = resolve_uniprot_id("JAK1")
    assert uid == "P23458"
    assert name == "JAK1"

    name, uid = resolve_uniprot_id("GENE:CD19")
    assert uid == "P15391"
    assert name == "CD19"

    # Novel gene fallback
    name, uid = resolve_uniprot_id("UNKNOWN_GENE_123")
    assert uid.startswith("P")
    assert len(uid) == 6


def test_get_target_3d_structure_known_targets():
    for gene_symbol in ["TNF", "JAK1", "CD19", "IL23R", "BTK"]:
        res = get_target_3d_structure(gene_symbol)
        assert res["gene_name"] == gene_symbol
        assert res["uniprot_id"] == KNOWN_UNIPROT_MAP[gene_symbol]
        assert 50.0 <= res["plddt_score"] <= 100.0
        assert res["confidence_category"] in [
            "Very High Confidence (>90)",
            "High Confidence (70-90)",
            "Moderate Confidence (50-70)",
            "Intrinsically Disordered (<50)",
        ]
        assert len(res["active_site_residues"]) > 0
        assert res["pocket_volume_A3"] > 300.0
        assert 0.40 <= res["docking_readiness_score"] <= 1.0
        assert res["druggability_tier"].startswith("Tier")
        assert res["pdb_id"] == f"AF-{KNOWN_UNIPROT_MAP[gene_symbol]}-F1"
        assert res["alphafold_cif_url"].startswith("https://alphafold.ebi.ac.uk/files/AF-")
        assert res["alphafold_pae_url"].startswith("https://alphafold.ebi.ac.uk/files/AF-")


def test_analyze_structure_3d_disease():
    res = analyze_structure_3d("sle")
    assert res["disease_id"] == "sle"
    assert res["total_structures"] > 0
    assert len(res["structures"]) > 0

    first = res["structures"][0]
    assert "plddt_score" in first
    assert "pocket_volume_A3" in first
    assert "docking_readiness_score" in first


def test_api_biomed_structure_endpoint():
    resp = client.get("/api/v1/biomed/structures/UNIPROT:P01375")
    assert resp.status_code == 200
    data = resp.json()
    assert data["uniprot_id"] == "P01375"
    assert data["gene_name"] == "TNF"
    assert "plddt_score" in data
    assert "active_site_residues" in data
    assert "pocket_volume_A3" in data


def test_api_target_prioritization_with_3d_structures():
    resp = client.get("/api/v1/biomed/target-prioritization/MONDO:0007915?top_k=5")
    assert resp.status_code == 200
    data = resp.json()
    assert data["disease_curie"] == "MONDO:0007915"
    assert "rankings" in data

    for r in data["rankings"]:
        assert "plddt_score" in r
        assert "pocket_volume_A3" in r
        assert "docking_readiness_score" in r
        assert "confidence_category" in r
        assert "druggability_tier" in r
        assert "structure_3d" in r
