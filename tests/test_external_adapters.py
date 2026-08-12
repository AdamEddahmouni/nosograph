"""Unit tests for external adapters and workspace sources integration."""

from __future__ import annotations

import pytest

from med_research.pipeline.evidence_workspace.schemas import ResearchRequest
from med_research.pipeline.evidence_workspace.sources import ChEMBLSource, OpenTargetsSource, default_sources
from med_research.pipeline.external.chembl_uniprot import ChEMBLClient
from med_research.pipeline.external.opentargets import OpenTargetsClient


@pytest.mark.unit
def test_default_sources_includes_chembl_and_opentargets() -> None:
    sources = default_sources()
    assert "chembl" in sources
    assert "opentargets" in sources
    assert isinstance(sources["chembl"], ChEMBLSource)
    assert isinstance(sources["opentargets"], OpenTargetsSource)


@pytest.mark.unit
def test_chembl_source_search_mocked() -> None:
    mock_raw = [
        {
            "molecule_chembl_id": "CHEMBL1201585",
            "molecule_pref_name": "TOFACITINIB",
            "standard_type": "IC50",
            "standard_value": "1.6",
            "standard_units": "nM",
            "standard_relation": "=",
            "pchembl_value": "8.80",
        }
    ]

    def mock_fetcher(query: str, limit: int):
        return [
            {
                "native_id": "CHEMBL2111364",
                "title": f"ChEMBL Bioactivity: {mock_raw[0]['molecule_pref_name']}",
                "snippet": "Activity: IC50 = 1.6 nM",
                "evidence_type": "bioactivity",
            }
        ]

    source = ChEMBLSource(fetcher=mock_fetcher)
    request = ResearchRequest(disease_id="ra", question="JAK inhibitors for RA", sources=("chembl",))
    res = source.search(request, ["JAK2"])
    assert res.status.status == "ok"
    assert len(res.records) == 1
    assert res.records[0].source == "chembl"
    assert "TOFACITINIB" in res.records[0].title


@pytest.mark.unit
def test_opentargets_client_disease_targets_mock() -> None:
    class MockOpenTargetsClient(OpenTargetsClient):
        def query(self, query_str: str, variables=None):
            return {
                "disease": {
                    "id": "EFO_0000685",
                    "name": "Rheumatoid Arthritis",
                    "associatedTargets": {
                        "rows": [
                            {
                                "target": {
                                    "id": "ENSG00000096968",
                                    "approvedSymbol": "JAK2",
                                    "approvedName": "Janus kinase 2",
                                },
                                "score": 0.85,
                            }
                        ]
                    },
                }
            }

    client = MockOpenTargetsClient()
    targets = client.search_disease_targets("ra", size=5)
    assert len(targets) == 1
    assert targets[0]["symbol"] == "JAK2"
    assert targets[0]["association_score"] == 0.85
