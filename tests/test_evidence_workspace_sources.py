import pytest

from med_research.pipeline.evidence_workspace.schemas import ResearchRequest
from med_research.pipeline.evidence_workspace.sources import ClinicalTrialsSource, PubMedSource

pytestmark = pytest.mark.unit


def test_pubmed_source_normalizes_fixture_record():
    source = PubMedSource(
        lambda query, limit: [
            {
                "id": "123",
                "title": "JAK intervention in SLE",
                "abstract": "Baricitinib targets JAK1.",
                "year": "2024",
                "url": "https://pubmed.ncbi.nlm.nih.gov/123/",
                "doi": "10.1000/jak",
            }
        ]
    )

    result = source.search(ResearchRequest(question="JAK interventions"), ["JAK"])

    assert result.status.status == "ok"
    assert result.records[0].native_id == "123"
    assert result.records[0].source == "pubmed"
    assert result.records[0].published_date.year == 2024
    assert result.records[0].doi == "10.1000/jak"


def test_clinical_trials_failure_isolated_at_source_boundary():
    source = ClinicalTrialsSource(
        lambda query, limit: (_ for _ in ()).throw(RuntimeError("offline"))
    )

    result = source.search(ResearchRequest(question="JAK interventions"), ["JAK"])

    assert result.records == []
    assert result.status.status == "error"
    assert "offline" in result.status.warning
