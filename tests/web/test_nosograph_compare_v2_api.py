from __future__ import annotations

from med_research.biomed.identifiers import canonical_json
from med_research.biomed.models import ResearchRunCreate, RunStatus


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
    assert body["result_schema_version"] == "2.0"
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
    run_id = response.json()["run_id"]
    assert client.get(f"/api/v1/nosograph/comparisons/{run_id}/exports/json").status_code == 200
    assert client.get(f"/api/v1/nosograph/comparisons/{run_id}/exports/markdown").status_code == 200


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


def test_nosograph_compare_v2_replay_and_deterministic_exports(client) -> None:
    created = client.post(
        "/api/v1/nosograph/comparisons",
        json={
            "condition_curies": ["MONDO:0007915", "MONDO:0008390"],
            "dimensions": ["phenotype", "gene"],
        },
    )
    assert created.status_code == 200
    body = created.json()
    run_url = f"/api/v1/nosograph/comparisons/{body['run_id']}"

    replay = client.get(run_url)
    json_first = client.get(f"{run_url}/exports/json")
    json_second = client.get(f"{run_url}/exports/json")
    markdown_first = client.get(f"{run_url}/exports/markdown")
    markdown_second = client.get(f"{run_url}/exports/markdown")

    assert replay.status_code == 200
    assert replay.json() == body
    assert json_first.status_code == 200
    assert json_first.content == json_second.content
    assert json_first.content == (canonical_json(body) + "\n").encode("utf-8")
    assert json_first.headers["content-type"].startswith("application/json")
    assert (
        json_first.headers["content-disposition"]
        == f'attachment; filename="nosograph-comparison-{body["run_id"]}.json"'
    )
    assert markdown_first.status_code == 200
    assert markdown_first.content == markdown_second.content
    assert markdown_first.content.endswith(b"\n")
    markdown = markdown_first.text
    assert "# NosoGraph comparison" in markdown
    assert "## Conditions" in markdown
    assert "## Phenotype" in markdown
    assert "### Shared" in markdown
    assert "### Distinct" in markdown
    assert "### Missing data" in markdown
    assert "## Reproducibility" in markdown
    assert "created_at" not in markdown
    assert "updated_at" not in markdown
    assert (
        markdown_first.headers["content-disposition"]
        == f'attachment; filename="nosograph-comparison-{body["run_id"]}.md"'
    )


def test_nosograph_compare_v2_run_routes_distinguish_missing_and_incomplete(
    client, seeded_biomed_db
) -> None:
    missing_id = "00000000-0000-0000-0000-000000000000"
    assert client.get(f"/api/v1/nosograph/comparisons/{missing_id}").status_code == 404
    assert client.get(f"/api/v1/nosograph/comparisons/{missing_id}/exports/json").status_code == 404

    other_run = seeded_biomed_db.create_research_run(
        ResearchRunCreate(
            run_type="research",
            algorithm_id="other",
            input_query="nosograph-compare-v2-non-compare-route-test",
        )
    )
    assert client.get(f"/api/v1/nosograph/comparisons/{other_run.id}").status_code == 404

    created = client.post(
        "/api/v1/nosograph/comparisons",
        json={
            "condition_curies": ["MONDO:0007915", "MONDO:0008390"],
            "dimensions": ["pathway"],
        },
    )
    run_id = created.json()["run_id"]
    with seeded_biomed_db.transaction() as connection:
        connection.execute(
            "UPDATE research_runs SET status = ?, result_json = NULL WHERE id = ?",
            (RunStatus.RUNNING.value, run_id),
        )

    assert client.get(f"/api/v1/nosograph/comparisons/{run_id}").status_code == 409
    assert client.get(f"/api/v1/nosograph/comparisons/{run_id}/exports/markdown").status_code == 409
