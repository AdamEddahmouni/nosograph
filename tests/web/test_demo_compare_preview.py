from __future__ import annotations

from med_research.biomed.identifiers import canonical_json
from med_research.web.demo_mode import is_demo_allowed_path

TWO_CONDITIONS = ["MONDO:0007915", "MONDO:0008390"]
DEMO_READ_ONLY = {
    "code": "demo_read_only",
    "detail": "This operation is disabled in the public read-only demo.",
}


def test_preview_post_is_exact_allow_list_not_all_subpaths() -> None:
    assert is_demo_allowed_path("/api/v1/nosograph/comparisons/preview", "POST") is True
    assert is_demo_allowed_path("/api/v1/nosograph/comparisons/preview/", "POST") is True
    assert is_demo_allowed_path("/api/v1/nosograph/comparisons/preview/export", "POST") is True
    assert is_demo_allowed_path("/api/v1/nosograph/comparisons/preview/other", "POST") is False
    assert is_demo_allowed_path("/api/v1/nosograph/comparisons", "POST") is False


def test_demo_allows_preview_and_export_but_blocks_persisted_compare(client, demo_env) -> None:
    persisted = client.post(
        "/api/v1/nosograph/comparisons",
        json={"condition_curies": TWO_CONDITIONS},
    )
    preview = client.post(
        "/api/v1/nosograph/comparisons/preview",
        json={"condition_curies": TWO_CONDITIONS},
    )
    export = client.post(
        "/api/v1/nosograph/comparisons/preview/export",
        params={"format": "json"},
        json={"condition_curies": TWO_CONDITIONS},
    )
    other_preview = client.post(
        "/api/v1/nosograph/comparisons/preview/other",
        json={"condition_curies": TWO_CONDITIONS},
    )

    assert persisted.status_code == 403
    assert persisted.json() == DEMO_READ_ONLY
    assert preview.status_code != 403
    assert export.status_code != 403
    assert other_preview.status_code == 403
    assert other_preview.json() == DEMO_READ_ONLY


def test_compare_preview_api_two_conditions_is_non_persisting(client, seeded_biomed_db) -> None:
    before = seeded_biomed_db.list_research_runs(limit=1).total
    first = client.post(
        "/api/v1/nosograph/comparisons/preview",
        json={"condition_curies": TWO_CONDITIONS, "dimensions": ["phenotype", "gene"]},
    )
    second = client.post(
        "/api/v1/nosograph/comparisons/preview",
        json={
            "condition_curies": ["mondo:0008390", "MONDO:0007915", "MONDO:0007915"],
            "dimensions": ["gene", "phenotype", "gene"],
        },
    )

    assert first.status_code == 200
    assert second.status_code == 200
    body = first.json()
    assert body == second.json()
    assert body["run_id"] is None
    assert body["preview"] is True
    assert body["condition_curies"] == TWO_CONDITIONS
    assert body["dimensions"] == ["phenotype", "gene"]
    assert "overall_score" not in body
    assert seeded_biomed_db.list_research_runs(limit=1).total == before


def test_compare_preview_api_rejects_invalid_condition_and_dimension(client) -> None:
    unresolved = client.post(
        "/api/v1/nosograph/comparisons/preview",
        json={"condition_curies": ["MONDO:0007915", "MONDO:9999999"]},
    )
    unknown_dimension = client.post(
        "/api/v1/nosograph/comparisons/preview",
        json={"condition_curies": TWO_CONDITIONS, "dimensions": ["mechanism"]},
    )
    too_few = client.post(
        "/api/v1/nosograph/comparisons/preview",
        json={"condition_curies": ["MONDO:0007915"]},
    )

    assert unresolved.status_code == 422
    assert "Unresolved condition CURIE" in str(unresolved.json())
    assert unknown_dimension.status_code == 422
    assert "Unknown comparison dimensions" in str(unknown_dimension.json())
    assert too_few.status_code == 422
    assert "2 to 5 unique conditions" in str(too_few.json())


def test_compare_preview_exports_are_deterministic_and_have_no_run_id(
    client, seeded_biomed_db
) -> None:
    payload = {"condition_curies": TWO_CONDITIONS, "dimensions": ["phenotype", "gene"]}
    preview = client.post("/api/v1/nosograph/comparisons/preview", json=payload)
    json_first = client.post(
        "/api/v1/nosograph/comparisons/preview/export",
        params={"format": "json"},
        json=payload,
    )
    json_second = client.post(
        "/api/v1/nosograph/comparisons/preview/export",
        params={"format": "json"},
        json=payload,
    )
    markdown_first = client.post(
        "/api/v1/nosograph/comparisons/preview/export",
        params={"format": "markdown"},
        json=payload,
    )
    markdown_second = client.post(
        "/api/v1/nosograph/comparisons/preview/export",
        params={"format": "markdown"},
        json=payload,
    )
    invalid = client.post(
        "/api/v1/nosograph/comparisons/preview/export",
        params={"format": "csv"},
        json=payload,
    )

    assert preview.status_code == 200
    body = preview.json()
    assert json_first.status_code == 200
    assert json_first.content == json_second.content
    assert json_first.content == (canonical_json(body) + "\n").encode("utf-8")
    exported = json_first.json()
    assert exported["run_id"] is None
    assert exported["preview"] is True
    assert json_first.headers["content-type"].startswith("application/json")
    assert (
        json_first.headers["content-disposition"]
        == 'attachment; filename="nosograph-comparison-preview.json"'
    )
    assert markdown_first.status_code == 200
    assert markdown_first.content == markdown_second.content
    assert markdown_first.content.endswith(b"\n")
    markdown = markdown_first.text
    assert "# NosoGraph comparison" in markdown
    assert "created_at" not in markdown
    assert "nosograph-compare-v2" in markdown
    assert (
        markdown_first.headers["content-disposition"]
        == 'attachment; filename="nosograph-comparison-preview.md"'
    )
    assert invalid.status_code == 422
    assert seeded_biomed_db.list_research_runs(limit=1).total == 0


def test_persisted_compare_still_creates_run_outside_demo_mode(client, seeded_biomed_db) -> None:
    before = seeded_biomed_db.list_research_runs(limit=1).total
    response = client.post(
        "/api/v1/nosograph/comparisons",
        json={"condition_curies": TWO_CONDITIONS, "dimensions": ["phenotype"]},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["run_id"]
    assert "preview" not in body
    run = seeded_biomed_db.get_research_run(body["run_id"])
    assert run is not None
    assert run.result is not None
    assert seeded_biomed_db.list_research_runs(limit=1).total == before + 1
