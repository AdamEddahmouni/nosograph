"""HTTP mocks for offline integration tests (PubMed, ClinicalTrials.gov, etc.)."""

from __future__ import annotations

import pytest

SAMPLE_PUBMED_ARTICLES = [
    {
        "pmid": "99001001",
        "title": "Kinase inhibition in autoimmune arthritis",
        "abstract": "JAK inhibitors show efficacy in rheumatoid arthritis trials.",
        "authors": ["Chen L", "Patel R"],
        "journal": "Ann Rheum Dis",
        "year": "2024",
        "publication_types": ["Journal Article"],
        "mesh_terms": ["Arthritis, Rheumatoid"],
    },
    {
        "pmid": "99001002",
        "title": "B cell pathways in inflammatory disease",
        "abstract": "BTK signaling modulates autoreactive B cells.",
        "authors": ["Jones K"],
        "journal": "Nat Rev Rheumatol",
        "year": "2023",
        "publication_types": ["Review"],
        "mesh_terms": ["B-Lymphocytes"],
    },
]

MINIMAL_CT_STUDY = {
    "protocolSection": {
        "identificationModule": {
            "nctId": "NCT99001001",
            "briefTitle": "Phase 2 study of JAK inhibitor in RA",
        },
        "statusModule": {"overallStatus": "RECRUITING"},
        "descriptionModule": {
            "briefTitle": "Phase 2 study of JAK inhibitor in RA",
            "briefSummary": "Interventional trial for rheumatoid arthritis.",
        },
        "designModule": {
            "phases": ["PHASE2"],
            "enrollmentInfo": {"count": 120},
        },
        "armsInterventionsModule": {
            "interventions": [{"name": "baricitinib", "type": "DRUG"}],
        },
        "sponsorCollaboratorsModule": {
            "leadSponsor": {"name": "Academic Medical Center"},
        },
        "conditionsModule": {"conditions": ["Rheumatoid Arthritis"]},
    }
}

SAMPLE_ENRICHMENT = {
    "GO_Biological_Process_2023": {
        "library": "GO_Biological_Process_2023",
        "terms": [
            {
                "term": "immune response",
                "p_value": 0.001,
                "adj_p_value": 0.01,
                "odds_ratio": 2.5,
                "combined_score": 30.0,
                "genes": ["BTK", "TYK2"],
            }
        ],
        "total_significant": 1,
    }
}


@pytest.fixture
def offline_pipeline_http_mocks(monkeypatch):
    """Stub external HTTP for offline run-all and scheduler integration tests."""
    from med_research.pipeline.bioinformatics import enrichment, gwas, ppi
    from med_research.pipeline.clinical_trials import tracker
    from med_research.pipeline.gene_expression import geo
    from med_research.pipeline.literature_mining import miner

    def fake_search_pubmed(query: str, max_results: int = 50, email: str | None = None, **kwargs):
        return SAMPLE_PUBMED_ARTICLES[:max_results]

    def fake_search_clinical_trials(query: str, max_results: int = 100, **kwargs):
        return [MINIMAL_CT_STUDY]

    def fake_run_gwas_analysis(disease_id: str = "sle", **kwargs):
        return {
            "gwas_results": [],
            "crossref": {
                "validated": [],
                "novel": [],
                "missing": [],
                "n_validated": 0,
                "n_novel": 0,
                "n_missing": 0,
            },
            "status": "ready",
        }

    def fake_run_enrichment_analysis(disease_id: str = "sle", **kwargs):
        return {
            "enrichment_results": SAMPLE_ENRICHMENT,
            "gene_list": [{"symbol": "BTK", "id": "BTK"}],
            "kg_pathway_matches": {},
            "status": "ready",
        }

    def fake_run_ppi_analysis(disease_id: str = "sle", **kwargs):
        return {
            "hub_scores": [{"symbol": "BTK", "hub_score": 1.0, "degree": 2}],
            "crossref": {},
            "graph": {"nodes": [{"id": "BTK"}], "edges": []},
            "status": "ready",
        }

    def fake_search_geo_datasets(
        disease: str = "sle",
        category: str = "broad",
        max_results: int = 30,
        no_cache: bool = False,
    ):
        return []

    monkeypatch.setattr(miner, "search_pubmed", fake_search_pubmed)
    monkeypatch.setattr(tracker, "search_clinical_trials", fake_search_clinical_trials)
    monkeypatch.setattr(gwas, "run_gwas_analysis", fake_run_gwas_analysis)
    monkeypatch.setattr(enrichment, "run_enrichment_analysis", fake_run_enrichment_analysis)
    monkeypatch.setattr(ppi, "run_ppi_analysis", fake_run_ppi_analysis)
    monkeypatch.setattr(geo, "search_geo_datasets", fake_search_geo_datasets)

    yield
