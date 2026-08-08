"""Optional delivery adapters for researcher-owned Workspace alerts."""

from __future__ import annotations

import os
import smtplib
from datetime import datetime
from email.message import EmailMessage
from typing import Any
from urllib.parse import urlparse

import requests

from med_research.web.services.review_links import create_review_link
from med_research.web.services.workspace_store import WorkspaceRunStore


def _slack_webhook_is_safe(webhook_url: str) -> bool:
    parsed = urlparse(webhook_url)
    return parsed.scheme == "https" and parsed.hostname in {
        "hooks.slack.com",
        "hooks.slack-gov.com",
    }


def _alert_text(alert: dict[str, Any]) -> str:
    evidence = ", ".join(alert.get("evidence_added", [])) or "none"
    metrics = []
    if alert.get("score_drop", 0) > 0:
        metrics.append(f"score drop: {alert['score_drop']:.1f}")
    if alert.get("rank_change", 0) > 0:
        metrics.append(f"rank movement: {alert['rank_change']}")
    if alert.get("quality_change") is not None:
        metrics.append(f"evidence quality change: {alert['quality_change']:+.2f}")
    return (
        f"{alert.get('title', 'Workspace review reminder')}\n\n"
        f"{alert.get('message', '')}\n"
        f"Evidence added: {evidence}\n"
        f"Metrics: {', '.join(metrics) or 'no configured metric threshold exceeded'}\n"
        f"Trigger run: {alert.get('trigger_run_id', '')}"
    )


def send_slack_alert(alert: dict[str, Any], webhook_url: str) -> None:
    """Send one alert to a Slack Incoming Webhook."""
    if not _slack_webhook_is_safe(webhook_url):
        raise ValueError("Slack webhook must use an HTTPS Slack webhook host")
    response = requests.post(
        webhook_url,
        json={"text": _alert_text(alert)},
        timeout=10,
    )
    response.raise_for_status()


def _send_email_message(subject: str, text: str, recipient: str) -> None:
    host = os.environ.get("ALERT_SMTP_HOST", "").strip()
    if not host:
        raise RuntimeError("ALERT_SMTP_HOST is not configured")
    port = int(os.environ.get("ALERT_SMTP_PORT", "587"))
    username = os.environ.get("ALERT_SMTP_USERNAME", "").strip()
    password = os.environ.get("ALERT_SMTP_PASSWORD", "")
    sender = os.environ.get("ALERT_SMTP_FROM", "").strip() or username or "alerts@localhost"
    use_tls = os.environ.get("ALERT_SMTP_USE_TLS", "true").lower() not in {"0", "false", "no"}

    message = EmailMessage()
    message["Subject"] = subject
    message["From"] = sender
    message["To"] = recipient
    message.set_content(text)

    smtp_class = smtplib.SMTP_SSL if port == 465 else smtplib.SMTP
    with smtp_class(host, port, timeout=15) as smtp:
        if port != 465 and use_tls:
            smtp.starttls()
        if username:
            smtp.login(username, password)
        smtp.send_message(message)


def send_email_alert(alert: dict[str, Any], recipient: str) -> None:
    """Send one alert using the deployment's opt-in SMTP configuration."""
    _send_email_message(alert.get("title", "Workspace review reminder"), _alert_text(alert), recipient)


def render_weekly_digest(digest: dict[str, Any]) -> str:
    lines = [
        "Weekly Evidence Workspace Digest",
        "=================================",
        f"Period: {digest['period_start'][:10]} through {digest['period_end'][:10]}",
        f"Review reminders: {digest['review_url']}" if digest.get("review_url") else "",
        "",
        f"New evidence: {digest['new_evidence_count']}",
    ]
    for item in digest["new_evidence"]:
        lines.append(
            f"- {item['candidate_name']} ({item['candidate_type']}): "
            f"{item['evidence_id']} in run {item['trigger_run_id']}"
        )
    lines.extend(["", f"Unresolved reminders: {digest['unresolved_reminder_count']}"])
    for alert in digest["unresolved_reminders"]:
        lines.append(f"- {alert['title']}: {alert['message']}")
    lines.extend(["", f"Changed decisions: {digest['changed_decision_count']}"])
    for decision in digest["changed_decisions"]:
        lines.append(
            f"- {decision['candidate_id']} ({decision['candidate_type']}): "
            f"{decision['previous_decision']} → {decision['decision']}"
        )
        if decision.get("changed_my_mind"):
            lines.append(f"  What changed my mind: {decision['changed_my_mind']}")
    if not digest["new_evidence"] and not digest["unresolved_reminders"] and not digest["changed_decisions"]:
        lines.extend(["", "No new evidence, unresolved reminders, or changed decisions."])
    return "\n".join(lines)


