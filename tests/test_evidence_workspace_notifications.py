from datetime import datetime, timezone

import pytest

from med_research.web.services import notifications
from med_research.web.services.workspace_store import WorkspaceRunStore

from .test_evidence_workspace_reviews import _dossier, _save

pytestmark = pytest.mark.unit


def _store_with_alert(tmp_path):
    store = WorkspaceRunStore(tmp_path / "workspace.sqlite3")
    old = _dossier("ew-notify-old", 70.0, "pmid-old")
    new = _dossier("ew-notify-new", 86.0, "pmid-new")
    old.completed_at = datetime(2026, 3, 1, tzinfo=timezone.utc)
    new.completed_at = datetime(2026, 3, 2, tzinfo=timezone.utc)
    _save(store, old)
    _save(store, new)
    store.upsert_review(
        "ew-notify-old",
        "tofacitinib",
        "drug",
        "Tofacitinib",
        "pinned",
        "Follow up",
        "",
        ["priority"],
        "",
        "fp-notify",
        researcher_id="alice",
    )
    assert store.refresh_alerts("alice") == 1
    return store


def test_dispatch_delivers_each_configured_channel_once(monkeypatch, tmp_path):
    store = _store_with_alert(tmp_path)
    store.save_notification_settings(
        "alice",
        "alice@example.org",
        True,
        "https://hooks.slack.com/services/T000/B000/secret",
        True,
    )
    monkeypatch.setenv("ALERT_SMTP_HOST", "smtp.test")
    sent: dict[str, list[tuple[str, str]]] = {"email": [], "slack": []}
    monkeypatch.setattr(
        notifications,
        "send_email_alert",
        lambda alert, recipient: sent["email"].append((alert["alert_id"], recipient)),
    )
    monkeypatch.setattr(
        notifications,
        "send_slack_alert",
        lambda alert, webhook: sent["slack"].append((alert["alert_id"], webhook)),
    )

    first = notifications.dispatch_pending_alerts(store, "alice")
    second = notifications.dispatch_pending_alerts(store, "alice")

    assert first["email_delivered"] == 1
    assert first["slack_delivered"] == 1
    assert second["email_delivered"] == 0
    assert second["slack_delivered"] == 0
    assert len(sent["email"]) == 1
    assert len(sent["slack"]) == 1
    settings = store.get_notification_settings("alice")
    assert settings["slack_configured"] is True
    assert settings["delivery"]["email"]["status"] == "delivered"
    assert settings["delivery"]["slack"]["status"] == "delivered"


def test_failed_delivery_is_recorded_and_retryable(monkeypatch, tmp_path):
    store = _store_with_alert(tmp_path)
    store.save_notification_settings(
        "alice", "", False, "https://hooks.slack.com/services/T000/B000/secret", True
    )
    attempts = {"count": 0}

    def fail_once(alert, webhook):
        attempts["count"] += 1
        if attempts["count"] == 1:
            raise RuntimeError("Slack unavailable")

    monkeypatch.setattr(notifications, "send_slack_alert", fail_once)
    first = notifications.dispatch_pending_alerts(store, "alice")
    second = notifications.dispatch_pending_alerts(store, "alice")

    assert first["failed"] == 1
    assert second["slack_delivered"] == 1
    settings = store.get_notification_settings("alice")
    assert settings["delivery"]["slack"]["attempts"] == 2
    assert settings["delivery"]["slack"]["status"] == "delivered"


def test_notification_settings_api_masks_slack_secret(monkeypatch, tmp_path):
    from fastapi.testclient import TestClient

    import med_research.web.routers.workspace as workspace_router
    from med_research.web.main import app

    db_path = tmp_path / "workspace.sqlite3"
    monkeypatch.setattr(workspace_router, "WORKSPACE_DB_PATH", db_path)
    with TestClient(app) as client:
        saved = client.put(
            "/api/workspace/notifications",
            headers={"X-Researcher-ID": "alice"},
            json={
                "email": "alice@example.org",
                "email_enabled": False,
                "slack_webhook_url": "https://hooks.slack.com/services/T000/B000/secret",
                "slack_enabled": True,
                "score_drop_threshold": 12.5,
                "rank_change_threshold": 2,
                "evidence_quality_change_threshold": 0.15,
                "weekly_digest_enabled": True,
                "weekly_digest_weekday": 2,
                "weekly_digest_hour": 14,
                "weekly_digest_minute": 30,
                "weekly_digest_timezone": "America/New_York",
            },
        )
        loaded = client.get("/api/workspace/notifications", headers={"X-Researcher-ID": "alice"})

    assert saved.status_code == 200
    assert loaded.status_code == 200
    assert loaded.json()["email"] == "alice@example.org"
    assert loaded.json()["slack_configured"] is True
    assert loaded.json()["score_drop_threshold"] == 12.5
    assert loaded.json()["rank_change_threshold"] == 2
    assert loaded.json()["evidence_quality_change_threshold"] == 0.15
    assert loaded.json()["weekly_digest_enabled"] is True
    assert loaded.json()["weekly_digest_weekday"] == 2
    assert loaded.json()["weekly_digest_hour"] == 14
    assert loaded.json()["weekly_digest_minute"] == 30
    assert loaded.json()["weekly_digest_timezone"] == "America/New_York"
    assert "slack_webhook_url" not in loaded.json()
