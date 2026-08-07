from datetime import date, datetime, timezone

from med_research.pipeline.evidence_workspace.schemas import (
    EvidenceDossier,
    RankedCandidate,
    ResearchRequest,
)
from med_research.web.services.workspace_store import WorkspaceRunStore


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
