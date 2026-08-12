import json
import sqlite3
from datetime import date, datetime, timezone

import pytest

from med_research.pipeline.evidence_workspace.schemas import (
    WORKSPACE_REQUEST_MIGRATIONS,
    WORKSPACE_REQUEST_SCHEMA_VERSION,
    WORKSPACE_RESULT_MIGRATIONS,
    WORKSPACE_RESULT_SCHEMA_VERSION,
    EvidenceDossier,
    RankedCandidate,
    ResearchRequest,
    WorkspaceRequestV1,
    WorkspaceResultV1,
    migrate_workspace_request,
    migrate_workspace_result,
    serialize_workspace_request,
    serialize_workspace_result,
)
from med_research.web.services.workspace_store import WorkspaceRunStore

pytestmark = pytest.mark.unit


def dossier(run_id: str, drug_score: float, target_score: float) -> EvidenceDossier:
    return EvidenceDossier(
        run_id=run_id,
        request=ResearchRequest(
            question="Find JAK interventions for SLE",
            date_from=date(2025, 1, 1),
        ),
        started_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
        completed_at=datetime(2026, 1, 1, 0, 0, 1, tzinfo=timezone.utc),
        drug_rankings=[
            RankedCandidate(
                candidate_id="tofacitinib",
                candidate_type="drug",
                name="Tofacitinib",
                score=drug_score,
                confidence_band="moderate",
                explanation="Evidence-backed candidate",
            )
        ],
        target_rankings=[
            RankedCandidate(
                candidate_id="JAK1",
                candidate_type="target",
                name="JAK1",
                score=target_score,
                confidence_band="high",
                explanation="Mechanistic candidate",
            )
        ],
    )


def test_sqlite_store_persists_and_lists_dossiers(tmp_path):
    store = WorkspaceRunStore(tmp_path / "workspace.sqlite3")
    request = ResearchRequest(question="Find JAK interventions for SLE")

    store.create_run("ew-pending", request)
    store.save_success(dossier("ew-pending", 82.5, 76.0), "<html>one</html>")

    listed = store.list_runs(limit=10)
    assert listed[0]["run_id"] == "ew-pending"
    assert listed[0]["status"] == "SUCCESS"
    assert listed[0]["evidence_count"] == 0

    loaded = store.get_run("ew-pending")
    assert loaded["dossier"]["run_id"] == "ew-pending"
    assert loaded["html"] == "<html>one</html>"
    assert loaded["request_schema_version"] == WORKSPACE_REQUEST_SCHEMA_VERSION
    assert loaded["result_schema_version"] == WORKSPACE_RESULT_SCHEMA_VERSION


def test_workspace_migration_registry_contains_explicit_upgrade_chain():
    assert ("legacy", WORKSPACE_REQUEST_SCHEMA_VERSION) in WORKSPACE_REQUEST_MIGRATIONS
    assert ("legacy", "1.0") in WORKSPACE_RESULT_MIGRATIONS
    assert ("1.0", WORKSPACE_RESULT_SCHEMA_VERSION) in WORKSPACE_RESULT_MIGRATIONS
    assert all(callable(step) for step in WORKSPACE_REQUEST_MIGRATIONS.values())
    assert all(callable(step) for step in WORKSPACE_RESULT_MIGRATIONS.values())


def test_workspace_persisted_schemas_are_versioned_and_migratable():
    request = ResearchRequest(question="Find JAK interventions for SLE")
    encoded_request = serialize_workspace_request(request)
    assert encoded_request["schema_version"] == WORKSPACE_REQUEST_SCHEMA_VERSION
    assert WorkspaceRequestV1.model_json_schema()["properties"]["schema_version"]["const"] == "1.0"
    assert migrate_workspace_request(encoded_request) == request
    assert migrate_workspace_request(request.model_dump(mode="json")) == request

    result = dossier("ew-schema", 82.5, 76.0)
    encoded_result = serialize_workspace_result(result)
    assert encoded_result["schema_version"] == WORKSPACE_RESULT_SCHEMA_VERSION
    assert encoded_result["request"]["schema_version"] == WORKSPACE_REQUEST_SCHEMA_VERSION
    assert WorkspaceResultV1.model_json_schema()["properties"]["schema_version"]["const"] == "1.1"
    assert migrate_workspace_result(encoded_result).run_id == "ew-schema"

    legacy_result = result.model_dump(mode="json")
    legacy_result.pop("schema_version")
    legacy_result.pop("graph_explanations")
    migrated = migrate_workspace_result(legacy_result)
    assert migrated.schema_version == WORKSPACE_RESULT_SCHEMA_VERSION
    assert migrated.graph_explanations == []

    with pytest.raises(ValueError, match="Unsupported Workspace request schema version"):
        migrate_workspace_request({**encoded_request, "schema_version": "9.0"})
    with pytest.raises(ValueError, match="Unsupported Workspace result schema version"):
        migrate_workspace_result({**encoded_result, "schema_version": "9.0"})


