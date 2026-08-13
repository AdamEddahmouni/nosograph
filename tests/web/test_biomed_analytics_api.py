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

