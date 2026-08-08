from datetime import datetime, timezone

from med_research.web.services import notifications
from med_research.web.services.workspace_store import WorkspaceRunStore

from .test_evidence_workspace_reviews import _dossier, _save


def _store_with_weekly_digest_data(tmp_path):
    store = WorkspaceRunStore(tmp_path / "workspace.sqlite3")
    old = _dossier("ew-digest-old", 80.0, "pmid-digest-old")
    new = _dossier("ew-digest-new", 85.0, "pmid-digest-new")
    old.completed_at = datetime(2026, 3, 1, tzinfo=timezone.utc)
    new.completed_at = datetime(2026, 3, 2, tzinfo=timezone.utc)
    _save(store, old)
    _save(store, new)
    store.upsert_review(
        "ew-digest-old",
        "tofacitinib",
        "drug",
        "Tofacitinib",
        "pinned",
        "Initial priority",
        "",
        [],
        "",
        "fp-digest",
        researcher_id="alice",
    )
    store.refresh_alerts("alice")
    store.upsert_review(
        "ew-digest-old",
        "tofacitinib",
        "drug",
        "Tofacitinib",
        "rejected",
        "Safety concern",
        "Revisit after more data",
        [],
        "The safety signal changed my mind.",
        "fp-digest",
        researcher_id="alice",
    )
    with store._connect() as connection:
        connection.execute(
            "UPDATE workspace_alerts SET created_at=? WHERE researcher_id=?",
            ("2026-03-03T12:00:00+00:00", "alice"),
        )
        connection.execute(
            "UPDATE workspace_review_events SET recorded_at=? WHERE researcher_id=?",
            ("2026-03-04T12:00:00+00:00", "alice"),
        )
    return store


def test_weekly_digest_summarizes_evidence_reminders_and_decisions(tmp_path):
    store = _store_with_weekly_digest_data(tmp_path)
    digest = store.build_weekly_digest(
        "alice", now=datetime(2026, 3, 9, 12, tzinfo=timezone.utc)
    )

    assert digest["digest_key"] == "weekly-2026-03-02"
    assert digest["new_evidence_count"] == 1
    assert digest["new_evidence"][0]["evidence_id"] == "pmid-digest-new"
    assert digest["unresolved_reminder_count"] == 1
    assert digest["changed_decision_count"] == 2
    assert digest["changed_decisions"][-1]["decision"] == "rejected"


def test_weekly_digest_delivery_is_idempotent(monkeypatch, tmp_path):
    store = _store_with_weekly_digest_data(tmp_path)
    store.save_notification_settings(
        "alice",
        "alice@example.org",
        True,
        "https://hooks.slack.com/services/T000/B000/digest",
        True,
        weekly_digest_enabled=True,
    )
    monkeypatch.setenv("ALERT_SMTP_HOST", "smtp.test")
    sent = {"email": 0, "slack": 0}
    monkeypatch.setattr(
        notifications,
        "send_email_digest",
        lambda digest, recipient: sent.__setitem__("email", sent["email"] + 1),
    )
    monkeypatch.setattr(
        notifications,
        "send_slack_digest",
        lambda digest, webhook: sent.__setitem__("slack", sent["slack"] + 1),
    )

    first = notifications.dispatch_weekly_digest(
        store, "alice", now=datetime(2026, 3, 9, 12, tzinfo=timezone.utc)
    )
    second = notifications.dispatch_weekly_digest(
        store, "alice", now=datetime(2026, 3, 9, 12, tzinfo=timezone.utc)
    )

    assert first["email_delivered"] == 1
    assert first["slack_delivered"] == 1
    assert second["email_delivered"] == 0
    assert second["slack_delivered"] == 0
    assert sent == {"email": 1, "slack": 1}
    assert "Weekly Evidence Workspace Digest" in first["markdown"]
