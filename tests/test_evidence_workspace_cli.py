from unittest.mock import MagicMock

import pytest

from med_research.cli import _build_parser, cmd_workspace, cmd_workspace_migrate
from med_research.pipeline.base import PipelineRunResult
from med_research.pipeline.evidence_workspace.schemas import EvidenceDossier, ResearchRequest
from med_research.pipeline.progress import cli_progress
from med_research.web.services.workspace_store import WorkspaceRunStore

pytestmark = pytest.mark.unit


def test_workspace_cli_parser_accepts_question_sources_and_exports():
    args = _build_parser().parse_args(
        [
            "workspace",
            "--question",
            "Find JAK interventions",
            "--sources",
            "pubmed",
            "--no-llm",
            "--json",
            "out.json",
            "--html",
            "out.html",
        ]
    )

    assert args.command == "workspace"
    assert args.question == "Find JAK interventions"
    assert args.sources == "pubmed"
    assert args.enable_llm is False
    assert args.json_path == "out.json"
    assert args.html_path == "out.html"


def test_workspace_migrate_cli_defaults_to_dry_run_then_applies(tmp_path, capsys):
    import json
    import sqlite3

    path = tmp_path / "workspace.sqlite3"
    store = WorkspaceRunStore(path)
    store.create_run("ew-cli-legacy", ResearchRequest(question="Find JAK interventions"))
    with sqlite3.connect(path) as connection:
        connection.execute(
            "UPDATE workspace_runs SET request_json=?, request_schema_version='1.0' WHERE run_id=?",
            (json.dumps({"question": "Find JAK interventions"}), "ew-cli-legacy"),
        )

    args = _build_parser().parse_args(
        ["workspace-migrate", "--db", str(path), "--dry-run", "--json"]
    )
    assert cmd_workspace_migrate(args) == 0
    report = json.loads(capsys.readouterr().out)
    assert report["dry_run"] is True
    assert report["legacy"] == 1
    assert report["migrated"] == 0

    with sqlite3.connect(path) as connection:
        request_json = connection.execute(
            "SELECT request_json FROM workspace_runs WHERE run_id=?", ("ew-cli-legacy",)
        ).fetchone()[0]
    assert "schema_version" not in json.loads(request_json)

    args = _build_parser().parse_args(["workspace-migrate", "--db", str(path), "--apply", "--json"])
    assert cmd_workspace_migrate(args) == 0
    report = json.loads(capsys.readouterr().out)
    assert report["dry_run"] is False
    assert report["migrated"] == 1


def test_workspace_cli_wires_cli_progress_through_dispatch(monkeypatch, tmp_path):
    """Workspace CLI must thread cli_progress into the gateway dispatch path."""
    dossier = EvidenceDossier(
        run_id="ew-cli-progress",
        request=ResearchRequest(question="JAK interventions"),
        started_at="2026-08-06T00:00:00Z",
        completed_at="2026-08-06T00:00:00Z",
    )
    mock_execute = MagicMock(return_value=PipelineRunResult(success=True, data=dossier))
    monkeypatch.setattr(
        "med_research.pipeline.gateway.pipeline_gateway.execute",
        mock_execute,
    )
    args = _build_parser().parse_args(
        [
            "workspace",
            "--question",
            "JAK interventions",
            "--json",
            str(tmp_path / "dossier.json"),
        ]
    )

    assert cmd_workspace(args) == 0
    mock_execute.assert_called_once()
    _, kwargs = mock_execute.call_args
    assert kwargs["progress_callback"] is cli_progress


def test_workspace_cli_runs_and_writes_requested_exports(monkeypatch, tmp_path, caplog):
    import logging

    def fake_run(request, **kwargs):
        return EvidenceDossier(
            run_id="ew-cli",
            request=request,
            started_at="2026-08-06T00:00:00Z",
            completed_at="2026-08-06T00:00:00Z",
        )

    monkeypatch.setattr(
        "med_research.pipeline.evidence_workspace.workspace.run_workspace",
        fake_run,
    )
    args = _build_parser().parse_args(
        [
            "workspace",
            "--question",
            "JAK interventions",
            "--json",
            str(tmp_path / "dossier.json"),
            "--html",
            str(tmp_path / "dossier.html"),
        ]
    )

    with caplog.at_level(logging.INFO):
        assert cmd_workspace(args) == 0
    assert (tmp_path / "dossier.json").exists()
    assert (tmp_path / "dossier.html").exists()
    assert "ew-cli" in caplog.text
