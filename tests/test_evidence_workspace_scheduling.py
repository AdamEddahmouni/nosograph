from datetime import datetime, timezone

import pytest

from med_research.web.services.review_links import create_review_link, verify_review_token
from med_research.web.services.workspace_store import WorkspaceRunStore
from med_research.web.tasks.analysis_tasks import celery_app

pytestmark = pytest.mark.unit


def test_due_digest_researchers_use_configured_local_schedule(tmp_path):
    store = WorkspaceRunStore(tmp_path / "workspace.sqlite3")
    store.save_notification_settings(
        "alice",
        "alice@example.org",
        True,
        "",
        False,
        weekly_digest_enabled=True,
        weekly_digest_weekday=0,
        weekly_digest_hour=9,
        weekly_digest_minute=30,
        weekly_digest_timezone="America/New_York",
    )
    monday_0930_new_york = datetime(2026, 3, 9, 13, 30, tzinfo=timezone.utc)
    monday_1030_new_york = datetime(2026, 3, 9, 14, 30, tzinfo=timezone.utc)

    assert store.due_weekly_digest_researchers(monday_0930_new_york) == ["alice"]
    assert store.due_weekly_digest_researchers(monday_1030_new_york) == []


def test_digest_review_links_are_signed_and_expiring(monkeypatch):
    monkeypatch.setenv("WORKSPACE_REVIEW_LINK_SECRET", "test-secret")
    monkeypatch.setenv("WORKSPACE_PUBLIC_URL", "https://research.example.org")
    now = datetime(2026, 3, 9, tzinfo=timezone.utc)
    link = create_review_link("alice", "weekly-2026-03-02", now=now)

    assert link is not None
    token = link.split("token=", 1)[1]
    assert verify_review_token(token, now=now) == {
        "researcher_id": "alice",
        "digest_key": "weekly-2026-03-02",
    }
    assert verify_review_token(token, now=datetime(2026, 3, 18, tzinfo=timezone.utc)) is None
    assert verify_review_token(token + "x", now=now) is None


def test_secure_review_endpoint_redirects_only_valid_tokens(monkeypatch):
    from fastapi.testclient import TestClient

    from med_research.web.main import app

    monkeypatch.setenv("WORKSPACE_REVIEW_LINK_SECRET", "test-secret")
    now = datetime.now(timezone.utc)
    link = create_review_link("alice", "weekly-2026-03-02", now=now)
    assert link is not None
    token = link.split("token=", 1)[1]
    with TestClient(app) as client:
        response = client.get(f"/api/workspace/digest/review?token={token}", follow_redirects=False)
        invalid = client.get("/api/workspace/digest/review?token=invalid", follow_redirects=False)

    assert response.status_code == 303
    assert "researcher_id=alice" in response.headers["location"]
    assert invalid.status_code == 401


def test_celery_beat_and_retry_configuration_are_registered():
    schedule = celery_app.conf.beat_schedule["workspace-digest-dispatcher"]
    task = celery_app.tasks["dispatch_workspace_digest"]

    assert schedule["task"] == "dispatch_workspace_digests"
    assert schedule["schedule"] == 60.0
    assert task.autoretry_for == (Exception,)
    assert task.retry_backoff is True
    assert task.retry_backoff_max == 3600
    assert task.max_retries == 5
