import pytest
from unittest.mock import patch

from med_research.pipeline.external import (
    BioRxivClient,
    ChEMBLClient,
    GTExClient,
    OpenTargetsClient,
    UniProtClient,
)
from med_research.pipeline.evidence_workspace.schemas import ResearchRequest
from med_research.pipeline.evidence_workspace.sources import (
    BioRxivSource,
    GTExSource,
    OpenTargetsSource,
)

pytestmark = pytest.mark.unit


def test_opentargets_client_get_target_details():
    mock_response = {
        "data": {
            "search": {
                "hits": [
                    {
                        "object": {
                            "id": "ENSG00000096968",
                            "approvedSymbol": "JAK2",
                            "approvedName": "Janus kinase 2",
                            "biotype": "protein_coding",
                        }
                    }
                ]
            }
        }
    }
    with patch("med_research.pipeline.external.opentargets.fetch_json", return_value=mock_response):
        client = OpenTargetsClient()
        details = client.get_target_details("JAK2")
        assert details["symbol"] == "JAK2"
        assert details["ensembl_id"] == "ENSG00000096968"
        assert details["name"] == "Janus kinase 2"


def test_opentargets_client_search_disease_targets():
    mock_response = {
        "data": {
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
    }
    with patch("med_research.pipeline.external.opentargets.fetch_json", return_value=mock_response):
        client = OpenTargetsClient()
        targets = client.search_disease_targets("ra", size=5)
        assert len(targets) == 1
        assert targets[0]["symbol"] == "JAK2"
        assert targets[0]["association_score"] == 0.85


def test_gtex_client_median_expression():
    mock_gene_info = {"data": {"gene": [{"gencodeId": "ENSG00000096968.10", "geneSymbol": "JAK2"}]}}
    mock_expression = {
        "medianGeneExpression": [
            {"tissueSiteDetailId": "Whole_Blood", "median": 45.2},
            {"tissueSiteDetailId": "Liver", "median": 12.1},
        ]
    }

    def side_effect(url, params=None, body=None, headers=None, timeout=30, retries=3):
        if "reference/gene" in url:
            return mock_gene_info["data"]
        return mock_expression

    with patch("med_research.pipeline.external.gtex.fetch_json", side_effect=side_effect):
        client = GTExClient()
        exp = client.get_median_tissue_expression("JAK2")
        assert len(exp) == 2
        assert exp[0]["tissue_site_detail_id"] == "Whole_Blood"
        assert exp[0]["median_tpm"] == 45.2


def test_chembl_client_search_target():
    mock_resp = {
        "targets": [
            {
                "target_chembl_id": "CHEMBL2971",
                "pref_name": "Tyrosine-protein kinase JAK2",
                "target_type": "SINGLE PROTEIN",
                "organism": "Homo sapiens",
            }
        ]
    }
    with patch("med_research.pipeline.external.chembl_uniprot.fetch_json", return_value=mock_resp):
        client = ChEMBLClient()
        res = client.search_target("JAK2")
        assert res is not None
        assert res["target_chembl_id"] == "CHEMBL2971"
        assert "JAK2" in res["pref_name"]


def test_uniprot_client_get_protein():
    mock_resp = {
        "results": [
            {
                "primaryAccession": "O60674",
                "proteinDescription": {
                    "recommendedName": {"fullName": {"value": "Janus kinase 2"}}
                },
                "comments": [{"commentType": "FUNCTION", "texts": [{"value": "Non-receptor tyrosine kinase."}]}],
                "features": [{"type": "DOMAIN", "description": "Protein kinase"}],
                "sequence": {"length": 1132},
            }
        ]
    }
    with patch("med_research.pipeline.external.chembl_uniprot.fetch_json", return_value=mock_resp):
        client = UniProtClient()
        protein = client.get_protein_by_gene("JAK2")
        assert protein is not None
        assert protein["accession"] == "O60674"
        assert protein["protein_name"] == "Janus kinase 2"
        assert "kinase" in protein["function_summary"]


def test_biorxiv_client_search():
    mock_resp = {
        "collection": [
            {
                "doi": "10.1101/2024.01.01.123456",
                "title": "Novel JAK2 Inhibitor in Rheumatoid Arthritis",
                "authors": "Smith et al.",
                "date": "2024-01-02",
                "abstract": "We describe JAK2 inhibition in RA mouse models.",
            }
        ]
    }
    with patch("med_research.pipeline.external.biorxiv.fetch_json", return_value=mock_resp):
        client = BioRxivClient()
        preprints = client.search_preprints_by_keyword("JAK2")
        assert len(preprints) == 1
        assert preprints[0]["doi"] == "10.1101/2024.01.01.123456"
        assert "JAK2" in preprints[0]["title"]


def test_opentargets_workspace_source():
    source = OpenTargetsSource(
        lambda query, limit: [
            {"native_id": "ENSG00000096968", "title": "Target: JAK2", "snippet": "Score 0.9", "evidence_type": "target_association"}
        ]
    )
    res = source.search(ResearchRequest(question="Target discovery"), ["JAK2"])
    assert res.status.status == "ok"
    assert len(res.records) == 1
    assert res.records[0].source == "opentargets"


def test_gtex_workspace_source():
    source = GTExSource(
        lambda query, limit: [
            {"native_id": "JAK2:Whole_Blood", "title": "GTEx: JAK2 Whole Blood", "snippet": "45 TPM", "evidence_type": "gene_expression"}
        ]
    )
    res = source.search(ResearchRequest(question="Expression lookup"), ["JAK2"])
    assert res.status.status == "ok"
    assert len(res.records) == 1
    assert res.records[0].source == "gtex"


def test_biorxiv_workspace_source():
    source = BioRxivSource(
        lambda query, limit: [
            {"native_id": "10.1101/123", "title": "JAK2 Preprint", "snippet": "Abstract...", "url": "https://biorxiv.org", "evidence_type": "preprint"}
        ]
    )
    res = source.search(ResearchRequest(question="Preprints"), ["JAK2"])
    assert res.status.status == "ok"
    assert len(res.records) == 1
    assert res.records[0].source == "biorxiv"
