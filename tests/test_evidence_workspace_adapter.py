"""Contract tests for the evidence workspace registry adapter."""

from __future__ import annotations

from pathlib import Path

import networkx as nx

import med_research.pipeline.evidence_workspace.adapter  # noqa: F401
from med_research.pipeline.evidence_workspace.adapter import EvidenceWorkspaceModule
from med_research.pipeline.evidence_workspace.schemas import ResearchRequest
from med_research.pipeline.evidence_workspace.sources import ClinicalTrialsSource, PubMedSource
from med_research.pipeline.evidence_workspace.workspace import run_workspace
from med_research.pipeline.provenance import build_provenance
from med_research.pipeline.registry import MODULE_REGISTRY, get_module
from tests.test_pipeline_base import ModuleAdapterContract


def _fixture_sources():
    return {
        "pubmed": PubMedSource(
            lambda query, limit: [
                {
                    "id": "1",
                    "title": "Baricitinib JAK1 study in RA",
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


class TestEvidenceWorkspaceAdapter(ModuleAdapterContract):
    module_cls = EvidenceWorkspaceModule
    module_id = "evidence_workspace"
    coverage_module = "evidence_workspace"
    coverage_inputs = ()
    disease_id = "ra"

    def test_depends_on_knowledge_graph(self):
        module = self.module_cls()
        assert module.depends_on == ("knowledge_graph",)

    def test_build_provenance_matches_engine_main(self):
        module = self.module_cls()
        provenance = module.build_provenance(
            self.disease_id,
            question="JAK interventions for rheumatoid arthritis",
        )
        expected = build_provenance(
            disease_id=self.disease_id,
            module=module.module_id,
            sources=["pubmed", "clinical_trials"],
            query="JAK interventions for rheumatoid arthritis",
            cache_or_live="cache",
            scoring={
                "ranking": "support/contradiction/recency/quality heuristic",
                "candidate_type": "both",
            },
        )

        for key in ("disease_id", "module", "sources", "cache_or_live", "query", "scoring"):
            assert provenance[key] == expected[key]

    def test_run_matches_engine(self):
        module = self.module_cls()
        disease_id = self.disease_id
        graph = nx.MultiDiGraph()
        sources = _fixture_sources()
        request = ResearchRequest(
            disease_id=disease_id,
            question="Find JAK interventions for RA",
            enable_llm=False,
        )

        direct = run_workspace(request, sources=sources, graph=graph)
        wrapped = module.run(
            disease_id,
            request=request,
            sources=sources,
            graph=graph,
        )

        assert len(wrapped.evidence) == len(direct.evidence)
        assert len(wrapped.claims) == len(direct.claims)
        assert wrapped.request.question == direct.request.question
        assert wrapped.manifest["provenance"]["module"] == "evidence_workspace"

    def test_report_returns_path(self):
        module = self.module_cls()
        disease_id = self.disease_id
        dossier = module.run(
            disease_id,
            question="Find JAK interventions for RA",
            sources=_fixture_sources(),
            graph=nx.MultiDiGraph(),
            enable_llm=False,
        )
        assert dossier.evidence

        provenance = module.build_provenance(
            disease_id,
            question=dossier.request.question,
            run_id="evidence-workspace-adapter-test",
        )
        report_path = module.report(dossier, disease_id, provenance=provenance)

        assert isinstance(report_path, Path)
        assert report_path.exists()
        html = report_path.read_text(encoding="utf-8")
        assert provenance["fingerprint"][:12] in html


def test_evidence_workspace_adapter_registered():
    assert "evidence_workspace" in MODULE_REGISTRY
    instance = get_module("evidence_workspace")
    assert instance.module_id == "evidence_workspace"
    assert instance.depends_on == ("knowledge_graph",)
