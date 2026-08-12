from datetime import datetime
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from med_research.pipeline.evidence_workspace.schemas import (
    EvidenceDossier,
    RankedCandidate,
    ResearchRequest,
    SourceStatus,
)
from med_research.web.services.workspace_store import WorkspaceRunStore

pytestmark = pytest.mark.unit


def _dossier(run_id: str, completed_at: str, drug_score: float, include_target: bool = True):
    targets = []
    if include_target:
        targets.append(
            RankedCandidate(
                candidate_id="JAK1",
                candidate_type="target",
                name="JAK1",
                score=70.0,
                confidence_band="high",
                explanation="Target evidence",
                supporting_claim_ids=["claim-1"],
                contradicting_claim_ids=[],
            )
        )
    return EvidenceDossier(
        run_id=run_id,
        request=ResearchRequest(question=f"Find JAK interventions ({run_id})"),
        started_at=datetime.fromisoformat(completed_at.replace("Z", "+00:00")),
        completed_at=datetime.fromisoformat(completed_at.replace("Z", "+00:00")),
        source_statuses=[
            SourceStatus(source="pubmed", status="ok", records_found=3),
            SourceStatus(source="gwas", status="warning", records_found=1, warning="undated"),
        ],
        drug_rankings=[
            RankedCandidate(
                candidate_id="tofacitinib",
                candidate_type="drug",
                name="Tofacitinib",
                score=drug_score,
                confidence_band="moderate",
                explanation="Drug evidence",
                supporting_claim_ids=["claim-1", "claim-2"],
                contradicting_claim_ids=["claim-3"] if drug_score < 80 else [],
            )
        ],
        target_rankings=targets,
        claims=[],
        warnings=["one warning"] if drug_score < 80 else [],
    )


def _save(store: WorkspaceRunStore, dossier: EvidenceDossier):
    store.create_run(dossier.run_id, dossier.request)
    store.save_success(dossier, "<html />")


def test_sqlite_store_builds_chronological_sparse_trends(tmp_path):
    store = WorkspaceRunStore(tmp_path / "workspace.sqlite3")
    _save(store, _dossier("ew-new", "2026-01-02T00:00:00Z", 84.0, include_target=False))
    _save(store, _dossier("ew-old", "2026-01-01T00:00:00Z", 72.0, include_target=True))
    store.create_run("ew-failed", ResearchRequest(question="failed"))
    store.mark_failed("ew-failed", "source unavailable")

    trends = store.trends(limit=20)

    assert [run["run_id"] for run in trends["runs"]] == ["ew-old", "ew-new"]
    assert [point["score"] for point in trends["drug_series"][0]["points"]] == [72.0, 84.0]
    assert trends["drug_series"][0]["points"][0]["rank"] == 1
    assert trends["drug_series"][0]["points"][0]["supporting_claim_count"] == 2
    assert trends["drug_series"][0]["points"][0]["contradicting_claim_count"] == 1
    assert trends["target_series"][0]["points"][0]["present"] is True
    assert trends["target_series"][0]["points"][1]["present"] is False
    assert trends["runs"][0]["source_coverage"] == {
        "pubmed": {"status": "ok", "records_found": 3},
        "gwas": {"status": "warning", "records_found": 1},
    }
    assert all(run["run_id"] != "ew-failed" for run in trends["runs"])


def test_sqlite_store_trends_can_select_runs_and_handle_empty(tmp_path):
    store = WorkspaceRunStore(tmp_path / "workspace.sqlite3")
    _save(store, _dossier("ew-one", "2026-01-01T00:00:00Z", 72.0))
    _save(store, _dossier("ew-two", "2026-01-02T00:00:00Z", 84.0))

    selected = store.trends(run_ids=["ew-two"])
    assert [run["run_id"] for run in selected["runs"]] == ["ew-two"]
    assert selected["drug_series"][0]["points"] == [
        {
            "run_id": "ew-two",
            "timestamp": "2026-01-02T00:00:00+00:00",
            "score": 84.0,
            "rank": 1,
            "confidence_band": "moderate",
            "supporting_claim_count": 2,
            "contradicting_claim_count": 0,
            "present": True,
        }
    ]

    empty = store.trends(run_ids=["missing"])
    assert empty == {"runs": [], "drug_series": [], "target_series": []}


def test_workspace_trends_api_and_dashboard_controls(monkeypatch, tmp_path):
    import med_research.web.routers.workspace as workspace_router

    db_path = tmp_path / "workspace.sqlite3"
    store = WorkspaceRunStore(db_path)
    _save(store, _dossier("ew-one", "2026-01-01T00:00:00Z", 72.0))
    _save(store, _dossier("ew-two", "2026-01-02T00:00:00Z", 84.0))
    monkeypatch.setattr(workspace_router, "WORKSPACE_DB_PATH", db_path)

    from med_research.web.main import app

    with TestClient(app) as client:
        response = client.get("/api/workspace/trends?run_ids=ew-one&run_ids=ew-two")

    assert response.status_code == 200
    assert [run["run_id"] for run in response.json()["runs"]] == ["ew-one", "ew-two"]
    assert response.json()["drug_series"][0]["points"][1]["score"] == 84.0

    root = Path(__file__).parents[1] / "src/med_research/web/static"
    index = (root / "index.html").read_text(encoding="utf-8")
    script = (root / "js/dashboard.js").read_text(encoding="utf-8")
    assert 'id="workspace-trends"' in index
    assert "loadWorkspaceTrends" in script
    assert "/api/workspace/trends" in script
    assert "<svg" in script
