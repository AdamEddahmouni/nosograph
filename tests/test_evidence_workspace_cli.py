from med_research.cli import _build_parser, cmd_workspace
from med_research.pipeline.evidence_workspace.schemas import EvidenceDossier


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


def test_workspace_cli_runs_and_writes_requested_exports(monkeypatch, tmp_path, caplog):
    import med_research.pipeline.evidence_workspace as workspace_module

    def fake_run(request, **kwargs):
        return EvidenceDossier(
            run_id="ew-cli",
            request=request,
            started_at="2026-08-06T00:00:00Z",
            completed_at="2026-08-06T00:00:00Z",
        )

    monkeypatch.setattr(workspace_module, "run_workspace", fake_run)
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

    assert cmd_workspace(args) == 0
    assert (tmp_path / "dossier.json").exists()
    assert (tmp_path / "dossier.html").exists()
    assert "ew-cli" in caplog.text