def send_email_digest(digest: dict[str, Any], recipient: str) -> None:
    _send_email_message(
        f"Weekly Evidence Workspace Digest ({digest['period_start'][:10]})",
        digest["markdown"],
        recipient,
    )


def send_slack_digest(digest: dict[str, Any], webhook_url: str) -> None:
    if not _slack_webhook_is_safe(webhook_url):
        raise ValueError("Slack webhook must use an HTTPS Slack webhook host")
    response = requests.post(
        webhook_url,
        json={"text": digest["markdown"]},
        timeout=10,
    )
    response.raise_for_status()


def dispatch_weekly_digest(
    store: WorkspaceRunStore,
    researcher_id: str,
    *,
    force: bool = False,
    now: datetime | None = None,
    raise_on_failure: bool = False,
) -> dict[str, Any]:
    """Send the completed previous calendar week's digest once per channel."""
    settings = store._notification_settings_raw(researcher_id)
    if not settings.get("weekly_digest_enabled"):
        return {"status": "disabled", "email_delivered": 0, "slack_delivered": 0, "failed": 0}
    digest = store.build_weekly_digest(researcher_id, now=now)
    digest["review_url"] = create_review_link(researcher_id, digest["digest_key"], now=now)
    digest["markdown"] = render_weekly_digest(digest)
    if not (
        digest["new_evidence"]
        or digest["unresolved_reminders"]
        or digest["changed_decisions"]
    ):
        digest["status"] = "empty"
        digest["email_delivered"] = 0
        digest["slack_delivered"] = 0
        digest["failed"] = 0
        return digest

    email_recipient = settings.get("email", "") if settings.get("email_enabled") else ""
    slack_webhook = settings.get("slack_webhook_url", "") if settings.get("slack_enabled") else ""
    delivered: dict[str, Any] = {
        "status": "attempted",
        "email_delivered": 0,
        "slack_delivered": 0,
        "failed": 0,
    }
    channels = []
    if email_recipient and os.environ.get("ALERT_SMTP_HOST", "").strip():
        channels.append(
            (
                "email",
                lambda digest=digest, recipient=email_recipient: send_email_digest(
                    digest, recipient
                ),
            )
        )
    if slack_webhook:
        channels.append(
            (
                "slack",
                lambda digest=digest, webhook=slack_webhook: send_slack_digest(
                    digest, webhook
                ),
            )
        )
    for channel, send in channels:
        if not force and store.digest_delivery_completed(digest["digest_key"], researcher_id, channel):
            continue
        try:
            send()
        except Exception as exc:  # delivery must not break preview/polling
            store.record_digest_delivery_attempt(
                digest["digest_key"], researcher_id, channel, delivered=False,
                error=f"{type(exc).__name__}: {exc}",
            )
            delivered["failed"] += 1
            if raise_on_failure:
                raise
        else:
            store.record_digest_delivery_attempt(
                digest["digest_key"], researcher_id, channel, delivered=True
            )
            delivered[f"{channel}_delivered"] += 1
    digest.update(delivered)
    return digest


def dispatch_pending_alerts(store: WorkspaceRunStore, researcher_id: str) -> dict[str, int]:
    """Deliver unread alerts once per configured channel; failures remain retryable."""
    settings = store._notification_settings_raw(researcher_id)
    email_recipient = settings.get("email", "") if settings.get("email_enabled") else ""
    slack_webhook = settings.get("slack_webhook_url", "") if settings.get("slack_enabled") else ""
    if not email_recipient and not slack_webhook:
        return {"email_delivered": 0, "slack_delivered": 0, "failed": 0, "skipped": 0}

    delivered = {"email_delivered": 0, "slack_delivered": 0, "failed": 0, "skipped": 0}
    for alert in store.pending_alerts_for_delivery(researcher_id):
        channels = []
        if email_recipient:
            if os.environ.get("ALERT_SMTP_HOST", "").strip():
                channels.append(
                    (
                        "email",
                        lambda alert=alert, recipient=email_recipient: send_email_alert(
                            alert, recipient
                        ),
                    )
                )
            else:
                delivered["skipped"] += 1
        if slack_webhook:
            channels.append(
                (
                    "slack",
                    lambda alert=alert, webhook=slack_webhook: send_slack_alert(
                        alert, webhook
                    ),
                )
            )
        for channel, send in channels:
            if store.delivery_completed(alert["alert_id"], researcher_id, channel):
                delivered["skipped"] += 1
                continue
            try:
                send()
            except Exception as exc:  # delivery must not break alert reads
                store.record_delivery_attempt(
                    alert["alert_id"],
                    researcher_id,
                    channel,
                    delivered=False,
                    error=f"{type(exc).__name__}: {exc}",
                )
                delivered["failed"] += 1
            else:
                store.record_delivery_attempt(
                    alert["alert_id"], researcher_id, channel, delivered=True
                )
                delivered[f"{channel}_delivered"] += 1
    return delivered
