"""SQLite persistence for Evidence-to-Hypothesis Workspace dossiers."""

from __future__ import annotations

import hashlib
import json
import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from med_research.pipeline.evidence_workspace.schemas import EvidenceDossier, ResearchRequest
from med_research.web.identity import DEFAULT_RESEARCHER_ID


def _candidate_evidence_ids(
    dossier: dict[str, Any], candidate_type: str, candidate_id: str
) -> set[str]:
    rankings = dossier.get(f"{candidate_type}_rankings", [])
    candidate = next(
        (item for item in rankings if item.get("candidate_id") == candidate_id), None
    )
    if not candidate:
        return set()
    claims_by_id = {claim.get("claim_id"): claim for claim in dossier.get("claims", [])}
    claim_ids = set(candidate.get("supporting_claim_ids", [])) | set(
        candidate.get("contradicting_claim_ids", [])
    )
    return {
        evidence_id
        for claim_id in claim_ids
        for evidence_id in claims_by_id.get(claim_id, {}).get("evidence_ids", [])
    }


def _candidate_evidence_quality(
    dossier: dict[str, Any], candidate_type: str, candidate_id: str
) -> float | None:
    evidence_ids = _candidate_evidence_ids(dossier, candidate_type, candidate_id)
    scores = [
        record.get("quality_score")
        for record in dossier.get("evidence", [])
        if record.get("evidence_id") in evidence_ids
        and isinstance(record.get("quality_score"), (int, float))
    ]
    return round(sum(scores) / len(scores), 6) if scores else None


