import pytest

from med_research.pipeline.evidence_workspace.schemas import ResearchRequest
from med_research.pipeline.evidence_workspace.sources import (
    FDALabelSource,
    GWASSource,
    default_sources,
)

pytestmark = pytest.mark.unit


def test_request_accepts_gwas_and_fda_sources():
    request = ResearchRequest(
        disease_id="sle",
        question="Find genetic and approved-drug evidence for SLE",
        sources=("pubmed", "clinical_trials", "gwas", "fda_labels"),
    )

    assert request.sources == ("pubmed", "clinical_trials", "gwas", "fda_labels")


def test_default_sources_registers_expanded_adapters():
    sources = default_sources()
    assert {"pubmed", "clinical_trials", "gwas", "fda_labels"}.issubset(set(sources))


def test_gwas_source_normalizes_study_fixture():
    source = GWASSource(
        lambda query, limit: [
            {
                "accessionId": "GCST900001",
                "title": "Systemic lupus erythematosus GWAS",
                "publicationInfo": {"pubmedId": "40000001", "publicationDate": "2024-04-01"},
                "url": "https://www.ebi.ac.uk/gwas/studies/GCST900001",
                "reportedTrait": "systemic lupus erythematosus",
            }
        ]
    )

    result = source.search(
        ResearchRequest(disease_id="sle", question="SLE", sources=("gwas",)),
        ["systemic lupus erythematosus"],
    )

    assert result.status.status == "ok"
    assert result.records[0].native_id == "GCST900001"
    assert result.records[0].source == "gwas"
    assert result.records[0].published_date.isoformat() == "2024-04-01"
    assert "40000001" in result.records[0].source_ids


def test_fda_label_source_normalizes_dailymed_fixture():
    setid = "11111111-2222-3333-4444-555555555555"
    source = FDALabelSource(
        lambda query, limit: [
            {
                "setid": setid,
                "title": "TOFACITINIB tablet",
                "updated_date": "2025-02-10",
                "url": f"https://dailymed.nlm.nih.gov/dailymed/drugInfo.cfm?setid={setid}",
                "indications": "For the treatment of autoimmune disease.",
                "drug_name": "tofacitinib",
            }
        ]
    )

    result = source.search(
        ResearchRequest(disease_id="sle", question="tofacitinib", sources=("fda_labels",)),
        ["tofacitinib"],
    )

    assert result.status.status == "ok"
    assert result.records[0].native_id == setid
    assert result.records[0].source == "fda_labels"
    assert result.records[0].published_date.isoformat() == "2025-02-10"
    assert "autoimmune" in result.records[0].snippet
    assert f"setid={setid}" in result.records[0].url


def test_expanded_source_failure_is_isolated():
    source = GWASSource(lambda query, limit: (_ for _ in ()).throw(RuntimeError("catalog offline")))
    result = source.search(
        ResearchRequest(disease_id="sle", question="SLE", sources=("gwas",)), ["SLE"]
    )

    assert result.records == []
    assert result.status.status == "error"
    assert "catalog offline" in result.status.warning


def test_date_filter_warns_when_source_record_has_no_date():
    source = FDALabelSource(lambda query, limit: [{"setid": "undated", "title": "Unknown label"}])
    result = source.search(
        ResearchRequest(
            disease_id="sle",
            question="label",
            sources=("fda_labels",),
            date_from="2024-01-01",
        ),
        ["label"],
    )

    assert result.records == []
    assert result.status.status == "warning"
    assert "undated" in result.status.warning.lower()
