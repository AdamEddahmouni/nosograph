from datetime import datetime, timezone
from pathlib import Path

from med_research.web.services.workspace_store import WorkspaceRunStore

from .test_evidence_workspace_reviews import _dossier, _save


def test_dashboard_contains_review_alert_inbox():
    root = Path(__file__).parents[1] / "src/med_research/web/static"
    index = (root / "index.html").read_text(encoding="utf-8")
    script = (root / "js/dashboard.js").read_text(encoding="utf-8")

    assert 'id="workspace-alerts"' in index
    assert "loadWorkspaceAlerts" in script
    assert "/api/workspace/alerts" in script
    assert "openWorkspaceAlert" in script
    assert "previewWorkspaceDigest" in script
    assert "/api/workspace/digest" in script
    assert 'id="workspace-weekly-digest-enabled"' in index


def test_new_evidence_creates_one_researcher_scoped_review_reminder(tmp_path):
    store = WorkspaceRunStore(tmp_path / "workspace.sqlite3")
    old = _dossier("ew-alert-old", 70.0, "pmid-old")
    new = _dossier("ew-alert-new", 86.0, "pmid-new")
    old.completed_at = datetime(2026, 1, 1, tzinfo=timezone.utc)
    new.completed_at = datetime(2026, 1, 2, tzinfo=timezone.utc)
    _save(store, old)
    _save(store, new)
    store.upsert_review(
        "ew-alert-old",
        "tofacitinib",
        "drug",
        "Tofacitinib",
        "pinned",
        "Prioritize follow-up",
        "",
        ["priority"],
        "",
        "fp-old",
        researcher_id="alice",
    )

    assert store.refresh_alerts("alice") == 1
    assert store.refresh_alerts("alice") == 0
    assert store.refresh_alerts("bob") == 0

    alerts = store.list_alerts("alice")
    assert alerts["unread_count"] == 1
    alert = alerts["alerts"][0]
    assert alert["kind"] == "review_reminder"
    assert alert["candidate_id"] == "tofacitinib"
    assert alert["reviewed_run_id"] == "ew-alert-old"
    assert alert["trigger_run_id"] == "ew-alert-new"
    assert alert["evidence_added"] == ["pmid-new"]
    assert alert["previous_score"] == 70.0
    assert alert["current_score"] == 86.0
    assert store.list_alerts("bob")["alerts"] == []

    assert store.mark_alert_read(alert["alert_id"], "alice") is True
    assert store.list_alerts("alice", unread_only=True)["alerts"] == []
    assert store.mark_alert_read(alert["alert_id"], "bob") is False


def test_rejected_candidates_also_generate_reminders_and_api_scopes_them(monkeypatch, tmp_path):
    from fastapi.testclient import TestClient

    import med_research.web.routers.workspace as workspace_router
    from med_research.web.main import app

    db_path = tmp_path / "workspace.sqlite3"
    store = WorkspaceRunStore(db_path)
    old = _dossier("ew-api-alert-old", 77.0, "pmid-old")
    new = _dossier("ew-api-alert-new", 61.0, "pmid-new")
    old.completed_at = datetime(2026, 2, 1, tzinfo=timezone.utc)
    new.completed_at = datetime(2026, 2, 2, tzinfo=timezone.utc)
    _save(store, old)
    _save(store, new)
    store.upsert_review(
        "ew-api-alert-old",
        "tofacitinib",
        "drug",
        "Tofacitinib",
        "rejected",
        "Safety concern",
        "",
        [],
        "",
        "fp-api-old",
        researcher_id="alice",
    )
    monkeypatch.setattr(workspace_router, "WORKSPACE_DB_PATH", db_path)

    with TestClient(app) as client:
        alice = client.get("/api/workspace/alerts", headers={"X-Researcher-ID": "alice"})
        bob = client.get("/api/workspace/alerts", headers={"X-Researcher-ID": "bob"})
        alert_id = alice.json()["alerts"][0]["alert_id"]
        read = client.post(
            f"/api/workspace/alerts/{alert_id}/read",
            headers={"X-Researcher-ID": "alice"},
        )
        bob_read = client.post(
            f"/api/workspace/alerts/{alert_id}/read",
            headers={"X-Researcher-ID": "bob"},
        )

    assert alice.status_code == 200
    assert alice.json()["unread_count"] == 1
    assert "rejected" in alice.json()["alerts"][0]["message"]
    assert bob.status_code == 200
    assert bob.json()["alerts"] == []
    assert read.status_code == 200
    assert bob_read.status_code == 404
