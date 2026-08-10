import asyncio
import json
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from med_research.pipeline.evidence_workspace.schemas import EvidenceDossier, ResearchRequest


def _fixture_dossier():
    return EvidenceDossier(
        run_id="ew-test",
        request=ResearchRequest(question="Find JAK interventions for SLE"),
        started_at="2026-01-01T00:00:00Z",
        completed_at="2026-01-01T00:00:01Z",
    )


def test_workspace_task_returns_json_safe_dossier_and_html(monkeypatch):
    from med_research.web.tasks import analysis_tasks

    dossier = _fixture_dossier()

    def fake_run(request, progress_callback=None):
        progress_callback("fixture progress", 42, 100)
        return dossier

    monkeypatch.setattr(
        "med_research.pipeline.evidence_workspace.workspace.run_workspace", fake_run
    )
    monkeypatch.setattr(
        "med_research.pipeline.evidence_workspace.report.render_html",
        lambda value: "<html>fixture</html>",
    )

    states = []

    def capture_state(**kwargs):
        states.append(kwargs)

    monkeypatch.setattr(analysis_tasks.task_run_workspace, "update_state", capture_state)
    result = analysis_tasks.task_run_workspace.run(
        question="Find JAK interventions for SLE",
        disease_id="sle",
        sources=["pubmed", "clinical_trials"],
        enable_llm=False,
    )

    assert result["dossier"]["run_id"].startswith("ew-")
    assert result["html"] == "<html>fixture</html>"
    json.dumps(result)
    assert any(state["meta"]["message"] == "fixture progress" for state in states)


def test_workspace_job_route_uses_json_payload(monkeypatch):
    from med_research.web.routers import jobs

    captured = {}

    class FakeTask:
        id = "workspace-job-id"

    def fake_delay(**kwargs):
        captured.update(kwargs)
        return FakeTask()

    monkeypatch.setattr(jobs.task_run_workspace, "delay", fake_delay)
    with ThreadPoolExecutor(max_workers=1) as executor:
        response = executor.submit(
            asyncio.run,
            jobs.submit_workspace(
                ResearchRequest(question="Find promising JAK/STAT interventions for SLE")
            ),
        ).result()

    assert response["job_id"] == "workspace-job-id"
    assert response["module"] == "workspace"
    assert captured["disease_id"] == "sle"
    assert captured["sources"] == ["pubmed", "clinical_trials"]


def test_workspace_http_endpoint_accepts_json(monkeypatch):
    from med_research.web.main import app
    from med_research.web.routers import jobs

    class FakeTask:
        id = "http-workspace-job"

    captured = {}

    def fake_delay(**kwargs):
        captured.update(kwargs)
        return FakeTask()

    monkeypatch.setattr(jobs.task_run_workspace, "delay", fake_delay)
    with TestClient(app) as client:
        response = client.post(
            "/api/jobs/workspace",
            json={
                "question": "Find promising JAK/STAT interventions for SLE",
                "sources": ["pubmed"],
                "enable_llm": False,
            },
        )

    assert response.status_code == 200
    assert response.json() == {
        "job_id": "http-workspace-job",
        "status": "PENDING",
        "module": "workspace",
    }
    assert captured["sources"] == ["pubmed"]
    assert captured["enable_llm"] is False


def test_dashboard_contains_workspace_form_and_async_rendering():
    root = Path(__file__).parents[1] / "src/med_research/web/static"
    index = (root / "index.html").read_text(encoding="utf-8")
    script = (root / "js/dashboard.js").read_text(encoding="utf-8")
    styles = (root / "css/dashboard.css").read_text(encoding="utf-8")

    assert 'id="evidence-workspace"' in index
    assert 'data-action="workspace-submit"' in index
    assert 'onsubmit=' not in index
    assert 'onclick=' not in index
    assert 'onchange=' not in index
    assert "module === 'workspace'" in script
    assert "'/api/jobs/workspace'" in script
    assert "renderWorkspaceResult" in script
    assert ".workspace-shell" in styles
    assert "selected disease" in index


