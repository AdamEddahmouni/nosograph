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
    body = evidence.json()
    assert "items" in body
    assert "total" in body
    rows = body["items"]
    if rows:
        assert "summary" in rows[0]
        assert "provenance" in rows[0]
        assert "quality" in rows[0]
        assert rows[0]["quality"]["species_context"]

    provenance = client.get(f"/api/v1/claims/{claim_id}/provenance")
    assert provenance.status_code == 200
    steps = provenance.json()
    assert any(step.get("stage") == "graph_claim" for step in steps)


def test_claim_detail_includes_counts_and_quality(client, seeded_biomed_db) -> None:
    claims = client.get("/api/v1/conditions/MONDO:0007915/claims?limit=5").json()
    claim_id = claims["items"][0]["claim_id"]
    detail = client.get(f"/api/v1/claims/{claim_id}").json()
    assert "supporting_count" in detail
    assert "source_count" in detail
    if detail["supporting_evidence"]:
        assert detail["supporting_evidence"][0]["quality"]["origin_class"]


def test_claim_evidence_pagination_and_filters(client, seeded_biomed_db) -> None:
    claims = client.get("/api/v1/conditions/MONDO:0007915/claims?limit=5").json()
    claim_id = claims["items"][0]["claim_id"]
    page = client.get(f"/api/v1/claims/{claim_id}/evidence?limit=1&offset=0&sort=source")
    assert page.status_code == 200
    body = page.json()
    assert body["limit"] == 1
    assert body["total"] >= len(body["items"])

    filtered = client.get(
        f"/api/v1/claims/{claim_id}/evidence",
        params={"direction": "supporting"},
    )
    assert filtered.status_code == 200
    for row in filtered.json()["items"]:
        assert row["direction"] == "supporting"


def test_related_claims_endpoint(client, seeded_biomed_db) -> None:
    claims = client.get("/api/v1/conditions/MONDO:0007915/claims?limit=5").json()
    claim_id = claims["items"][0]["claim_id"]
    related = client.get(f"/api/v1/claims/{claim_id}/related")
    assert related.status_code == 200
    rows = related.json()
    assert isinstance(rows, list)
    if rows:
        assert rows[0]["relation"] in {"same_subject", "same_object"}
        assert rows[0]["evidence_summary"] in {"SUPPORTS", "CONTRADICTS", "INCONCLUSIVE", "UNASSERTED"}


def test_claim_evidence_unknown_claim_returns_404(client, seeded_biomed_db) -> None:
    missing = "00000000-0000-0000-0000-000000000099"
    response = client.get(f"/api/v1/claims/{missing}/evidence")
    assert response.status_code == 404


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