class WorkspaceRunStore:
    """Persist workspace run metadata and exact JSON/HTML dossier outputs."""

    def __init__(self, path: str | Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._initialize()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.path)
        connection.row_factory = sqlite3.Row
        return connection

    @staticmethod
    def _ensure_columns(
        connection: sqlite3.Connection,
        table: str,
        columns: dict[str, str],
    ) -> None:
        existing = {
            row[1] for row in connection.execute(f"PRAGMA table_info({table})").fetchall()
        }
        for name, definition in columns.items():
            if name not in existing:
                connection.execute(f"ALTER TABLE {table} ADD COLUMN {name} {definition}")

    def _initialize(self) -> None:
        with self._connect() as connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS workspace_runs (
                    run_id TEXT PRIMARY KEY,
                    disease_id TEXT NOT NULL,
                    question TEXT NOT NULL,
                    status TEXT NOT NULL,
                    request_json TEXT NOT NULL,
                    dossier_json TEXT,
                    html_export TEXT,
                    error TEXT,
                    evidence_count INTEGER NOT NULL DEFAULT 0,
                    claim_count INTEGER NOT NULL DEFAULT 0,
                    drug_count INTEGER NOT NULL DEFAULT 0,
                    target_count INTEGER NOT NULL DEFAULT 0,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
                """
            )
            self._ensure_columns(
                connection,
                "workspace_runs",
                {"researcher_id": "TEXT NOT NULL DEFAULT 'anonymous'"},
            )
            connection.execute(
                "CREATE INDEX IF NOT EXISTS idx_workspace_runs_updated "
                "ON workspace_runs(updated_at DESC)"
            )
            connection.execute(
                "CREATE INDEX IF NOT EXISTS idx_workspace_runs_researcher "
                "ON workspace_runs(researcher_id, updated_at DESC)"
            )
            self._ensure_review_tables(connection)
            connection.execute(
                "CREATE INDEX IF NOT EXISTS idx_workspace_reviews_candidate "
                "ON workspace_reviews(candidate_type, candidate_id, updated_at DESC)"
            )
            connection.execute(
                "CREATE INDEX IF NOT EXISTS idx_workspace_review_events_candidate "
                "ON workspace_review_events(candidate_type, candidate_id, recorded_at DESC)"
            )
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS workspace_alerts (
                    alert_id TEXT PRIMARY KEY,
                    researcher_id TEXT NOT NULL,
                    kind TEXT NOT NULL,
                    candidate_id TEXT NOT NULL,
                    candidate_type TEXT NOT NULL,
                    candidate_name TEXT NOT NULL,
                    reviewed_run_id TEXT NOT NULL,
                    trigger_run_id TEXT NOT NULL,
                    title TEXT NOT NULL,
                    message TEXT NOT NULL,
                    evidence_added_json TEXT NOT NULL DEFAULT '[]',
                    evidence_removed_json TEXT NOT NULL DEFAULT '[]',
                    previous_score REAL,
                    current_score REAL,
                    previous_rank INTEGER,
                    current_rank INTEGER,
                    created_at TEXT NOT NULL,
                    read_at TEXT
                )
                """
            )
            self._ensure_columns(
                connection,
                "workspace_alerts",
                {
                    "score_drop": "REAL NOT NULL DEFAULT 0",
                    "rank_change": "INTEGER NOT NULL DEFAULT 0",
                    "previous_quality": "REAL",
                    "current_quality": "REAL",
                    "quality_change": "REAL",
                    "trigger_reasons_json": "TEXT NOT NULL DEFAULT '[]'",
                },
            )
            connection.execute(
                "CREATE INDEX IF NOT EXISTS idx_workspace_alerts_researcher "
                "ON workspace_alerts(researcher_id, read_at, created_at DESC)"
            )
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS workspace_notification_settings (
                    researcher_id TEXT PRIMARY KEY,
                    email TEXT NOT NULL DEFAULT '',
                    email_enabled INTEGER NOT NULL DEFAULT 1,
                    slack_webhook_url TEXT NOT NULL DEFAULT '',
                    slack_enabled INTEGER NOT NULL DEFAULT 1,
                    updated_at TEXT NOT NULL
                )
                """
            )
            self._ensure_columns(
                connection,
                "workspace_notification_settings",
                {
                    "score_drop_threshold": "REAL NOT NULL DEFAULT 0",
                    "rank_change_threshold": "INTEGER NOT NULL DEFAULT 0",
                    "evidence_quality_change_threshold": "REAL NOT NULL DEFAULT 0",
                    "weekly_digest_enabled": "INTEGER NOT NULL DEFAULT 0",
                    "weekly_digest_weekday": "INTEGER NOT NULL DEFAULT 0",
                    "weekly_digest_hour": "INTEGER NOT NULL DEFAULT 9",
                    "weekly_digest_minute": "INTEGER NOT NULL DEFAULT 0",
                    "weekly_digest_timezone": "TEXT NOT NULL DEFAULT 'UTC'",
                },
            )
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS workspace_alert_deliveries (
                    alert_id TEXT NOT NULL,
                    researcher_id TEXT NOT NULL,
                    channel TEXT NOT NULL,
                    status TEXT NOT NULL,
                    attempts INTEGER NOT NULL DEFAULT 0,
                    last_attempt_at TEXT,
                    delivered_at TEXT,
                    error TEXT,
                    PRIMARY KEY (alert_id, researcher_id, channel)
                )
                """
            )
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS workspace_digest_deliveries (
                    digest_key TEXT NOT NULL,
                    researcher_id TEXT NOT NULL,
                    channel TEXT NOT NULL,
                    status TEXT NOT NULL,
                    attempts INTEGER NOT NULL DEFAULT 0,
                    last_attempt_at TEXT,
                    delivered_at TEXT,
                    error TEXT,
                    PRIMARY KEY (digest_key, researcher_id, channel)
                )
                """
            )
            connection.execute(
                "CREATE INDEX IF NOT EXISTS idx_workspace_digest_deliveries_researcher "
                "ON workspace_digest_deliveries(researcher_id, last_attempt_at DESC)"
            )

    @staticmethod
    def _ensure_review_tables(connection: sqlite3.Connection) -> None:
        """Create ownership-aware review tables and migrate the pre-identity schema."""
        legacy_reviews = False
        legacy_events = False
        review_columns = {
            row[1]
            for row in connection.execute("PRAGMA table_info(workspace_reviews)").fetchall()
        }
        if review_columns and "researcher_id" not in review_columns:
            connection.execute("DROP INDEX IF EXISTS idx_workspace_reviews_candidate")
            connection.execute("ALTER TABLE workspace_reviews RENAME TO workspace_reviews_legacy")
            legacy_reviews = True
        event_columns = {
            row[1]
            for row in connection.execute("PRAGMA table_info(workspace_review_events)").fetchall()
        }
        if event_columns and "researcher_id" not in event_columns:
            connection.execute("DROP INDEX IF EXISTS idx_workspace_review_events_candidate")
            connection.execute(
                "ALTER TABLE workspace_review_events RENAME TO workspace_review_events_legacy"
            )
            legacy_events = True

        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS workspace_reviews (
                run_id TEXT NOT NULL,
                researcher_id TEXT NOT NULL DEFAULT 'anonymous',
                candidate_id TEXT NOT NULL,
                candidate_type TEXT NOT NULL,
                candidate_name TEXT NOT NULL DEFAULT '',
                decision TEXT NOT NULL DEFAULT 'unreviewed',
                rationale TEXT NOT NULL DEFAULT '',
                notes TEXT NOT NULL DEFAULT '',
                tags_json TEXT NOT NULL DEFAULT '[]',
                changed_my_mind TEXT NOT NULL DEFAULT '',
                provenance_fingerprint TEXT NOT NULL DEFAULT '',
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                PRIMARY KEY (run_id, researcher_id, candidate_type, candidate_id)
            )
            """
        )
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS workspace_review_events (
                event_id INTEGER PRIMARY KEY AUTOINCREMENT,
                run_id TEXT NOT NULL,
                researcher_id TEXT NOT NULL DEFAULT 'anonymous',
                candidate_id TEXT NOT NULL,
                candidate_type TEXT NOT NULL,
                previous_decision TEXT NOT NULL,
                decision TEXT NOT NULL,
                rationale TEXT NOT NULL DEFAULT '',
                notes TEXT NOT NULL DEFAULT '',
                tags_json TEXT NOT NULL DEFAULT '[]',
                changed_my_mind TEXT NOT NULL DEFAULT '',
                provenance_fingerprint TEXT NOT NULL DEFAULT '',
                recorded_at TEXT NOT NULL
            )
            """
        )
        if legacy_reviews:
            connection.execute(
                """
                INSERT INTO workspace_reviews
                (run_id, researcher_id, candidate_id, candidate_type, candidate_name, decision,
                 rationale, notes, tags_json, changed_my_mind, provenance_fingerprint, created_at, updated_at)
                SELECT run_id, ?, candidate_id, candidate_type, candidate_name, decision,
                       rationale, notes, tags_json, changed_my_mind, provenance_fingerprint, created_at, updated_at
                FROM workspace_reviews_legacy
                """,
                (DEFAULT_RESEARCHER_ID,),
            )
            connection.execute("DROP TABLE workspace_reviews_legacy")
        if legacy_events:
            connection.execute(
                """
                INSERT INTO workspace_review_events
                (event_id, run_id, researcher_id, candidate_id, candidate_type, previous_decision,
                 decision, rationale, notes, tags_json, changed_my_mind, provenance_fingerprint, recorded_at)
                SELECT event_id, run_id, ?, candidate_id, candidate_type, previous_decision,
                       decision, rationale, notes, tags_json, changed_my_mind, provenance_fingerprint, recorded_at
                FROM workspace_review_events_legacy
                """,
                (DEFAULT_RESEARCHER_ID,),
            )
            connection.execute("DROP TABLE workspace_review_events_legacy")

    @staticmethod
    def _now() -> str:
        return datetime.now(timezone.utc).isoformat()

    @staticmethod
    def _request_json(request: ResearchRequest) -> str:
        return json.dumps(request.model_dump(mode="json"), sort_keys=True)

    def create_run(
        self,
        run_id: str,
        request: ResearchRequest,
        researcher_id: str = DEFAULT_RESEARCHER_ID,
    ) -> None:
        now = self._now()
        with self._connect() as connection:
            connection.execute(
                """
                INSERT OR REPLACE INTO workspace_runs
                (run_id, researcher_id, disease_id, question, status, request_json, created_at, updated_at)
                VALUES (?, ?, ?, ?, 'PENDING', ?, ?, ?)
                """,
                (
                    run_id,
                    researcher_id,
                    request.disease_id,
                    request.question,
                    self._request_json(request),
                    now,
                    now,
                ),
            )

    def save_success(self, dossier: EvidenceDossier, html: str) -> None:
        now = self._now()
        dossier_json = json.dumps(dossier.model_dump(mode="json"), ensure_ascii=False)
        with self._connect() as connection:
            cursor = connection.execute(
                """
                UPDATE workspace_runs
                SET status='SUCCESS', dossier_json=?, html_export=?, error=NULL,
                    evidence_count=?, claim_count=?, drug_count=?, target_count=?, updated_at=?
                WHERE run_id=?
                """,
                (
                    dossier_json,
                    html,
                    len(dossier.evidence),
                    len(dossier.claims),
                    len(dossier.drug_rankings),
                    len(dossier.target_rankings),
                    now,
                    dossier.run_id,
                ),
            )
            if cursor.rowcount != 1:
                raise KeyError(dossier.run_id)

    def mark_failed(self, run_id: str, error: str) -> None:
        with self._connect() as connection:
            connection.execute(
                "UPDATE workspace_runs SET status='FAILURE', error=?, updated_at=? WHERE run_id=?",
                (error, self._now(), run_id),
            )

    def list_runs(self, limit: int = 50, offset: int = 0) -> list[dict[str, Any]]:
        limit = max(1, min(int(limit), 200))
        offset = max(0, int(offset))
        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT run_id, disease_id, question, status, error, evidence_count,
                       claim_count, drug_count, target_count, created_at, updated_at
                FROM workspace_runs ORDER BY updated_at DESC LIMIT ? OFFSET ?
                """,
                (limit, offset),
            ).fetchall()
        return [dict(row) for row in rows]

    def get_run(self, run_id: str) -> dict[str, Any] | None:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT * FROM workspace_runs WHERE run_id=?", (run_id,)
            ).fetchone()
        if row is None:
            return None
        result = dict(row)
        result["request"] = json.loads(result.pop("request_json"))
        result["dossier"] = json.loads(result["dossier_json"]) if result["dossier_json"] else None
        result.pop("dossier_json", None)
        result["html"] = result.pop("html_export", None)
        return result

    def delete_run(self, run_id: str) -> bool:
        with self._connect() as connection:
            cursor = connection.execute("DELETE FROM workspace_runs WHERE run_id=?", (run_id,))
            if cursor.rowcount:
                connection.execute("DELETE FROM workspace_reviews WHERE run_id=?", (run_id,))
                connection.execute("DELETE FROM workspace_review_events WHERE run_id=?", (run_id,))
        return cursor.rowcount > 0

    @staticmethod
    def _review_dict(row: sqlite3.Row) -> dict[str, Any]:
        result = dict(row)
        result["tags"] = json.loads(result.pop("tags_json") or "[]")
        return result

    def list_reviews(
        self, run_id: str, researcher_id: str = DEFAULT_RESEARCHER_ID
    ) -> list[dict[str, Any]]:
        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT run_id, researcher_id, candidate_id, candidate_type, candidate_name, decision,
                       rationale, notes, tags_json, changed_my_mind,
                       provenance_fingerprint, created_at, updated_at
                FROM workspace_reviews WHERE run_id=? AND researcher_id=?
                ORDER BY candidate_type, candidate_name, candidate_id
                """,
                (run_id, researcher_id),
            ).fetchall()
        return [self._review_dict(row) for row in rows]

    def list_review_events(
        self, run_id: str, researcher_id: str = DEFAULT_RESEARCHER_ID
    ) -> list[dict[str, Any]]:
        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT event_id, run_id, researcher_id, candidate_id, candidate_type,
                       previous_decision, decision, rationale, notes, tags_json, changed_my_mind,
                       provenance_fingerprint, recorded_at
                FROM workspace_review_events WHERE run_id=? AND researcher_id=?
                ORDER BY recorded_at, event_id
                """,
                (run_id, researcher_id),
            ).fetchall()
        return [self._review_dict(row) for row in rows]

    @staticmethod
    def _weekly_period(
        now: datetime | None = None, timezone_name: str = "UTC"
    ) -> tuple[str, datetime, datetime]:
        current = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)
        try:
            zone = ZoneInfo(timezone_name)
        except ZoneInfoNotFoundError:
            zone = ZoneInfo("UTC")
        local_current = current.astimezone(zone)
        local_week_start = (local_current - timedelta(days=local_current.weekday())).replace(
            hour=0, minute=0, second=0, microsecond=0
        )
        local_period_end = local_week_start
        local_period_start = local_period_end - timedelta(days=7)
        digest_key = f"weekly-{local_period_start.date().isoformat()}"
        return (
            digest_key,
            local_period_start.astimezone(timezone.utc),
            local_period_end.astimezone(timezone.utc),
        )

    def list_review_events_between(
        self,
        researcher_id: str,
        period_start: str,
        period_end: str,
    ) -> list[dict[str, Any]]:
        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT event_id, run_id, researcher_id, candidate_id, candidate_type,
                       previous_decision, decision, rationale, notes, tags_json, changed_my_mind,
                       provenance_fingerprint, recorded_at
                FROM workspace_review_events
                WHERE researcher_id=? AND recorded_at>=? AND recorded_at<?
                ORDER BY recorded_at, event_id
                """,
                (researcher_id, period_start, period_end),
            ).fetchall()
        return [self._review_dict(row) for row in rows]

    def build_weekly_digest(
        self, researcher_id: str = DEFAULT_RESEARCHER_ID, now: datetime | None = None
    ) -> dict[str, Any]:
        settings = self._notification_settings_raw(researcher_id)
        digest_key, period_start, period_end = self._weekly_period(
            now, settings["weekly_digest_timezone"]
        )
        period_start_text = period_start.isoformat()
        period_end_text = period_end.isoformat()
        all_alerts = self.list_alerts(researcher_id, limit=100)
        period_alerts = [
            alert
            for alert in all_alerts["alerts"]
            if period_start_text <= alert["created_at"] < period_end_text
        ]
        evidence: list[dict[str, Any]] = []
        seen_evidence: set[tuple[str, str, str]] = set()
        for alert in period_alerts:
            for evidence_id in alert.get("evidence_added", []):
                key = (evidence_id, alert["candidate_type"], alert["candidate_id"])
                if key in seen_evidence:
                    continue
                seen_evidence.add(key)
                evidence.append(
                    {
                        "evidence_id": evidence_id,
                        "candidate_id": alert["candidate_id"],
                        "candidate_type": alert["candidate_type"],
                        "candidate_name": alert["candidate_name"],
                        "trigger_run_id": alert["trigger_run_id"],
                        "created_at": alert["created_at"],
                    }
                )
        events = self.list_review_events_between(
            researcher_id, period_start_text, period_end_text
        )
        decisions = [
            {
                key: event[key]
                for key in (
                    "event_id",
                    "run_id",
                    "candidate_id",
                    "candidate_type",
                    "previous_decision",
                    "decision",
                    "rationale",
                    "notes",
                    "changed_my_mind",
                    "recorded_at",
                )
            }
            for event in events
        ]
        unresolved = self.list_alerts(researcher_id, unread_only=True, limit=100)["alerts"]
        return {
            "researcher_id": researcher_id,
            "digest_key": digest_key,
            "period_start": period_start_text,
            "period_end": period_end_text,
            "generated_at": self._now(),
            "new_evidence": evidence,
            "unresolved_reminders": unresolved,
            "changed_decisions": decisions,
            "new_evidence_count": len(evidence),
            "unresolved_reminder_count": len(unresolved),
            "changed_decision_count": len(decisions),
            "markdown": "",
        }

    def due_weekly_digest_researchers(
        self, now: datetime | None = None
    ) -> list[str]:
        """Return enabled researchers whose configured local schedule is due this minute."""
        current = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)
        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT researcher_id, email, slack_webhook_url, weekly_digest_weekday,
                       weekly_digest_hour, weekly_digest_minute, weekly_digest_timezone
                FROM workspace_notification_settings
                WHERE weekly_digest_enabled=1
                  AND (email != '' OR slack_webhook_url != '')
                """
            ).fetchall()
        due: list[str] = []
        for row in rows:
            try:
                zone = ZoneInfo(row["weekly_digest_timezone"] or "UTC")
            except ZoneInfoNotFoundError:
                zone = ZoneInfo("UTC")
            local = current.astimezone(zone)
            digest_key, _, _ = self._weekly_period(
                current, row["weekly_digest_timezone"] or "UTC"
            )
            with self._connect() as connection:
                attempted = {
                    (item["researcher_id"], item["channel"])
                    for item in connection.execute(
                        "SELECT researcher_id, channel FROM workspace_digest_deliveries "
                        "WHERE digest_key=? AND researcher_id=?",
                        (digest_key, row["researcher_id"]),
                    ).fetchall()
                }
            if (
                local.weekday() != int(row["weekly_digest_weekday"])
                or local.hour != int(row["weekly_digest_hour"])
                or local.minute != int(row["weekly_digest_minute"])
            ):
                continue
            researcher_id = row["researcher_id"]
            configured_channels = []
            if row["email"]:
                configured_channels.append("email")
            if row["slack_webhook_url"]:
                configured_channels.append("slack")
            if configured_channels and all(
                (researcher_id, channel) in attempted for channel in configured_channels
            ):
                continue
            due.append(researcher_id)
        return due

    def digest_delivery_completed(
        self, digest_key: str, researcher_id: str, channel: str
    ) -> bool:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT delivered_at FROM workspace_digest_deliveries "
                "WHERE digest_key=? AND researcher_id=? AND channel=?",
                (digest_key, researcher_id, channel),
            ).fetchone()
        return bool(row and row["delivered_at"])

    def record_digest_delivery_attempt(
        self,
        digest_key: str,
        researcher_id: str,
        channel: str,
        *,
        delivered: bool,
        error: str = "",
    ) -> None:
        now = self._now()
        with self._connect() as connection:
            existing = connection.execute(
                "SELECT attempts FROM workspace_digest_deliveries "
                "WHERE digest_key=? AND researcher_id=? AND channel=?",
                (digest_key, researcher_id, channel),
            ).fetchone()
            attempts = int(existing["attempts"] if existing else 0) + 1
            connection.execute(
                """
                INSERT INTO workspace_digest_deliveries
                (digest_key, researcher_id, channel, status, attempts, last_attempt_at,
                 delivered_at, error)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(digest_key, researcher_id, channel) DO UPDATE SET
                    status=excluded.status,
                    attempts=excluded.attempts,
                    last_attempt_at=excluded.last_attempt_at,
                    delivered_at=excluded.delivered_at,
                    error=excluded.error
                """,
                (
                    digest_key,
                    researcher_id,
                    channel,
                    "delivered" if delivered else "failed",
                    attempts,
                    now,
                    now if delivered else None,
                    error[:1000],
                ),
            )

    @staticmethod
    def _alert_dict(row: sqlite3.Row) -> dict[str, Any]:
        result = dict(row)
        result["evidence_added"] = json.loads(result.pop("evidence_added_json") or "[]")
        result["evidence_removed"] = json.loads(result.pop("evidence_removed_json") or "[]")
        result["trigger_reasons"] = json.loads(result.pop("trigger_reasons_json") or "[]")
        return result

    def list_alerts(
        self,
        researcher_id: str = DEFAULT_RESEARCHER_ID,
        *,
        unread_only: bool = False,
        limit: int = 50,
        offset: int = 0,
    ) -> dict[str, Any]:
        limit = max(1, min(int(limit), 100))
        offset = max(0, int(offset))
        where = "researcher_id=?"
        params: list[Any] = [researcher_id]
        if unread_only:
            where += " AND read_at IS NULL"
        with self._connect() as connection:
            rows = connection.execute(
                f"""
                SELECT alert_id, researcher_id, kind, candidate_id, candidate_type, candidate_name,
                       reviewed_run_id, trigger_run_id, title, message, evidence_added_json,
                       evidence_removed_json, previous_score, current_score, score_drop,
                       previous_rank, current_rank, rank_change, previous_quality,
                       current_quality, quality_change, trigger_reasons_json, created_at, read_at
                FROM workspace_alerts WHERE {where}
                ORDER BY created_at DESC, alert_id DESC LIMIT ? OFFSET ?
                """,
                [*params, limit, offset],
            ).fetchall()
            unread_count = connection.execute(
                "SELECT COUNT(*) FROM workspace_alerts WHERE researcher_id=? AND read_at IS NULL",
                (researcher_id,),
            ).fetchone()[0]
        return {
            "alerts": [self._alert_dict(row) for row in rows],
            "unread_count": int(unread_count),
            "limit": limit,
            "offset": offset,
        }

    def _notification_settings_raw(self, researcher_id: str) -> dict[str, Any]:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT * FROM workspace_notification_settings WHERE researcher_id=?",
                (researcher_id,),
            ).fetchone()
        if row is None:
            return {
                "researcher_id": researcher_id,
                "email": "",
                "email_enabled": True,
                "slack_webhook_url": "",
                "slack_enabled": True,
                "score_drop_threshold": 0.0,
                "rank_change_threshold": 0,
                "evidence_quality_change_threshold": 0.0,
                "weekly_digest_enabled": False,
                "weekly_digest_weekday": 0,
                "weekly_digest_hour": 9,
                "weekly_digest_minute": 0,
                "weekly_digest_timezone": "UTC",
                "updated_at": None,
            }
        result = dict(row)
        result["email_enabled"] = bool(result["email_enabled"])
        result["slack_enabled"] = bool(result["slack_enabled"])
        result["score_drop_threshold"] = float(result["score_drop_threshold"])
        result["rank_change_threshold"] = int(result["rank_change_threshold"])
        result["evidence_quality_change_threshold"] = float(
            result["evidence_quality_change_threshold"]
        )
        result["weekly_digest_enabled"] = bool(result["weekly_digest_enabled"])
        result["weekly_digest_weekday"] = int(result["weekly_digest_weekday"])
        result["weekly_digest_hour"] = int(result["weekly_digest_hour"])
        result["weekly_digest_minute"] = int(result["weekly_digest_minute"])
        result["weekly_digest_timezone"] = str(result["weekly_digest_timezone"] or "UTC")
        return result

    def _digest_delivery_status(self, researcher_id: str) -> dict[str, dict[str, Any]]:
        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT channel, status, attempts, last_attempt_at, delivered_at, error
                FROM workspace_digest_deliveries
                WHERE researcher_id=?
                ORDER BY last_attempt_at DESC
                """,
                (researcher_id,),
            ).fetchall()
        status: dict[str, dict[str, Any]] = {}
        for row in rows:
            status.setdefault(row["channel"], dict(row))
        return status

    def list_digest_deliveries(
        self, researcher_id: str = DEFAULT_RESEARCHER_ID, limit: int = 50
    ) -> list[dict[str, Any]]:
        limit = max(1, min(int(limit), 200))
        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT digest_key, researcher_id, channel, status, attempts,
                       last_attempt_at, delivered_at, error
                FROM workspace_digest_deliveries
                WHERE researcher_id=?
                ORDER BY last_attempt_at DESC
                LIMIT ?
                """,
                (researcher_id, limit),
            ).fetchall()
        return [dict(row) for row in rows]

    def _notification_delivery_status(self, researcher_id: str) -> dict[str, dict[str, Any]]:
        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT channel, status, attempts, last_attempt_at, delivered_at, error
                FROM workspace_alert_deliveries
                WHERE researcher_id=?
                ORDER BY last_attempt_at DESC
                """,
                (researcher_id,),
            ).fetchall()
        status: dict[str, dict[str, Any]] = {}
        for row in rows:
            # Keep the most recent delivery attempt for each channel. Individual alert
            # history remains available in the delivery table for operational inspection.
            status.setdefault(row["channel"], dict(row))
        return status

    def get_notification_settings(self, researcher_id: str = DEFAULT_RESEARCHER_ID) -> dict[str, Any]:
        settings = self._notification_settings_raw(researcher_id)
        return {
            "researcher_id": researcher_id,
            "email": settings["email"],
            "email_enabled": settings["email_enabled"],
            "slack_configured": bool(settings["slack_webhook_url"]),
            "slack_enabled": settings["slack_enabled"],
            "score_drop_threshold": settings["score_drop_threshold"],
            "rank_change_threshold": settings["rank_change_threshold"],
            "evidence_quality_change_threshold": settings[
                "evidence_quality_change_threshold"
            ],
            "weekly_digest_enabled": settings["weekly_digest_enabled"],
            "weekly_digest_weekday": settings["weekly_digest_weekday"],
            "weekly_digest_hour": settings["weekly_digest_hour"],
            "weekly_digest_minute": settings["weekly_digest_minute"],
            "weekly_digest_timezone": settings["weekly_digest_timezone"],
            "delivery": self._notification_delivery_status(researcher_id),
            "digest_delivery": self._digest_delivery_status(researcher_id),
            "updated_at": settings["updated_at"],
        }

    def save_notification_settings(
        self,
        researcher_id: str,
        email: str,
        email_enabled: bool,
        slack_webhook_url: str,
        slack_enabled: bool,
        score_drop_threshold: float = 0.0,
        rank_change_threshold: int = 0,
        evidence_quality_change_threshold: float = 0.0,
        weekly_digest_enabled: bool = False,
        weekly_digest_weekday: int = 0,
        weekly_digest_hour: int = 9,
        weekly_digest_minute: int = 0,
        weekly_digest_timezone: str = "UTC",
    ) -> dict[str, Any]:
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO workspace_notification_settings
                (researcher_id, email, email_enabled, slack_webhook_url, slack_enabled,
                 score_drop_threshold, rank_change_threshold, evidence_quality_change_threshold,
                 weekly_digest_enabled, weekly_digest_weekday, weekly_digest_hour,
                 weekly_digest_minute, weekly_digest_timezone, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(researcher_id) DO UPDATE SET
                    email=excluded.email,
                    email_enabled=excluded.email_enabled,
                    slack_webhook_url=excluded.slack_webhook_url,
                    slack_enabled=excluded.slack_enabled,
                    score_drop_threshold=excluded.score_drop_threshold,
                    rank_change_threshold=excluded.rank_change_threshold,
                    evidence_quality_change_threshold=excluded.evidence_quality_change_threshold,
                    weekly_digest_enabled=excluded.weekly_digest_enabled,
                    weekly_digest_weekday=excluded.weekly_digest_weekday,
                    weekly_digest_hour=excluded.weekly_digest_hour,
                    weekly_digest_minute=excluded.weekly_digest_minute,
                    weekly_digest_timezone=excluded.weekly_digest_timezone,
                    updated_at=excluded.updated_at
                """,
                (
                    researcher_id,
                    email,
                    int(email_enabled),
                    slack_webhook_url,
                    int(slack_enabled),
                    float(score_drop_threshold),
                    int(rank_change_threshold),
                    float(evidence_quality_change_threshold),
                    int(weekly_digest_enabled),
                    int(weekly_digest_weekday),
                    int(weekly_digest_hour),
                    int(weekly_digest_minute),
                    weekly_digest_timezone,
                    self._now(),
                ),
            )
        return self.get_notification_settings(researcher_id)

    def pending_alerts_for_delivery(self, researcher_id: str) -> list[dict[str, Any]]:
        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT a.alert_id, a.researcher_id, a.kind, a.candidate_id, a.candidate_type,
                       a.candidate_name, a.reviewed_run_id, a.trigger_run_id, a.title, a.message,
                       a.evidence_added_json, a.evidence_removed_json, a.previous_score,
                       a.current_score, a.score_drop, a.previous_rank, a.current_rank,
                       a.rank_change, a.previous_quality, a.current_quality, a.quality_change,
                       a.trigger_reasons_json, a.created_at, a.read_at
                FROM workspace_alerts AS a
                WHERE a.researcher_id=? AND a.read_at IS NULL
                  AND EXISTS (
                      SELECT 1 FROM workspace_notification_settings AS s
                      WHERE s.researcher_id=a.researcher_id
                  )
                ORDER BY a.created_at ASC, a.alert_id ASC
                """,
                (researcher_id,),
            ).fetchall()
        return [self._alert_dict(row) for row in rows]

    def delivery_completed(
        self, alert_id: str, researcher_id: str, channel: str
    ) -> bool:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT delivered_at FROM workspace_alert_deliveries "
                "WHERE alert_id=? AND researcher_id=? AND channel=?",
                (alert_id, researcher_id, channel),
            ).fetchone()
        return bool(row and row["delivered_at"])

    def record_delivery_attempt(
        self,
        alert_id: str,
        researcher_id: str,
        channel: str,
        *,
        delivered: bool,
        error: str = "",
    ) -> None:
        now = self._now()
        with self._connect() as connection:
            existing = connection.execute(
                "SELECT attempts FROM workspace_alert_deliveries "
                "WHERE alert_id=? AND researcher_id=? AND channel=?",
                (alert_id, researcher_id, channel),
            ).fetchone()
            attempts = int(existing["attempts"] if existing else 0) + 1
            connection.execute(
                """
                INSERT INTO workspace_alert_deliveries
                (alert_id, researcher_id, channel, status, attempts, last_attempt_at, delivered_at, error)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(alert_id, researcher_id, channel) DO UPDATE SET
                    status=excluded.status,
                    attempts=excluded.attempts,
                    last_attempt_at=excluded.last_attempt_at,
                    delivered_at=excluded.delivered_at,
                    error=excluded.error
                """,
                (
                    alert_id,
                    researcher_id,
                    channel,
                    "delivered" if delivered else "failed",
                    attempts,
                    now,
                    now if delivered else None,
                    error[:1000],
                ),
            )

    def mark_alert_read(self, alert_id: str, researcher_id: str = DEFAULT_RESEARCHER_ID) -> bool:
        with self._connect() as connection:
            cursor = connection.execute(
                "UPDATE workspace_alerts SET read_at=? WHERE alert_id=? AND researcher_id=?",
                (self._now(), alert_id, researcher_id),
            )
        return cursor.rowcount > 0

    def refresh_alerts(self, researcher_id: str = DEFAULT_RESEARCHER_ID) -> int:
        """Create idempotent review reminders when later runs add candidate evidence."""
        with self._connect() as connection:
            review_rows = connection.execute(
                """
                SELECT run_id, researcher_id, candidate_id, candidate_type, candidate_name,
                       decision, rationale, notes, tags_json, changed_my_mind,
                       provenance_fingerprint, created_at, updated_at
                FROM workspace_reviews WHERE researcher_id=?
                """,
                (researcher_id,),
            ).fetchall()
            run_rows = connection.execute(
                "SELECT run_id, dossier_json, updated_at FROM workspace_runs WHERE status='SUCCESS'"
            ).fetchall()
        reviews = {
            (row["run_id"], row["candidate_type"], row["candidate_id"]): self._review_dict(row)
            for row in review_rows
        }
        settings = self._notification_settings_raw(researcher_id)
        score_drop_threshold = settings["score_drop_threshold"]
        rank_change_threshold = settings["rank_change_threshold"]
        quality_change_threshold = settings["evidence_quality_change_threshold"]
        parsed_runs: list[dict[str, Any]] = []
        for row in run_rows:
            try:
                dossier = json.loads(row["dossier_json"] or "{}")
                timestamp = str(dossier.get("completed_at") or row["updated_at"]).replace(
                    "Z", "+00:00"
                )
                parsed_runs.append(
                    {
                        "run_id": row["run_id"],
                        "dossier": dossier,
                        "timestamp": timestamp,
                        "disease_id": (dossier.get("request") or {}).get("disease_id", "sle"),
                        "parsed_timestamp": datetime.fromisoformat(timestamp),
                    }
                )
            except (TypeError, ValueError, json.JSONDecodeError):
                continue
        parsed_runs.sort(key=lambda item: (item["parsed_timestamp"], item["run_id"]))
        created = 0
        with self._connect() as connection:
            for index, current in enumerate(parsed_runs):
                current_dossier = current["dossier"]
                for candidate_type, ranking_key in (("drug", "drug_rankings"), ("target", "target_rankings")):
                    for candidate in current_dossier.get(ranking_key, []):
                        candidate_id = candidate.get("candidate_id", "")
                        current_review = reviews.get((current["run_id"], candidate_type, candidate_id))
                        if current_review:
                            continue
                        previous = None
                        previous_review = None
                        for earlier in reversed(parsed_runs[:index]):
                            if earlier["disease_id"] != current["disease_id"]:
                                continue
                            review = reviews.get((earlier["run_id"], candidate_type, candidate_id))
                            if review and review.get("decision") in {"pinned", "rejected"}:
                                previous = earlier
                                previous_review = review
                                break
                        if previous is None or previous_review is None:
                            continue
                        current_evidence = _candidate_evidence_ids(
                            current_dossier, candidate_type, candidate_id
                        )
                        previous_evidence = _candidate_evidence_ids(
                            previous["dossier"], candidate_type, candidate_id
                        )
                        evidence_added = sorted(current_evidence - previous_evidence)
                        previous_ranked = next(
                            (
                                item
                                for item in previous["dossier"].get(ranking_key, [])
                                if item.get("candidate_id") == candidate_id
                            ),
                            None,
                        )
                        if previous_ranked is None:
                            continue
                        previous_rank = next(
                            (
                                rank + 1
                                for rank, item in enumerate(previous["dossier"].get(ranking_key, []))
                                if item.get("candidate_id") == candidate_id
                            ),
                            None,
                        )
                        current_rank = next(
                            rank + 1
                            for rank, item in enumerate(current_dossier.get(ranking_key, []))
                            if item.get("candidate_id") == candidate_id
                        )
                        previous_score = previous_ranked.get("score")
                        current_score = candidate.get("score")
                        score_drop = round(
                            max(previous_score - current_score, 0.0), 6
                        ) if isinstance(previous_score, (int, float)) and isinstance(
                            current_score, (int, float)
                        ) else 0.0
                        rank_change = (
                            abs(current_rank - previous_rank)
                            if current_rank is not None and previous_rank is not None
                            else 0
                        )
                        previous_quality = _candidate_evidence_quality(
                            previous["dossier"], candidate_type, candidate_id
                        )
                        current_quality = _candidate_evidence_quality(
                            current_dossier, candidate_type, candidate_id
                        )
                        quality_change = (
                            round(current_quality - previous_quality, 6)
                            if previous_quality is not None and current_quality is not None
                            else None
                        )
                        trigger_reasons = []
                        if evidence_added:
                            trigger_reasons.append("new_evidence")
                        if score_drop_threshold > 0 and score_drop >= score_drop_threshold:
                            trigger_reasons.append("score_drop")
                        if rank_change_threshold > 0 and rank_change >= rank_change_threshold:
                            trigger_reasons.append("rank_change")
                        if (
                            quality_change_threshold > 0
                            and quality_change is not None
                            and abs(quality_change) >= quality_change_threshold
                        ):
                            trigger_reasons.append("evidence_quality_change")
                        if not trigger_reasons:
                            continue
                        alert_key = "|".join(
                            [researcher_id, current["run_id"], candidate_type, candidate_id]
                        )
                        alert_id = "alert-" + hashlib.sha256(alert_key.encode()).hexdigest()[:24]
                        decision = previous_review["decision"]
                        reason_text = ", ".join(trigger_reasons).replace("_", " ")
                        detail_parts = []
                        if evidence_added:
                            detail_parts.append(f"{len(evidence_added)} new evidence record(s)")
                        if "score_drop" in trigger_reasons:
                            detail_parts.append(
                                f"score dropped by {score_drop:.1f}"
                            )
                        if "rank_change" in trigger_reasons:
                            detail_parts.append(f"rank changed by {rank_change}")
                        if "evidence_quality_change" in trigger_reasons:
                            detail_parts.append(
                                f"evidence quality changed from {previous_quality:.2f} to {current_quality:.2f}"
                            )
                        title = f"Review reminder: change for {candidate.get('name', candidate_id)}"
                        message = (
                            f"Your {decision} candidate triggered {reason_text} since run "
                            f"{previous['run_id']}: {', '.join(detail_parts)}."
                        )
                        cursor = connection.execute(
                            """
                            INSERT OR IGNORE INTO workspace_alerts
                            (alert_id, researcher_id, kind, candidate_id, candidate_type, candidate_name,
                             reviewed_run_id, trigger_run_id, title, message, evidence_added_json,
                             evidence_removed_json, previous_score, current_score, score_drop,
                             previous_rank, current_rank, rank_change, previous_quality, current_quality,
                             quality_change, trigger_reasons_json, created_at)
                            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                            """,
                            (
                                alert_id,
                                researcher_id,
                                "review_reminder",
                                candidate_id,
                                candidate_type,
                                candidate.get("name", candidate_id),
                                previous["run_id"],
                                current["run_id"],
                                title,
                                message,
                                json.dumps(evidence_added),
                                json.dumps(sorted(previous_evidence - current_evidence)),
                                previous_score,
                                current_score,
                                score_drop,
                                previous_rank,
                                current_rank,
                                rank_change,
                                previous_quality,
                                current_quality,
                                quality_change,
                                json.dumps(trigger_reasons),
                                self._now(),
                            ),
                        )
                        created += int(cursor.rowcount > 0)
        return created

    def get_review(
        self,
        run_id: str,
        candidate_type: str,
        candidate_id: str,
        researcher_id: str = DEFAULT_RESEARCHER_ID,
    ) -> dict[str, Any] | None:
        with self._connect() as connection:
            row = connection.execute(
                """
                SELECT run_id, researcher_id, candidate_id, candidate_type, candidate_name, decision,
                       rationale, notes, tags_json, changed_my_mind,
                       provenance_fingerprint, created_at, updated_at
                FROM workspace_reviews
                WHERE run_id=? AND researcher_id=? AND candidate_type=? AND candidate_id=?
                """,
                (run_id, researcher_id, candidate_type, candidate_id),
            ).fetchone()
        return self._review_dict(row) if row else None

    def upsert_review(
        self,
        run_id: str,
        candidate_id: str,
        candidate_type: str,
        candidate_name: str,
        decision: str,
        rationale: str,
        notes: str,
        tags: list[str],
        changed_my_mind: str,
        provenance_fingerprint: str,
        researcher_id: str = DEFAULT_RESEARCHER_ID,
    ) -> dict[str, Any]:
        now = self._now()
        normalized_tags = list(dict.fromkeys(tag.strip() for tag in tags if tag.strip()))
        with self._connect() as connection:
            existing = connection.execute(
                "SELECT decision, created_at FROM workspace_reviews "
                "WHERE run_id=? AND researcher_id=? AND candidate_type=? AND candidate_id=?",
                (run_id, researcher_id, candidate_type, candidate_id),
            ).fetchone()
            created_at = existing["created_at"] if existing else now
            previous_decision = existing["decision"] if existing else "unreviewed"
            connection.execute(
                """
                INSERT INTO workspace_reviews
                (run_id, researcher_id, candidate_id, candidate_type, candidate_name, decision, rationale,
                 notes, tags_json, changed_my_mind, provenance_fingerprint, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(run_id, researcher_id, candidate_type, candidate_id) DO UPDATE SET
                    candidate_name=excluded.candidate_name,
                    decision=excluded.decision,
                    rationale=excluded.rationale,
                    notes=excluded.notes,
                    tags_json=excluded.tags_json,
                    changed_my_mind=excluded.changed_my_mind,
                    provenance_fingerprint=excluded.provenance_fingerprint,
                    updated_at=excluded.updated_at
                """,
                (
                    run_id,
                    researcher_id,
                    candidate_id,
                    candidate_type,
                    candidate_name,
                    decision,
                    rationale,
                    notes,
                    json.dumps(normalized_tags, ensure_ascii=False),
                    changed_my_mind,
                    provenance_fingerprint,
                    created_at,
                    now,
                ),
            )
            connection.execute(
                """
                INSERT INTO workspace_review_events
                (run_id, researcher_id, candidate_id, candidate_type, previous_decision, decision,
                 rationale, notes, tags_json, changed_my_mind, provenance_fingerprint, recorded_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    run_id,
                    researcher_id,
                    candidate_id,
                    candidate_type,
                    previous_decision,
                    decision,
                    rationale,
                    notes,
                    json.dumps(normalized_tags, ensure_ascii=False),
                    changed_my_mind,
                    provenance_fingerprint,
                    now,
                ),
            )
        review = self.get_review(run_id, candidate_type, candidate_id, researcher_id)
        if review is None:
            raise KeyError(f"review not saved: {run_id}/{candidate_type}/{candidate_id}")
        return review

    def candidate_history(
        self,
        candidate_id: str,
        candidate_type: str,
        disease_id: str | None = None,
        researcher_id: str = DEFAULT_RESEARCHER_ID,
    ) -> dict[str, Any]:
        filters = ["status='SUCCESS'"]
        params: list[Any] = []
        if disease_id:
            filters.append("disease_id=?")
            params.append(disease_id)
        with self._connect() as connection:
            rows = connection.execute(
                "SELECT run_id, dossier_json, updated_at FROM workspace_runs WHERE "
                + " AND ".join(filters),
                params,
            ).fetchall()
        parsed: list[dict[str, Any]] = []
        candidate_name = ""
        for row in rows:
            try:
                dossier = json.loads(row["dossier_json"] or "{}")
                timestamp = str(dossier.get("completed_at") or row["updated_at"]).replace(
                    "Z", "+00:00"
                )
                parsed_timestamp = datetime.fromisoformat(timestamp)
            except (TypeError, ValueError, json.JSONDecodeError):
                continue
            rankings = dossier.get(f"{candidate_type}_rankings", [])
            item = next(
                (entry for entry in rankings if entry.get("candidate_id") == candidate_id), None
            )
            if item:
                candidate_name = item.get("name", candidate_name)
            parsed.append(
                {
                    "run_id": row["run_id"],
                    "timestamp": timestamp,
                    "parsed_timestamp": parsed_timestamp,
                    "item": item,
                    "dossier": dossier,
                }
            )
        parsed.sort(key=lambda item: (item["parsed_timestamp"], item["run_id"]))
        points: list[dict[str, Any]] = []
        previous_evidence: set[str] = set()
        for item in parsed:
            ranking = item["item"]
            evidence_ids: set[str] = set()
            if ranking:
                claims_by_id = {
                    claim.get("claim_id"): claim for claim in item["dossier"].get("claims", [])
                }
                claim_ids = set(ranking.get("supporting_claim_ids", [])) | set(
                    ranking.get("contradicting_claim_ids", [])
                )
                for claim_id in claim_ids:
                    evidence_ids.update(claims_by_id.get(claim_id, {}).get("evidence_ids", []))
            point = {
                "run_id": item["run_id"],
                "timestamp": item["timestamp"],
                "score": ranking.get("score") if ranking else None,
                "rank": (
                    next(
                        index + 1
                        for index, candidate in enumerate(
                            item["dossier"].get(f"{candidate_type}_rankings", [])
                        )
                        if candidate.get("candidate_id") == candidate_id
                    )
                    if ranking
                    else None
                ),
                "evidence_ids": sorted(evidence_ids),
                "evidence_added": sorted(evidence_ids - previous_evidence),
                "evidence_removed": sorted(previous_evidence - evidence_ids),
                "review": self.get_review(
                    item["run_id"], candidate_type, candidate_id, researcher_id
                ),
            }
            points.append(point)
            previous_evidence = evidence_ids
        return {
            "candidate_id": candidate_id,
            "candidate_type": candidate_type,
            "candidate_name": candidate_name or candidate_id,
            "points": points,
        }

    def trends(
        self,
        limit: int = 20,
        run_ids: list[str] | tuple[str, ...] | None = None,
    ) -> dict[str, Any]:
        """Return chronological ranking and source-coverage trends for successful runs.

        Trend aggregation intentionally reads only dossier JSON, never the stored HTML
        export. Missing candidates are represented as sparse points with ``present=False``
        so the dashboard can distinguish disappearance from a zero score.
        """
        limit = max(1, min(int(limit), 100))
        selected_ids = list(dict.fromkeys(run_ids or []))
        with self._connect() as connection:
            if selected_ids:
                placeholders = ",".join("?" for _ in selected_ids)
                rows = connection.execute(
                    f"""
                    SELECT run_id, question, dossier_json, updated_at
                    FROM workspace_runs
                    WHERE status='SUCCESS' AND run_id IN ({placeholders})
                    """,
                    selected_ids,
                ).fetchall()
            else:
                rows = connection.execute(
                    """
                    SELECT run_id, question, dossier_json, updated_at
                    FROM workspace_runs
                    WHERE status='SUCCESS'
                    ORDER BY updated_at DESC LIMIT ?
                    """,
                    (limit,),
                ).fetchall()

        parsed_runs: list[dict[str, Any]] = []
        for row in rows:
            try:
                dossier = json.loads(row["dossier_json"] or "{}")
                timestamp = dossier.get("completed_at") or row["updated_at"]
                # Normalize a trailing Z while retaining the explicit UTC offset in
                # the API contract and providing deterministic chronological sorting.
                timestamp = str(timestamp).replace("Z", "+00:00")
                parsed_timestamp = datetime.fromisoformat(timestamp)
            except (TypeError, ValueError, json.JSONDecodeError):
                continue
            parsed_runs.append(
                {
                    "run_id": row["run_id"],
                    "question": row["question"],
                    "timestamp": timestamp,
                    "parsed_timestamp": parsed_timestamp,
                    "dossier": dossier,
                }
            )

        parsed_runs.sort(key=lambda item: (item["parsed_timestamp"], item["run_id"]))
        if selected_ids:
            parsed_runs = parsed_runs[:limit]

        runs: list[dict[str, Any]] = []
        series: dict[str, dict[str, dict[str, Any]]] = {"drug": {}, "target": {}}
        previous_evidence: dict[tuple[str, str], set[str]] = {}
        for run in parsed_runs:
            dossier = run["dossier"]
            source_coverage = {
                item.get("source", ""): {
                    "status": item.get("status", "warning"),
                    "records_found": item.get("records_found", 0),
                }
                for item in dossier.get("source_statuses", [])
                if item.get("source")
            }
            runs.append(
                {
                    "run_id": run["run_id"],
                    "question": run["question"],
                    "timestamp": run["timestamp"],
                    "evidence_count": len(dossier.get("evidence", [])),
                    "claim_count": len(dossier.get("claims", [])),
                    "warning_count": len(dossier.get("warnings", [])),
                    "source_coverage": source_coverage,
                }
            )
            claims_by_id = {
                claim.get("claim_id"): claim for claim in dossier.get("claims", [])
            }
            for kind in ("drug", "target"):
                rankings = dossier.get(f"{kind}_rankings", [])
                for rank, candidate in enumerate(rankings, start=1):
                    candidate_id = candidate.get("candidate_id")
                    if not candidate_id:
                        continue
                    candidate_series = series[kind].setdefault(
                        candidate_id,
                        {
                            "candidate_id": candidate_id,
                            "name": candidate.get("name", candidate_id),
                            "points": [],
                        },
                    )
                    claim_ids = set(candidate.get("supporting_claim_ids", [])) | set(
                        candidate.get("contradicting_claim_ids", [])
                    )
                    evidence_ids = {
                        evidence_id
                        for claim_id in claim_ids
                        for evidence_id in claims_by_id.get(claim_id, {}).get("evidence_ids", [])
                    }
                    key = (kind, candidate_id)
                    old_evidence = previous_evidence.get(key, set())
                    point = {
                        "run_id": run["run_id"],
                        "timestamp": run["timestamp"],
                        "score": candidate.get("score"),
                        "rank": rank,
                        "confidence_band": candidate.get("confidence_band"),
                        "supporting_claim_count": len(
                            candidate.get("supporting_claim_ids", [])
                        ),
                        "contradicting_claim_count": len(
                            candidate.get("contradicting_claim_ids", [])
                        ),
                        "present": True,
                    }
                    if evidence_ids or old_evidence:
                        point.update(
                            {
                                "evidence_ids": sorted(evidence_ids),
                                "evidence_added": sorted(evidence_ids - old_evidence),
                                "evidence_removed": sorted(old_evidence - evidence_ids),
                            }
                        )
                    candidate_series["points"].append(point)
                    previous_evidence[key] = evidence_ids

        result = {"runs": runs, "drug_series": [], "target_series": []}
        for kind in ("drug", "target"):
            for candidate in series[kind].values():
                by_run = {point["run_id"]: point for point in candidate["points"]}
                candidate["points"] = [
                    by_run.get(
                        run["run_id"],
                        {
                            "run_id": run["run_id"],
                            "timestamp": run["timestamp"],
                            "score": None,
                            "rank": None,
                            "confidence_band": None,
                            "supporting_claim_count": 0,
                            "contradicting_claim_count": 0,
                            "present": False,
                        },
                    )
                    for run in runs
                ]
                result[f"{kind}_series"].append(candidate)
            result[f"{kind}_series"].sort(
                key=lambda item: (item["name"].lower(), item["candidate_id"])
            )
        return result

    def compare_runs(
        self,
        left_run_id: str,
        right_run_id: str,
        researcher_id: str = DEFAULT_RESEARCHER_ID,
    ) -> dict[str, Any]:
        left = self.get_run(left_run_id)
        right = self.get_run(right_run_id)
        if left is None or right is None:
            missing = left_run_id if left is None else right_run_id
            raise KeyError(missing)

        def by_id(items: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
            return {item["candidate_id"]: item for item in items}

        def candidate_evidence(dossier: dict[str, Any], item: dict[str, Any] | None) -> list[str]:
            if not item:
                return []
            claims_by_id = {
                claim.get("claim_id"): claim for claim in dossier.get("claims", [])
            }
            claim_ids = set(item.get("supporting_claim_ids", [])) | set(
                item.get("contradicting_claim_ids", [])
            )
            return sorted(
                {
                    evidence_id
                    for claim_id in claim_ids
                    for evidence_id in claims_by_id.get(claim_id, {}).get("evidence_ids", [])
                }
            )

        def changes(kind: str) -> list[dict[str, Any]]:
            left_items = by_id((left["dossier"] or {}).get(f"{kind}_rankings", []))
            right_items = by_id((right["dossier"] or {}).get(f"{kind}_rankings", []))
            rows = []
            for candidate_id in sorted(set(left_items) | set(right_items)):
                left_item = left_items.get(candidate_id)
                right_item = right_items.get(candidate_id)
                left_score = left_item.get("score") if left_item else None
                right_score = right_item.get("score") if right_item else None
                rows.append(
                    {
                        "candidate_id": candidate_id,
                        "name": (right_item or left_item or {}).get("name", candidate_id),
                        "left_score": left_score,
                        "right_score": right_score,
                        "left_rank": next(
                            (
                                index + 1
                                for index, item in enumerate(
                                    (left["dossier"] or {}).get(f"{kind}_rankings", [])
                                )
                                if item["candidate_id"] == candidate_id
                            ),
                            None,
                        ),
                        "right_rank": next(
                            (
                                index + 1
                                for index, item in enumerate(
                                    (right["dossier"] or {}).get(f"{kind}_rankings", [])
                                )
                                if item["candidate_id"] == candidate_id
                            ),
                            None,
                        ),
                        "left_confidence_band": left_item.get("confidence_band")
                        if left_item
                        else None,
                        "right_confidence_band": right_item.get("confidence_band")
                        if right_item
                        else None,
                        "left_evidence_ids": candidate_evidence(left_dossier, left_item),
                        "right_evidence_ids": candidate_evidence(right_dossier, right_item),
                        "score_delta": (
                            round(right_score - left_score, 6)
                            if left_score is not None and right_score is not None
                            else None
                        ),
                        "change": (
                            "added"
                            if left_item is None
                            else "removed"
                            if right_item is None
                            else "changed"
                        ),
                    }
                )
            return sorted(
                rows, key=lambda row: (row["score_delta"] is None, -(row["score_delta"] or 0))
            )

        left_dossier = left["dossier"] or {}
        right_dossier = right["dossier"] or {}
        left_reviews = {
            (item["candidate_type"], item["candidate_id"]): item
            for item in self.list_reviews(left_run_id, researcher_id)
        }
        right_reviews = {
            (item["candidate_type"], item["candidate_id"]): item
            for item in self.list_reviews(right_run_id, researcher_id)
        }
        review_changes = []
        for key in sorted(set(left_reviews) | set(right_reviews)):
            left_review = left_reviews.get(key)
            right_review = right_reviews.get(key)
            if (left_review or {}).get("decision") == (right_review or {}).get("decision") and (
                left_review or {}
            ).get("rationale", "") == (right_review or {}).get("rationale", "") and (
                left_review or {}
            ).get("notes", "") == (right_review or {}).get("notes", "") and (
                left_review or {}
            ).get("tags", []) == (right_review or {}).get("tags", []):
                continue
            review_changes.append(
                {
                    "candidate_type": key[0],
                    "candidate_id": key[1],
                    "candidate_name": (right_review or left_review or {}).get("candidate_name", key[1]),
                    "left": left_review,
                    "right": right_review,
                }
            )
        left_evidence = {item["evidence_id"] for item in left_dossier.get("evidence", [])}
        right_evidence = {item["evidence_id"] for item in right_dossier.get("evidence", [])}
        return {
            "left_run_id": left_run_id,
            "right_run_id": right_run_id,
            "left": {key: left[key] for key in ("question", "created_at", "status")},
            "right": {key: right[key] for key in ("question", "created_at", "status")},
            "drug_changes": changes("drug"),
            "target_changes": changes("target"),
            "evidence_changes": {
                "added": sorted(right_evidence - left_evidence),
                "removed": sorted(left_evidence - right_evidence),
            },
            "review_changes": review_changes,
            "summary": {
                "evidence_count_delta": len(right_dossier.get("evidence", []))
                - len(left_dossier.get("evidence", [])),
                "claim_count_delta": len(right_dossier.get("claims", []))
                - len(left_dossier.get("claims", [])),
                "warning_delta": len(right_dossier.get("warnings", []))
                - len(left_dossier.get("warnings", [])),
            },
        }
