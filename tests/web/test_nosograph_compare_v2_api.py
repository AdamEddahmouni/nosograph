from __future__ import annotations


def test_nosograph_compare_v2_api_is_canonical_and_replays_permutations(
    client, seeded_biomed_db
) -> None:
    canonical = client.post(
        "/api/v1/nosograph/comparisons",
        json={
            "condition_curies": ["MONDO:0007915", "MONDO:0008390"],
            "dimensions": ["evidence_coverage", "gene", "phenotype"],
        },
    )
    permuted = client.post(
        "/api/v1/nosograph/comparisons",
        json={
            "condition_curies": ["mondo:0008390", "MONDO:0007915", "MONDO:0007915"],
            "dimensions": ["phenotype", "gene", "evidence_coverage", "gene"],
        },
    )

    assert canonical.status_code == 200
    assert permuted.status_code == 200
    body = canonical.json()
    assert body == permuted.json()
    assert body["condition_curies"] == ["MONDO:0007915", "MONDO:0008390"]
    assert body["dimensions"] == ["phenotype", "gene", "evidence_coverage"]
    assert body["algorithm_id"] == "nosograph-compare-v2"
    assert body["algorithm_version"] == "2.0.0"
    assert body["dimension_results"]
    assert "overall_score" not in body
    assert body["disclaimer"]["text"]
    run = seeded_biomed_db.get_research_run(body["run_id"])
    assert run is not None
    assert run.result is not None
    assert run.result["condition_curies"] == body["condition_curies"]
    assert run.result["dimensions"] == body["dimensions"]
    assert run.result["dimension_results"] == body["dimension_results"]


def test_nosograph_compare_v2_sparse_data_remains_http_200(client) -> None:
    response = client.post(
        "/api/v1/nosograph/comparisons",
        json={
            "condition_curies": ["MONDO:0007915", "MONDO:0008390"],
            "dimensions": ["phenotype"],
        },
    )
    assert response.status_code == 200
    assert response.json()["status"] == "insufficient_data"


def test_nosograph_compare_v2_returns_stable_422_errors(client) -> None:
    cases = [
        ({"condition_curies": ["MONDO:0007915"]}, "2 to 5 unique conditions"),
        (
            {"condition_curies": ["MONDO:0007915", "MONDO:9999999"]},
            "Unresolved condition CURIE",
        ),
        (
            {
                "condition_curies": ["MONDO:0007915", "MONDO:0008390"],
                "dimensions": ["mechanism"],
            },
            "Unknown comparison dimensions",
        ),
        (
            {"condition_curies": ["MONDO:0007915", "MONDO:0008390"], "dimensions": []},
            "At least one comparison dimension",
        ),
    ]
    for payload, message in cases:
        response = client.post("/api/v1/nosograph/comparisons", json=payload)
        assert response.status_code == 422
        assert response.json() == {"detail": message} or message in str(response.json())


def test_legacy_pairwise_endpoint_projects_v2_and_is_deprecated(client) -> None:
    from med_research.web.routers.universal import router

    response = client.post(
        "/api/v1/nosograph/compare",
        json={
            "left_curie": "MONDO:0008390",
            "right_curie": "MONDO:0007915",
            "dimensions": ["mechanism"],
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert body["left_curie"] == "MONDO:0008390"
    assert body["right_curie"] == "MONDO:0007915"
    assert body["overlaps"][0]["dimension"] == "mechanism"
    assert body["algorithm_version"] == "2.0.0"

    route = next(item for item in router.routes if item.path == "/api/v1/nosograph/compare")
    assert route.deprecated is True
