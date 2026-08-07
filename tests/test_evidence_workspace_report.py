from datetime import datetime, timezone

import pytest

from med_research.pipeline.evidence_workspace.report import dossier_to_json, render_html
from med_research.pipeline.evidence_workspace.schemas import EvidenceDossier, ResearchRequest

pytestmark = pytest.mark.unit


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


def test_report_includes_provenance_block():
    dossier = EvidenceDossier(
        run_id="ew-test",
        request=ResearchRequest(question="BTK inhibition", disease_id="ra"),
        started_at=datetime.now(timezone.utc),
        completed_at=datetime.now(timezone.utc),
        manifest={
            "provenance": {
                "run_id": "ew-test",
                "fingerprint": "abc123def4567890abcd",
                "generated_at": "2026-08-07T12:00:00+00:00",
                "cache_or_live": "cache",
            }
        },
    )

    page = render_html(dossier)

    assert "abc123def4567890abcd" in page
    assert "ew-test" in page
    assert "cache" in page
    assert "Reproducibility" in page
    assert "fingerprint" in page
