"""HTTP tests for corpus status API."""


def test_corpus_status_endpoint(client):
    resp = client.get("/api/system/corpus-status")
    assert resp.status_code == 200
    data = resp.json()
    assert "aggregate" in data
    assert "top_config_gaps" in data


def test_disease_info_model_fields(client):
    """Spot-check enriched fields on a single known disease via system stats."""
    resp = client.get("/api/system/diseases")
    assert resp.status_code == 200
    data = resp.json()
    assert data["count"] >= 7
    sample = data["diseases"][0]
    for field in ("mondo_curie", "efo_id", "readiness_tier", "config_gaps"):
        assert field in sample


def test_corpus_status_filter_and_search(client):
    """Test filtering by tier, searching by name, and pagination."""
    resp = client.get("/api/system/corpus-status?tier=L3&limit=5")
    assert resp.status_code == 200
    data = resp.json()
    assert "diseases" in data
    assert "total_matching" in data
    for d in data["diseases"]:
        assert d["tier"].lower() == "l3"

    # Test search
    resp_search = client.get("/api/system/corpus-status?search=leukemia")
    assert resp_search.status_code == 200
    data_s = resp_search.json()
    assert "diseases" in data_s
    assert any("leukemia" in (d["name"] + d["disease_id"]).lower() for d in data_s["diseases"])
