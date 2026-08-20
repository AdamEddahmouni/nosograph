"""Unit tests for Target Hypothesis Agent API endpoints."""

import pytest
from fastapi.testclient import TestClient

from med_research.web.main import app

pytestmark = pytest.mark.unit
client = TestClient(app)


def test_agent_hypothesis_generate():
    payload = {"disease_id": "melanoma", "gene_symbol": "BRAF"}
    response = client.post("/api/agent/hypothesis/generate", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "success"
    hyp = data["hypothesis"]
    assert hyp["target_gene"] == "BRAF"
    assert hyp["overall_confidence"] > 0.5
    assert len(hyp["supporting_evidence"]) >= 1
    assert "tractability_small_molecule" in hyp["druggability_assessment"]


def test_agent_chat():
    payload = {"query": "Tell me about BRAF mutations in melanoma", "disease_id": "melanoma"}
    response = client.post("/api/agent/chat", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert "BRAF" in data["target_analyzed"]
    assert "answer" in data
    assert len(data["answer"]) > 20
