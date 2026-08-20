"""Unit tests for Lead Optimization & ADMET API endpoints."""

import pytest
from fastapi.testclient import TestClient

from med_research.web.main import app

pytestmark = pytest.mark.unit
client = TestClient(app)


def test_lead_opt_analyze_valid_smiles():
    # Vemurafenib
    payload = {
        "smiles": "CCCS(=O)(=O)NC1=C(C(=C(C=C1)F)C(=O)C2=CNC3=NC=C(C=C23)C4=CC=C(C=C4)Cl)F",
        "compound_name": "Vemurafenib",
    }
    response = client.post("/api/lead-opt/analyze", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["compound_name"] == "Vemurafenib"
    assert "composite_score" in data
    assert "properties" in data
    assert "admet_radar" in data
    assert data["properties"]["mw"] > 400


def test_lead_opt_analyze_invalid_smiles():
    payload = {
        "smiles": "INVALID_NOT_A_SMILES_STRING",
    }
    response = client.post("/api/lead-opt/analyze", json=payload)
    assert response.status_code == 400


def test_lead_opt_batch_screen():
    smiles_list = [
        "CC(=O)OC1=CC=CC=C1C(=O)O",  # Aspirin
        "CN1C=NC2=C1C(=O)N(C(=O)N2C)C",  # Caffeine
        "CC(C)CC1=CC=C(C=C1)C(C)C(=O)O",  # Ibuprofen
    ]
    response = client.post("/api/lead-opt/batch-screen", json={"smiles_list": smiles_list})
    assert response.status_code == 200
    data = response.json()
    assert data["total_screened"] == 3
    assert data["passed_count"] == 3
    assert len(data["ranked_candidates"]) == 3
