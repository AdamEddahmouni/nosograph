from datetime import datetime, timezone

from med_research.pipeline.evidence_workspace.report import dossier_to_json, render_html
from med_research.pipeline.evidence_workspace.schemas import EvidenceDossier, ResearchRequest


def test_report_preserves_provenance_escapes_text_and_includes_disclaimer():
    dossier = EvidenceDossier(
        run_id="ew-test",
        request=ResearchRequest(question='<script>alert("x")</script>'),
        started_at=datetime.now(timezone.utc),
        completed_at=datetime.now(timezone.utc),
        warnings=["source warning"],
    )

    payload = dossier_to_json(dossier)
    page = render_html(dossier)

    assert "ew-test" in payload
    assert "<script>alert" not in page
    assert "&lt;script&gt;" in page
    assert "not medical advice" in page
    assert "source warning" in page
