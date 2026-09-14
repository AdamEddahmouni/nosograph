"""Graceful API behavior when the canonical biomedical store is not initialized."""

from __future__ import annotations

from typing import Any

import pytest
from fastapi.testclient import TestClient

from med_research.biomed.repository import BiomedicalRepository
from med_research.web.dependencies_biomed import (
    get_biomedical_repository,
    reset_biomedical_repository,
)
from med_research.web.main import app


@pytest.fixture
def uninitialized_biomed_client(tmp_path) -> Any:
    reset_biomedical_repository()
    db_path = tmp_path / "biomedical.sqlite3"
    repository = BiomedicalRepository(db_path)
    assert not repository.is_schema_initialized()
    app.dependency_overrides[get_biomedical_repository] = lambda: repository
    with TestClient(app) as client:
        yield client, db_path
    app.dependency_overrides.pop(get_biomedical_repository, None)
    reset_biomedical_repository()


def test_search_conditions_returns_empty_paged_state(uninitialized_biomed_client) -> None:
    client, _ = uninitialized_biomed_client
    response = client.get("/api/v1/conditions/search?q=lupus")
    assert response.status_code == 200
    body = response.json()
    assert body["items"] == []
    assert body["total"] == 0
    assert body["store_state"]["status"] == "uninitialized"
    assert "biomed init" in body["store_state"]["initialization_hint"]


def test_snapshots_list_returns_empty_paged_state(uninitialized_biomed_client) -> None:
    client, _ = uninitialized_biomed_client
    response = client.get("/api/v1/snapshots")
    assert response.status_code == 200
    body = response.json()
    assert body["items"] == []
    assert body["store_state"]["status"] == "uninitialized"


def test_condition_detail_returns_typed_not_ready(uninitialized_biomed_client) -> None:
    client, _ = uninitialized_biomed_client
    response = client.get("/api/v1/conditions/MONDO:0007915")
    assert response.status_code == 503
    body = response.json()
    assert body["error_type"] == "BiomedicalStoreNotReadyError"
    assert body["store_state"]["status"] == "uninitialized"
    assert "biomed init" in body["store_state"]["initialization_hint"]


def test_biomed_analytics_summary_returns_zeros_not_error(uninitialized_biomed_client) -> None:
    client, _ = uninitialized_biomed_client
    response = client.get("/api/v1/biomed/analytics/summary")
    assert response.status_code == 200
    body = response.json()
    assert "error" not in body
    assert body["total_entities"] == 0
    assert body["total_claims"] == 0


def test_biomed_pathways_returns_empty_payload(uninitialized_biomed_client) -> None:
    client, _ = uninitialized_biomed_client
    response = client.get(
        "/api/v1/biomed/pathways",
        params={"start_curie": "MONDO:0007915", "target_curie": "MONDO:0008383"},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["total_paths"] == 0
    assert body["paths"] == []
    assert body["store_state"]["status"] == "uninitialized"


def test_initialized_empty_store_still_serves_lists(uninitialized_biomed_client) -> None:
    client, db_path = uninitialized_biomed_client
    repository = BiomedicalRepository(db_path)
    repository.initialize()
    app.dependency_overrides[get_biomedical_repository] = lambda: repository

    response = client.get("/api/v1/conditions/search?q=lupus")
    assert response.status_code == 200
    body = response.json()
    assert body["items"] == []
    assert body.get("store_state") is None
