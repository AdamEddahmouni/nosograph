from __future__ import annotations


def test_claim_detail_endpoint_serializes_provenance(client, seeded_biomed_db) -> None:
    claims = client.get("/api/v1/conditions/MONDO:0007915/claims?limit=5").json()
    assert claims["items"], "expected seeded claims"
    claim_id = claims["items"][0]["claim_id"]

    detail = client.get(f"/api/v1/claims/{claim_id}")
    assert detail.status_code == 200
    body = detail.json()
    assert body["claim_id"] == claim_id
    assert body["evidence_summary"] in {"SUPPORTS", "CONTRADICTS", "INCONCLUSIVE", "UNASSERTED"}
    assert "provenance" in body
    assert body["disclaimer"]["text"]


def test_claim_evidence_and_provenance_endpoints(client, seeded_biomed_db) -> None:
    claims = client.get("/api/v1/conditions/MONDO:0007915/claims?limit=5").json()
    claim_id = claims["items"][0]["claim_id"]

    evidence = client.get(f"/api/v1/claims/{claim_id}/evidence")
    assert evidence.status_code == 200
    rows = evidence.json()
    if rows:
        assert "summary" in rows[0]
        assert "provenance" in rows[0]

    provenance = client.get(f"/api/v1/claims/{claim_id}/provenance")
    assert provenance.status_code == 200
    steps = provenance.json()
    assert any(step.get("stage") == "graph_claim" for step in steps)


def test_nosograph_compare_api(client, seeded_biomed_db) -> None:
    response = client.post(
        "/api/v1/nosograph/compare",
        json={
            "left_curie": "MONDO:0007915",
            "right_curie": "MONDO:0008390",
            "dimensions": ["phenotype", "gene", "evidence_coverage"],
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert body["algorithm_id"] == "nosograph-compare"
    assert "overall_score" not in body
    assert body["overlaps"]
    assert body["disclaimer"]["text"]
