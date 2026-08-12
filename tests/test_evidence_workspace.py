import networkx as nx
import pytest

from med_research.pipeline.evidence_workspace.schemas import ResearchRequest
from med_research.pipeline.evidence_workspace.sources import ClinicalTrialsSource, PubMedSource
from med_research.pipeline.evidence_workspace.workspace import run_workspace

pytestmark = pytest.mark.unit


def test_workspace_assembles_evidence_claims_rankings_and_manifest():
    sources = {
        "pubmed": PubMedSource(
            lambda query, limit: [
                {
                    "id": "1",
                    "title": "Baricitinib JAK1 study in SLE",
                    "abstract": "Baricitinib targets JAK1 and improved disease activity.",
                    "year": "2024",
                    "url": "https://pubmed.ncbi.nlm.nih.gov/1/",
                }
            ]
        ),
        "clinical_trials": ClinicalTrialsSource(
            lambda query, limit: [
                {
                    "nct_id": "NCT0001",
                    "title": "JAK1 clinical trial",
                    "summary": "Baricitinib targets JAK1.",
                    "year": "2023",
                    "phase": "PHASE3",
                }
            ]
        ),
    }
    graph = nx.MultiDiGraph()
    graph.add_node("SLE", type="disease", label="SLE")
    graph.add_node("baricitinib", type="drug", label="Baricitinib")
    graph.add_node("JAK1", type="gene", label="JAK1")
    graph.add_edge("baricitinib", "JAK1", type="TARGETS")
    graph.add_edge("JAK1", "SLE", type="ASSOCIATED_WITH")

    dossier = run_workspace(
        ResearchRequest(question="Find JAK interventions for SLE", enable_llm=True),
        sources=sources,
        graph=graph,
    )

    assert dossier.evidence
    assert dossier.claims
    assert dossier.drug_rankings
    assert dossier.target_rankings
    assert dossier.graph_explanations
    assert dossier.manifest["llm"]["status"] == "skipped"
    assert all(claim.evidence_ids for claim in dossier.claims)


def test_workspace_manifest_reports_source_retrieval_modes():
    from med_research.pipeline.evidence_workspace.schemas import SourceStatus
    from med_research.pipeline.evidence_workspace.sources import SourceResult

    class FixtureSource:
        name = "pubmed"

        def search(self, request, terms):
            return SourceResult(
                [],
                SourceStatus(
                    source="pubmed",
                    status="ok",
                    retrieval_mode="cache",
                    query_terms=terms,
                ),
            )

    dossier = run_workspace(
        ResearchRequest(question="JAK interventions"),
        sources={"pubmed": FixtureSource(), "clinical_trials": FixtureSource()},
        graph=nx.MultiDiGraph(),
    )

    assert dossier.manifest["cache_or_live"] == "cache"
    assert dossier.manifest["provenance"]["cache_or_live"] == "cache"


def test_workspace_continues_when_one_source_fails():
    sources = {
        "pubmed": PubMedSource(lambda query, limit: (_ for _ in ()).throw(RuntimeError("offline"))),
        "clinical_trials": ClinicalTrialsSource(
            lambda query, limit: [
                {
                    "nct_id": "NCT0002",
                    "title": "Baricitinib trial",
                    "summary": "Baricitinib targets JAK1.",
                    "year": "2023",
                }
            ]
        ),
    }

    dossier = run_workspace(
        ResearchRequest(question="JAK interventions"), sources=sources, graph=nx.MultiDiGraph()
    )

    assert dossier.evidence
    assert any("offline" in warning for warning in dossier.warnings)
    assert any(
        status.source == "pubmed" and status.status == "error" for status in dossier.source_statuses
    )
