"""Unit tests for Spatial Transcriptomics API endpoints."""

import pytest
from fastapi.testclient import TestClient

from med_research.web.main import app

pytestmark = pytest.mark.unit
client = TestClient(app)


def test_spatial_sample_data():
    response = client.get("/api/spatial/sample-data?disease=melanoma&num_spots=100")
    assert response.status_code == 200
    data = response.json()
    assert data["spot_count"] == 100
    assert len(data["spots"]) == 100
    assert "CD274" in data["available_genes"]


def test_spatial_analyze():
    # Sample spots
    spots = [
        {"barcode": "SPOT-1", "x": 10.0, "y": 10.0, "features": {"CD274": 5.0, "PDCD1": 4.0}},
        {"barcode": "SPOT-2", "x": 15.0, "y": 12.0, "features": {"CD274": 4.8, "PDCD1": 3.9}},
        {"barcode": "SPOT-3", "x": 20.0, "y": 14.0, "features": {"CD274": 4.5, "PDCD1": 3.5}},
        {"barcode": "SPOT-4", "x": 100.0, "y": 100.0, "features": {"CD274": 0.5, "PDCD1": 0.2}},
        {"barcode": "SPOT-5", "x": 105.0, "y": 102.0, "features": {"CD274": 0.4, "PDCD1": 0.1}},
    ]
    payload = {
        "spots": spots,
        "gene": "CD274",
        "ligand_gene": "CD274",
        "receptor_gene": "PDCD1",
        "radius": 50.0,
    }
    response = client.post("/api/spatial/analyze", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["target_gene"] == "CD274"
    assert "morans_i_score" in data
    assert "spatial_pattern" in data
    assert "ligand_receptor_interaction" in data
    assert data["ligand_receptor_interaction"]["colocalization_score"] > 0
