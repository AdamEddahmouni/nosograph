"""Integration tests for Biomedical Analytics web API endpoints."""

from __future__ import annotations

from typing import Any


def test_find_claim_pathways_endpoint(client: Any, seeded_biomed_db: Any) -> None:
    response = client.get(
        "/api/v1/biomed/pathways",
        params={
            "start_curie": "MONDO:0007915",
            "target_curie": "MONDO:0007915",
            "max_depth": 3,
            "limit": 5,
        },
    )
    assert response.status_code == 200
    data = response.json()
    assert data["start_curie"] == "MONDO:0007915"
    assert data["target_curie"] == "MONDO:0007915"
    assert data["max_depth"] == 3
    assert "total_paths" in data
    assert isinstance(data["paths"], list)
    assert len(data["paths"]) >= 1
    path = data["paths"][0]
    assert path["nodes"] == ["MONDO:0007915"]
    assert path["score"] == 1.0


def test_find_claim_pathways_invalid_max_depth(client: Any) -> None:
    response = client.get(
        "/api/v1/biomed/pathways",
        params={
            "start_curie": "MONDO:0007915",
            "target_curie": "MONDO:0007915",
            "max_depth": 10,
        },
    )
    assert response.status_code == 422


def test_prioritize_targets_endpoint(client: Any, seeded_biomed_db: Any) -> None:
    response = client.get(
        "/api/v1/biomed/target-prioritization/MONDO:0007915",
        params={"top_k": 5},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["disease_curie"] == "MONDO:0007915"
    assert "total_targets" in data
    assert isinstance(data["rankings"], list)


def test_prioritize_targets_invalid_top_k(client: Any) -> None:
    response = client.get(
        "/api/v1/biomed/target-prioritization/MONDO:0007915",
        params={"top_k": 100},
    )
    assert response.status_code == 422


def test_graph_summary_endpoint(client: Any, seeded_biomed_db: Any) -> None:
    response = client.get("/api/v1/biomed/analytics/summary")
    assert response.status_code == 200
    data = response.json()
    assert "total_entities" in data
    assert "total_claims" in data
    assert "total_evidence" in data
    assert isinstance(data["total_entities"], int)


def test_shared_mechanisms_endpoint(client: Any, seeded_biomed_db: Any) -> None:
    response = client.get(
        "/api/v1/biomed/analytics/shared-mechanisms",
        params={"curie_a": "MONDO:0007915", "curie_b": "MONDO:0008383"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["condition_a"] == "MONDO:0007915"
    assert data["condition_b"] == "MONDO:0008383"
    assert "shared_pathways" in data
    assert "shared_genes" in data
    assert "jaccard_similarity" in data


def test_multi_hop_subgraph_endpoint(client: Any, seeded_biomed_db: Any) -> None:
    response = client.get(
        "/api/v1/biomed/analytics/subgraph",
        params={"start_curie": "MONDO:0007915", "max_hops": 2, "limit": 20},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["start_curie"] == "MONDO:0007915"
    assert data["max_hops"] == 2
    assert "total_edges" in data
    assert isinstance(data["edges"], list)


def test_cross_disease_matrix_endpoint(client: Any, seeded_biomed_db: Any) -> None:
    response = client.get(
        "/api/v1/biomed/analytics/matrix",
        params={"curies": "MONDO:0007915,MONDO:0008383"},
    )
    assert response.status_code == 200
    data = response.json()
    assert "conditions" in data
    assert "matrix" in data
    assert "details" in data
    assert len(data["conditions"]) == 2
    assert len(data["matrix"]) == 2


def test_druggability_analytics_endpoint(client: Any, seeded_biomed_db: Any) -> None:
    response = client.get(
        "/api/v1/biomed/analytics/druggability",
        params={"disease_curie": "MONDO:0007915"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["disease_curie"] == "MONDO:0007915"
    assert "distribution" in data


