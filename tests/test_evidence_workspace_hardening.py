from datetime import date

import pytest

from med_research.pipeline.evidence_workspace.report import render_html
from med_research.pipeline.evidence_workspace.schemas import (
    EvidenceDossier,
    EvidenceRecord,
    ResearchRequest,
)
from med_research.pipeline.evidence_workspace.sources import PubMedSource

pytestmark = pytest.mark.unit


def test_source_applies_date_window():
    source = PubMedSource(
        lambda query, limit: [
            {
                "id": "old",
                "title": "Old",
                "year": "2020",
                "url": "https://pubmed.ncbi.nlm.nih.gov/old/",
            },
            {
                "id": "new",
                "title": "New",
                "year": "2024",
                "url": "https://pubmed.ncbi.nlm.nih.gov/new/",
            },
        ]
    )

    result = source.search(
        ResearchRequest(disease_id="sle", question="JAK", date_from=date(2023, 1, 1)),
        ["JAK"],
    )

    assert [record.native_id for record in result.records] == ["new"]


def test_report_does_not_create_javascript_link():
    dossier = EvidenceDossier(
        run_id="ew-safe",
        request=ResearchRequest(disease_id="sle", question="JAK"),
        started_at="2026-08-06T00:00:00Z",
        completed_at="2026-08-06T00:00:00Z",
        evidence=[
            EvidenceRecord(
                evidence_id="pmid:unsafe",
                source="pubmed",
                native_id="unsafe",
                title="Unsafe",
                url="javascript:alert(1)",
            )
        ],
    )

    page = render_html(dossier)

    assert "javascript:" not in page
    assert "Unsafe" in page
