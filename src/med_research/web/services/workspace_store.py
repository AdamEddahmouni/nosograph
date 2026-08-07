"""SQLite persistence for Evidence-to-Hypothesis Workspace dossiers."""

from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from med_research.pipeline.evidence_workspace.schemas import EvidenceDossier, ResearchRequest


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
            connection.execute(
                "CREATE INDEX IF NOT EXISTS idx_workspace_runs_updated "
                "ON workspace_runs(updated_at DESC)"
            )

    @staticmethod
    def _now() -> str:
        return datetime.now(timezone.utc).isoformat()

    @staticmethod
    def _request_json(request: ResearchRequest) -> str:
        return json.dumps(request.model_dump(mode="json"), sort_keys=True)

    def create_run(self, run_id: str, request: ResearchRequest) -> None:
        now = self._now()
        with self._connect() as connection:
            connection.execute(
                """
                INSERT OR REPLACE INTO workspace_runs
                (run_id, disease_id, question, status, request_json, created_at, updated_at)
                VALUES (?, ?, ?, 'PENDING', ?, ?, ?)
                """,
                (
                    run_id,
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
        return cursor.rowcount > 0

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
                    candidate_series["points"].append(
                        {
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
                    )

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

    def compare_runs(self, left_run_id: str, right_run_id: str) -> dict[str, Any]:
        left = self.get_run(left_run_id)
        right = self.get_run(right_run_id)
        if left is None or right is None:
            missing = left_run_id if left is None else right_run_id
            raise KeyError(missing)

        def by_id(items: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
            return {item["candidate_id"]: item for item in items}

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
                        "name": (right_item or left_item).get("name", candidate_id),
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
            "summary": {
                "evidence_count_delta": len(right_dossier.get("evidence", []))
                - len(left_dossier.get("evidence", [])),
                "claim_count_delta": len(right_dossier.get("claims", []))
                - len(left_dossier.get("claims", [])),
                "warning_delta": len(right_dossier.get("warnings", []))
                - len(left_dossier.get("warnings", [])),
            },
        }
