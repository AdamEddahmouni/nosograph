def test_search_conditions_returns_disclaimer(client, seeded_biomed_db) -> None:
    response = client.get("/api/v1/conditions/search", params={"q": "lupus", "limit": 5})
    assert response.status_code == 200
    body = response.json()
    assert body["disclaimer"]["text"]
    assert body["items"]


def test_unknown_condition_returns_404(client, seeded_biomed_db) -> None:
    response = client.get("/api/v1/conditions/MONDO:9999999")
    assert response.status_code == 404


def test_condition_detail_includes_readiness(client, seeded_biomed_db) -> None:
    response = client.get("/api/v1/conditions/MONDO:0007915")
    assert response.status_code == 200
    body = response.json()
    assert body["curie"] == "MONDO:0007915"
    assert "readiness" in body
    assert body["disclaimer"]["text"]


def test_hierarchy_rejects_depth_over_limit(client, seeded_biomed_db) -> None:
    response = client.get(
        "/api/v1/conditions/MONDO:0007915/hierarchy",
        params={"depth": 4},
    )
    assert response.status_code == 422


def test_list_snapshots_returns_active_flags(client, seeded_biomed_db) -> None:
    response = client.get("/api/v1/snapshots", params={"limit": 10})
    assert response.status_code == 200
    body = response.json()
    assert body["items"]
    assert any(item["active"] for item in body["items"])