def test_dashboard_workspace_submission_is_terminal_aware_and_explainable():
    root = Path(__file__).parents[1] / "src/med_research/web/static"
    script = (root / "js/dashboard.js").read_text(encoding="utf-8")
    styles = (root / "css/dashboard.css").read_text(encoding="utf-8")

    assert "workspaceSubmissionActive" in script
    assert "setWorkspaceSubmissionState" in script
    assert "Why this ranked" in script
    assert "supporting evidence" in script
    assert "contradicting evidence" in script
    assert "fingerprint" in script
    assert "safeCitation" in script
    assert "settleJob(jobId, false" in script
    assert "TIMEOUT" in script
    assert "status.status === 'ERROR'" in script
    assert "new WebSocket(wsUrl)" in script
    assert "JSON.parse(event.data)" in script
    assert "escapeHtml(e.message)" in script
    assert "data-workspace-action" in script
    assert "data-workspace-alert-action" in script
    assert "setupWorkspaceResultActions" in script
    assert "populateWorkspaceTrendCandidates" in script
    assert "renderWorkspaceTrendTable" in script
    assert "downloadWorkspaceTrendCsv" in script
    assert "candidate_type" in script
    assert 'onclick=' not in script
    assert 'onchange=' not in script
    assert 'onsubmit=' not in script
    assert "setupDashboardActions" in script
    assert "data-action" in script
    assert ".workspace-provenance" in styles
    assert ".workspace-ranking-explanation" in styles
    assert ".workspace-trend-table" in styles
    assert ".workspace-sr-only" in styles


def test_dashboard_workspace_exports_keep_the_exact_task_payload():
    root = Path(__file__).parents[1] / "src/med_research/web/static"
    index = (root / "index.html").read_text(encoding="utf-8")
    script = (root / "js/dashboard.js").read_text(encoding="utf-8")

    assert "window.lastWorkspaceDossier = dossier" in script
    assert "window.lastWorkspaceHtml = payload?.html || ''" in script
    assert "downloadWorkspaceJson" in script
    assert "openWorkspaceHtml" in script
    assert "URL.createObjectURL" in script
    assert "sources: selectedSources" in script
    assert "aria-describedby=\"workspace-submit-status\"" in index
    assert "aria-label=\"Evidence sources\"" in index
    assert "role=\"region\" aria-label=\"Workspace result\"" in index
    assert "id=\"workspace-trend-table\"" in index
    assert "aria-label=\"Tabular trend data\"" in index
    assert "data-action=\"workspace-trends-export\"" in script
    assert "workspace-trend-table" in script
    assert "Research question:" in script
    assert "Sources:" in script
    assert "sources: selectedSources" in script


def test_dashboard_csp_mode_adds_an_enforcing_policy(monkeypatch):
    from med_research.web import middleware
    from med_research.web.main import app

    monkeypatch.setattr(middleware, "DASHBOARD_CSP_MODE", "enforce")
    with TestClient(app) as client:
        response = client.get("/")

    assert response.status_code == 200
    policy = response.headers["content-security-policy"]
    assert "script-src 'self'" in policy
    assert "script-src-attr 'none'" in policy
    assert "ws:" in policy
    assert "unsafe-eval" not in policy


def test_workspace_task_rejects_incomplete_disease_configuration(monkeypatch):
    from med_research.diseases.base import Disease
    from med_research.web.tasks import analysis_tasks

    monkeypatch.setattr(
        Disease,
        "validate",
        lambda self: {"CAR_T_SCORES": "empty"},
    )

    with pytest.raises(ValueError, match="incomplete disease configuration"):
        analysis_tasks.task_run_workspace.run(
            question="Find interventions",
            disease_id="ra",
            sources=["pubmed"],
            enable_llm=False,
        )
