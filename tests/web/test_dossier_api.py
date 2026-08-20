import pytest
from fastapi.testclient import TestClient

from med_research.web.main import app

client = TestClient(app)


@pytest.mark.unit
def test_dossier_generate_endpoint():
    response = client.get("/api/dossier/generate")
    # Should either succeed with URLs or 404 if pipeline empty in isolation
    assert response.status_code in (200, 404)
    if response.status_code == 200:
        data = response.json()
        assert "pdf_url" in data
        assert "markdown_url" in data
        assert "timestamp" in data