def test_sqlite_store_rewrites_legacy_workspace_payloads(tmp_path):
    path = tmp_path / "workspace.sqlite3"
    store = WorkspaceRunStore(path)
    request = ResearchRequest(question="Find JAK interventions for SLE")
    result = dossier("ew-legacy", 82.5, 76.0)
    store.create_run(result.run_id, request)
    store.save_success(result, "<html>legacy</html>")

    legacy_request = request.model_dump(mode="json")
    legacy_result = result.model_dump(mode="json")
    legacy_result.pop("schema_version")
    legacy_result.pop("graph_explanations")
    with sqlite3.connect(path) as connection:
        connection.execute(
            """
            UPDATE workspace_runs
            SET request_json=?, dossier_json=?, request_schema_version='1.0',
                result_schema_version='1.0'
            WHERE run_id=?
            """,
            (json.dumps(legacy_request), json.dumps(legacy_result), result.run_id),
        )

    loaded = store.get_run(result.run_id)
    assert loaded["request_schema_version"] == WORKSPACE_REQUEST_SCHEMA_VERSION
    assert loaded["result_schema_version"] == WORKSPACE_RESULT_SCHEMA_VERSION
    assert loaded["dossier"]["schema_version"] == WORKSPACE_RESULT_SCHEMA_VERSION

    with sqlite3.connect(path) as connection:
        row = connection.execute(
            "SELECT request_json, dossier_json, request_schema_version, result_schema_version "
            "FROM workspace_runs WHERE run_id=?",
            (result.run_id,),
        ).fetchone()
    assert json.loads(row[0])["schema_version"] == WORKSPACE_REQUEST_SCHEMA_VERSION
    assert json.loads(row[1])["schema_version"] == WORKSPACE_RESULT_SCHEMA_VERSION
    assert row[2:] == (WORKSPACE_REQUEST_SCHEMA_VERSION, WORKSPACE_RESULT_SCHEMA_VERSION)


def test_sqlite_store_migration_report_is_dry_run_then_applies(tmp_path):
    path = tmp_path / "workspace.sqlite3"
    store = WorkspaceRunStore(path)
    request = ResearchRequest(question="Find JAK interventions for SLE")
    result = dossier("ew-migrate", 82.5, 76.0)
    store.create_run(result.run_id, request)
    store.save_success(result, "<html>legacy</html>")

    legacy_request = request.model_dump(mode="json")
    legacy_result = result.model_dump(mode="json")
    legacy_result.pop("schema_version")
    legacy_result.pop("graph_explanations")
    with sqlite3.connect(path) as connection:
        connection.execute(
            "UPDATE workspace_runs SET request_json=?, dossier_json=?, "
            "request_schema_version='1.0', result_schema_version='1.0' WHERE run_id=?",
            (json.dumps(legacy_request), json.dumps(legacy_result), result.run_id),
        )

    dry_run = store.migrate_legacy_runs(dry_run=True)
    assert dry_run["dry_run"] is True
    assert dry_run["scanned"] == 1
    assert dry_run["legacy"] == 1
    assert dry_run["migrated"] == 0
    assert dry_run["runs"][0]["would_migrate"] is True

    with sqlite3.connect(path) as connection:
        row = connection.execute(
            "SELECT request_json, dossier_json, request_schema_version, "
            "result_schema_version FROM workspace_runs WHERE run_id=?",
            (result.run_id,),
        ).fetchone()
    assert "schema_version" not in json.loads(row[0])
    assert "schema_version" not in json.loads(row[1])
    assert row[2:] == ("1.0", "1.0")

    applied = store.migrate_legacy_runs(dry_run=False)
    assert applied["dry_run"] is False
    assert applied["migrated"] == 1
    assert applied["runs"][0]["migrated"] is True
    with sqlite3.connect(path) as connection:
        row = connection.execute(
            "SELECT request_json, dossier_json, request_schema_version, "
            "result_schema_version FROM workspace_runs WHERE run_id=?",
            (result.run_id,),
        ).fetchone()
    assert json.loads(row[0])["schema_version"] == WORKSPACE_REQUEST_SCHEMA_VERSION
    assert json.loads(row[1])["schema_version"] == WORKSPACE_RESULT_SCHEMA_VERSION
    assert row[2:] == (WORKSPACE_REQUEST_SCHEMA_VERSION, WORKSPACE_RESULT_SCHEMA_VERSION)


def test_sqlite_store_compares_rankings_and_can_delete(tmp_path):
    store = WorkspaceRunStore(tmp_path / "workspace.sqlite3")
    request = ResearchRequest(question="Find JAK interventions for SLE")
    store.create_run("ew-left", request)
    store.create_run("ew-right", request)
    left = dossier("ew-left", 70.0, 76.0)
    right = dossier("ew-right", 84.0, 72.0)
    left.warnings = ["old warning"]
    right.warnings = ["new warning"]
    store.save_success(left, "<html>left</html>")
    store.save_success(right, "<html>right</html>")

    comparison = store.compare_runs("ew-left", "ew-right")
    assert comparison["left_run_id"] == "ew-left"
    assert comparison["right_run_id"] == "ew-right"
    assert comparison["drug_changes"][0]["candidate_id"] == "tofacitinib"
    assert comparison["drug_changes"][0]["score_delta"] == 14.0
    assert comparison["target_changes"][0]["score_delta"] == -4.0
    assert comparison["drug_changes"][0]["left_rank"] == 1
    assert comparison["drug_changes"][0]["right_confidence_band"] == "moderate"
    assert comparison["summary"]["evidence_count_delta"] == 0
    assert comparison["summary"]["warning_delta"] == 0
    assert comparison["evidence_changes"] == {"added": [], "removed": []}

    assert store.delete_run("ew-left") is True
    assert store.get_run("ew-left") is None
    assert store.delete_run("ew-left") is False


def test_sqlite_store_rejects_success_without_pending_run(tmp_path):
    store = WorkspaceRunStore(tmp_path / "workspace.sqlite3")
    with __import__("pytest").raises(KeyError):
        store.save_success(dossier("ew-missing", 1.0, 1.0), "<html />")


def test_sqlite_store_records_failures(tmp_path):
    store = WorkspaceRunStore(tmp_path / "workspace.sqlite3")
    store.create_run("ew-failed", ResearchRequest(question="Find JAK interventions for SLE"))
    store.mark_failed("ew-failed", "source unavailable")

    run = store.get_run("ew-failed")
    assert run["status"] == "FAILURE"
    assert run["error"] == "source unavailable"
    assert run["dossier"] is None
