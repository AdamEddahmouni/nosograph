"""Regression contracts for biomedical store readiness and demo read-only access."""

from __future__ import annotations

import hashlib
import sqlite3
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient

from med_research.biomed.errors import BiomedicalStoreNotReadyError
from med_research.biomed.nosograph_compare.service import NosoGraphCompareService
from med_research.biomed.repository import BiomedicalRepository
from med_research.web import dependencies_biomed
from med_research.web.dependencies_biomed import (
    get_biomedical_repository,
    reset_biomedical_repository,
)
from med_research.web.main import app

CONDITIONS = ("MONDO:0007915", "MONDO:0008383")

pytestmark = pytest.mark.unit


@pytest.fixture(autouse=True)
def _reset_repository_cache() -> Any:
    reset_biomedical_repository()
    yield
    reset_biomedical_repository()


@pytest.fixture
def uninitialized_client(tmp_path: Path) -> Any:
    repository = BiomedicalRepository(tmp_path / "biomedical.sqlite3")
    app.dependency_overrides[get_biomedical_repository] = lambda: repository
    with TestClient(app) as client:
        yield client
    app.dependency_overrides.pop(get_biomedical_repository, None)


def test_repository_access_does_not_create_an_absent_store(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.delenv("DEMO_MODE", raising=False)
    absent = tmp_path / "missing" / "biomedical.sqlite3"
    monkeypatch.setattr(dependencies_biomed, "BIOMEDICAL_DB_PATH", absent)

    repository = get_biomedical_repository()

    assert repository.database.path == absent
    assert repository.is_schema_initialized() is False
    assert not absent.exists()
    assert not absent.parent.exists()


def test_compare_service_refuses_uninitialized_store_without_creating_it(
    tmp_path: Path,
) -> None:
    absent = tmp_path / "biomedical.sqlite3"
    repository = BiomedicalRepository(absent)
    service = NosoGraphCompareService(repository)

    with pytest.raises(BiomedicalStoreNotReadyError):
        service.compare_many_preview(list(CONDITIONS))
    with pytest.raises(BiomedicalStoreNotReadyError):
        service.compare_many(list(CONDITIONS))

    assert not absent.exists()


def test_compare_preview_api_reports_explicit_readiness(uninitialized_client: Any) -> None:
    response = uninitialized_client.post(
        "/api/v1/nosograph/comparisons/preview",
        json={"condition_curies": list(CONDITIONS)},
    )

    assert response.status_code == 503
    body = response.json()
    assert body["error_type"] == "BiomedicalStoreNotReadyError"
    assert body["store_state"]["status"] == "uninitialized"
    assert "biomed init" in body["store_state"]["initialization_hint"]


def test_demo_repository_is_read_only_and_initialized(demo_env: Any, demo_snapshot: Any) -> None:
    reset_biomedical_repository()

    repository = get_biomedical_repository()

    assert repository.database.read_only is True
    assert repository.is_schema_initialized() is True
    with pytest.raises(RuntimeError, match="read-only"):
        repository.initialize()


def test_demo_repository_rejects_writes(demo_env: Any, demo_snapshot: Any) -> None:
    reset_biomedical_repository()
    repository = get_biomedical_repository()

    with pytest.raises(sqlite3.OperationalError), repository.transaction() as connection:
        connection.execute("DELETE FROM entities")


def test_demo_read_routes_do_not_mutate_the_snapshot(
    demo_client: TestClient, demo_snapshot: Any
) -> None:
    database, manifest, _version = demo_snapshot
    before = (_sha256(database), _sha256(manifest))

    assert demo_client.get("/api/health").status_code == 200
    assert demo_client.get("/api/v1/snapshots").status_code == 200
    assert demo_client.get("/api/v1/conditions/search", params={"q": "lupus"}).status_code == 200

    assert (_sha256(database), _sha256(manifest)) == before


def test_demo_rejects_persisted_compare_but_allows_preview(demo_client: TestClient) -> None:
    persisted = demo_client.post(
        "/api/v1/nosograph/comparisons",
        json={"condition_curies": list(CONDITIONS)},
    )
    preview = demo_client.post(
        "/api/v1/nosograph/comparisons/preview",
        json={"condition_curies": list(CONDITIONS)},
    )

    assert persisted.status_code == 403
    assert persisted.json()["code"] == "demo_read_only"
    assert preview.status_code != 403


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()
