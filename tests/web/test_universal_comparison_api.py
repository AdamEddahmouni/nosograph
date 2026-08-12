from __future__ import annotations


def test_compare_endpoint_returns_components_and_disclaimer(client, seeded_biomed_db) -> None:
    response = client.post(
        "/api/v1/comparisons",
        json={"left_curie": "MONDO:0007915", "right_curie": "MONDO:0008390"},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["disclaimer"]["text"]
    assert "components" in body


def test_get_comparison_run_returns_persisted_result(client, seeded_biomed_db) -> None:
    created = client.post(
        "/api/v1/comparisons",
        json={"left_curie": "MONDO:0007915", "right_curie": "MONDO:0008390"},
    )
    run_id = created.json()["run_id"]
    fetched = client.get(f"/api/v1/comparisons/{run_id}")
    assert fetched.status_code == 200
    assert fetched.json()["run_id"] == run_id
