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
        progress_callback(42, "fixture progress")
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
    assert 'onsubmit="submitWorkspace(event)"' in index
    assert "workspace: '/api/jobs/workspace'" in script
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
    assert 'onclick="openWorkspaceRun' not in script
    assert ".workspace-provenance" in styles
    assert ".workspace-ranking-explanation" in styles


def test_dashboard_workspace_exports_keep_the_exact_task_payload():
    root = Path(__file__).parents[1] / "src/med_research/web/static"
    script = (root / "js/dashboard.js").read_text(encoding="utf-8")

    assert "window.lastWorkspaceDossier = dossier" in script
    assert "window.lastWorkspaceHtml = payload?.html || ''" in script
    assert "downloadWorkspaceJson" in script
    assert "openWorkspaceHtml" in script
    assert "URL.createObjectURL" in script
    assert "sources: selectedSources" in script
    assert "Research question:" in script
    assert "Sources:" in script
    assert "sources: selectedSources" in script


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
