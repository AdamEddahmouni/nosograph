"""Contract tests for the knowledge graph pipeline adapter."""

from __future__ import annotations

import json
from pathlib import Path

import networkx as nx
import pytest

from med_research.pipeline.knowledge_graph.adapter import KnowledgeGraphModule
from tests.test_pipeline_base import ModuleAdapterContract

pytestmark = pytest.mark.unit


class TestKnowledgeGraphAdapter(ModuleAdapterContract):
    module_cls = KnowledgeGraphModule
    module_id = "knowledge_graph"
    coverage_module = "kg"
    coverage_inputs = ("genes", "drugs", "pathways", "relationships")

    def test_run_matches_engine(self):
        module = self.module_cls()
        disease_id = self.disease_id

        from med_research.pipeline.knowledge_graph.builder import build_graph

        direct = build_graph(disease_id)
        wrapped = module.run(disease_id)

        assert isinstance(wrapped, nx.MultiDiGraph)
        assert wrapped.number_of_nodes() == direct.number_of_nodes()
        assert wrapped.number_of_edges() == direct.number_of_edges()

    def test_report_returns_path(self):
        module = self.module_cls()
        disease_id = self.disease_id
        graph = module.run(disease_id)
        assert graph is not None

        provenance = module.build_provenance(disease_id, run_id="pipeline-base-test")
        report_path = module.report(graph, disease_id, provenance=provenance)

        assert isinstance(report_path, Path)
        assert report_path.exists()
        payload = json.loads(report_path.read_text(encoding="utf-8"))
        assert payload["disease_id"] == disease_id
        assert isinstance(payload["elements"], list)
        assert len(payload["elements"]) == graph.number_of_nodes() + graph.number_of_edges()
