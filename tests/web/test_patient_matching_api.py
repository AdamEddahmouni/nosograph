"""Unit tests for Clinical Trial Patient Matching API endpoints."""

import pytest
from fastapi.testclient import TestClient

from med_research.web.main import app

pytestmark = pytest.mark.unit
client = TestClient(app)


def test_generate_synthetic_cohort():
    payload = {"num_patients": 5, "disease": "melanoma", "seed": 42}
    response = client.post("/api/matching/generate-cohort", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["count"] == 5
    assert len(data["cohort"]) == 5
    assert data["cohort"][0]["disease"] == "melanoma"
    assert data["persisted"] is False
    assert "Research simulation only" in data["disclaimer"]
    assert "protected health information" in data["disclaimer"]


def test_match_patient_to_trials():
    patient = {
        "patient_id": "PT-9999",
        "age": 52,
        "sex": "F",
        "disease": "melanoma",
        "stage": "III",
        "biomarkers": {"BRAF_V600E": True, "PD_L1": 0.8},
        "prior_therapies": ["Nivolumab"],
        "ecog_score": 1,
        "location_lat": 37.7749,
        "location_lon": -122.4194,
    }
    response = client.post("/api/matching/match", json=patient)
    assert response.status_code == 200
    data = response.json()
    assert data["patient_id"] == "PT-9999"
    assert data["total_trials_evaluated"] >= 1
    assert len(data["matches"]) >= 1
    assert data["persisted"] is False
    assert "not eligibility determinations" in data["disclaimer"]
    assert "overall_match_score" in data["matches"][0]
