from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from med_research.pipeline.evidence_workspace.schemas import EvidenceDossier, ResearchRequest
from med_research.web.services.workspace_store import WorkspaceRunStore

pytestmark = pytest.mark.unit


def _save_run(path, run_id, score):
    store = WorkspaceRunStore(path)
    dossier = EvidenceDossier(
        run_id=run_id,
        request=ResearchRequest(question="Find JAK interventions for SLE"),
        started_at="2026-01-01T00:00:00Z",
        completed_at="2026-01-01T00:00:01Z",
    )
    store.create_run(run_id, dossier.request)
    store.save_success(dossier, f"<html>{score}</html>")
    return store


def test_workspace_history_api_lists_gets_and_compares_runs(monkeypatch, tmp_path):
    import med_research.web.routers.workspace as workspace_router

    db_path = tmp_path / "workspace.sqlite3"
    store = _save_run(db_path, "ew-one", 1)
    store.create_run("ew-two", ResearchRequest(question="Second question"))
    monkeypatch.setattr(workspace_router, "WORKSPACE_DB_PATH", db_path)

    from med_research.web.main import app

    with TestClient(app) as client:
        listed = client.get("/api/workspace/runs?limit=10")
        loaded = client.get("/api/workspace/runs/ew-one")
        comparison = client.get("/api/workspace/compare?left=ew-one&right=ew-two")

    assert listed.status_code == 200
    assert {run["run_id"] for run in listed.json()["runs"]} == {"ew-one", "ew-two"}
    assert loaded.status_code == 200
    assert loaded.json()["dossier"]["run_id"] == "ew-one"
    assert comparison.status_code == 200
    assert comparison.json()["left_run_id"] == "ew-one"


def test_workspace_history_api_deletes_and_handles_missing_runs(monkeypatch, tmp_path):
    import med_research.web.routers.workspace as workspace_router

    db_path = tmp_path / "workspace.sqlite3"
    _save_run(db_path, "ew-delete", 1)
    monkeypatch.setattr(workspace_router, "WORKSPACE_DB_PATH", db_path)

    from med_research.web.main import app

    with TestClient(app) as client:
        deleted = client.delete("/api/workspace/runs/ew-delete")
        missing = client.get("/api/workspace/runs/ew-delete")
        compare_missing = client.get("/api/workspace/compare?left=ew-delete&right=missing")

    assert deleted.status_code == 200
    assert deleted.json() == {"deleted": True, "run_id": "ew-delete"}
    assert missing.status_code == 404
    assert compare_missing.status_code == 404


def test_dashboard_contains_workspace_history_and_compare_controls():
    root = Path(__file__).parents[1] / "src/med_research/web/static"
    index = (root / "index.html").read_text(encoding="utf-8")
    script = (root / "js/dashboard.js").read_text(encoding="utf-8")

    assert 'id="workspace-history"' in index
    assert "loadWorkspaceHistory" in script
    assert "compareWorkspaceRuns" in script
    assert "/api/workspace/runs" in script
    assert "workspaceSourceLabel" in script
