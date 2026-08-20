from fastapi.testclient import TestClient

from med_research.web.main import app

client = TestClient(app)


def test_pgx_endpoint_success():
    payload = {"genotypes": {"CYP2D6": ["*1", "*4"], "CYP2C19": ["*2"]}}
    response = client.post("/pgx/evaluate", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
    # Should contain entries for both genes
    genes = {item["gene"] for item in data}
    assert "CYP2D6" in genes and "CYP2C19" in genes
    # Phenotype strings present
    for item in data:
        assert "phenotype" in item and "dosing_guidance" in item


def test_pgx_endpoint_invalid_gene():
    payload = {"genotypes": {"XYZ": ["*1"]}}
    response = client.post("/pgx/evaluate", json=payload)
    assert response.status_code == 400
    assert "Gene XYZ is not supported" in response.json()["detail"]


def test_pgx_endpoint_invalid_allele():
    payload = {"genotypes": {"CYP2D6": ["*99"]}}
    response = client.post("/pgx/evaluate", json=payload)
    assert response.status_code == 400
    assert "Allele *99 not recognized" in response.json()["detail"]
