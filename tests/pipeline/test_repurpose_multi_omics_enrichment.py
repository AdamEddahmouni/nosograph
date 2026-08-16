"""Unit and integration tests for multi-omics variant and GTEx expression enrichments in drug repurposing."""

from __future__ import annotations

from fastapi.testclient import TestClient

from med_research.pipeline.drug_repurposing.engine import (
    compute_composite_score,
    compute_tissue_expression_score,
    compute_variant_functional_score,
    load_knowledge_graph,
    score_candidates,
)
from med_research.web.main import app

client = TestClient(app)


def test_compute_variant_functional_score():
    gene_info = {
        "id": "STAT4",
        "name": "STAT4",
        "odds_ratio": 2.2,
        "disease_evidence": "Strong GWAS risk association",
    }
    score, details = compute_variant_functional_score("STAT4", gene_info, disease_id="sle")
    assert 3.5 <= score <= 9.8
    assert len(details) > 0
    assert details[0]["odds_ratio"] == 2.2
    assert "consequence" in details[0]
    assert "variant_id" in details[0]


def test_compute_tissue_expression_score():
    gene_info = {"id": "BTK", "name": "BTK"}
    score, top_tissues, concordance = compute_tissue_expression_score("BTK", gene_info, disease_id="sle")
    assert 3.5 <= score <= 9.8
    assert 0.40 <= concordance <= 1.0
    assert len(top_tissues) == 3
    assert top_tissues[0]["tissue"] in ["Whole Blood", "Spleen", "Cells - EBV-transformed lymphocytes"]
    assert top_tissues[0]["median_tpm"] > 0


def test_compute_composite_score_backward_compatibility():
    # 6-dimension candidate without multi-omics keys
    candidate_legacy = {
        "target_similarity_score": 10,
        "pathway_proximity_score": 10,
        "mechanistic_rationale_score": 10,
        "clinical_evidence_score": 10,
        "safety_score": 10,
        "novelty_score": 10,
    }
    assert compute_composite_score(candidate_legacy) == 10.00


def test_compute_composite_score_multi_omics_enrichment():
    # 8-dimension candidate with variant and GTEx expression
    candidate_enriched = {
        "target_similarity_score": 8.0,
        "pathway_proximity_score": 7.0,
        "mechanistic_rationale_score": 9.0,
        "clinical_evidence_score": 8.5,
        "adverse_event_score": 7.5,
        "variant_functional_score": 9.0,
        "tissue_expression_score": 8.0,
        "novelty_score": 6.0,
    }
    score = compute_composite_score(candidate_enriched)
    expected = (
        8.0 * 0.15
        + 7.0 * 0.10
        + 9.0 * 0.15
        + 8.5 * 0.15
        + 7.5 * 0.15
        + 9.0 * 0.15
        + 8.0 * 0.10
        + 6.0 * 0.05
    )
    assert score == round(expected, 2)


def test_score_candidates_includes_multi_omics_enrichments():
    G = load_knowledge_graph("sle")
    candidates = [
        {
            "gene_id": "BTK",
            "drug_name": "Ibrutinib",
            "mechanism": "BTK inhibitor",
            "target_similarity_score": 10.0,
            "pathway_proximity_score": 9.0,
            "mechanistic_rationale_score": 8.5,
            "clinical_evidence_score": 7.0,
            "safety_score": 6.5,
            "novelty_score": 8.0,
        }
    ]
    genes = {"BTK": {"id": "BTK", "name": "BTK", "odds_ratio": 1.8}}
    scored = score_candidates(G, candidates, genes, disease_id="sle")
    assert len(scored) == 1
    c = scored[0]
    assert "variant_functional_score" in c
    assert "tissue_expression_score" in c
    assert "variant_details" in c
    assert "top_expressing_tissues" in c
    assert "gtex_tissue_concordance" in c
    assert c["composite_score"] > 0


def test_api_repurpose_candidates_with_multi_omics():
    resp = client.get("/api/repurpose/candidates?top_n=5&disease=sle")
    assert resp.status_code == 200
    data = resp.json()
    assert "candidates" in data
    assert len(data["candidates"]) > 0

    first = data["candidates"][0]
    assert "variant_functional_score" in first
    assert "tissue_expression_score" in first
    assert "gtex_tissue_concordance" in first
