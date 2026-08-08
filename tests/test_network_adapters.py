"""Contract tests for Wave 2C network pipeline adapters."""

from __future__ import annotations

from pathlib import Path

import med_research.pipeline.cross_disease.adapter  # noqa: F401
import med_research.pipeline.gene_expression.adapter  # noqa: F401
import med_research.pipeline.network_pharmacology.adapter  # noqa: F401
from med_research.diseases.coverage import module_coverage
from med_research.pipeline.cross_disease.adapter import CrossDiseaseModule
from med_research.pipeline.gene_expression.adapter import GeneExpressionModule
from med_research.pipeline.network_pharmacology.adapter import NetworkPharmacologyModule
from tests.test_pipeline_base import ModuleAdapterContract


class TestNetworkPharmacologyAdapter(ModuleAdapterContract):
    module_cls = NetworkPharmacologyModule
    module_id = "network_pharmacology"
    coverage_module = "network_pharm"
    coverage_inputs = ("genes", "relationships")

    def test_run_matches_engine(self):
        module = self.module_cls()
        disease_id = self.disease_id

        from med_research.pipeline.network_pharmacology.analyzer import (
            compute_all_metrics,
        )

        coverage = module_coverage(
            disease_id, self.coverage_module, module.coverage_inputs()
        )
        assert coverage.is_runnable

        direct = compute_all_metrics(disease_id=disease_id)
        wrapped = module.run(disease_id)

        assert isinstance(wrapped, dict)
        assert wrapped.get("status") != "blocked"
        assert wrapped["graph_metrics"] == direct["graph_metrics"]
        assert wrapped["bridge_nodes"] == direct["bridge_nodes"]
        assert wrapped["centrality"].keys() == direct["centrality"].keys()

    def test_report_returns_path(self):
        module = self.module_cls()
        disease_id = self.disease_id
        results = module.run(disease_id)
        assert results.get("graph_metrics")

        provenance = module.build_provenance(disease_id, run_id="network-adapter-test")
        report_path = module.report(results, disease_id, provenance=provenance)

        assert isinstance(report_path, Path)
        assert report_path.exists()
        html = report_path.read_text(encoding="utf-8")
        assert provenance["fingerprint"][:12] in html


class TestGeneExpressionAdapter(ModuleAdapterContract):
    module_cls = GeneExpressionModule
    module_id = "gene_expression"
    coverage_module = "expression"
    coverage_inputs = ("genes", "drugs")

    def test_run_matches_engine(self):
        module = self.module_cls()
        disease_id = self.disease_id

        from med_research.pipeline.gene_expression.correlator import (
            compute_all_correlations,
        )

        direct = compute_all_correlations(disease_id=disease_id, save=False)
        wrapped = module.run(disease_id, save=False)

        assert isinstance(wrapped, list)
        assert len(wrapped) == len(direct)
        assert wrapped[0].keys() == direct[0].keys()
        assert wrapped[0]["composite_score"] == direct[0]["composite_score"]

    def test_report_returns_path(self):
        module = self.module_cls()
        disease_id = self.disease_id
        results = module.run(disease_id, save=False)
        assert results

        provenance = module.build_provenance(disease_id, run_id="network-adapter-test")
        report_path = module.report(results, disease_id, provenance=provenance)

        assert isinstance(report_path, Path)
        assert report_path.exists()
        html = report_path.read_text(encoding="utf-8")
        assert provenance["fingerprint"][:12] in html


class TestCrossDiseaseAdapter(ModuleAdapterContract):
    module_cls = CrossDiseaseModule
    module_id = "cross_disease"
    coverage_module = "cross_disease"
    coverage_inputs = ("genes", "drugs", "pathways")

    def test_run_matches_engine(self):
        module = self.module_cls()
        disease_id = self.disease_id

        from med_research.pipeline.cross_disease.analyzer import (
            compute_cross_disease_analysis,
        )

        direct = compute_cross_disease_analysis()
        wrapped = module.run(disease_id)

        assert isinstance(wrapped, dict)
        assert wrapped.get("status") != "blocked"
        assert wrapped["total_diseases"] == direct["total_diseases"]
        assert len(wrapped["multi_disease_drugs"]) == len(direct["multi_disease_drugs"])
        assert (
            wrapped["multi_disease_drugs"][0]["composite_score"]
            == direct["multi_disease_drugs"][0]["composite_score"]
        )

    def test_report_returns_path(self):
        module = self.module_cls()
        disease_id = self.disease_id
        results = module.run(disease_id)
        assert results.get("multi_disease_drugs")

        provenance = module.build_provenance(disease_id, run_id="network-adapter-test")
        report_path = module.report(results, disease_id, provenance=provenance)

        assert isinstance(report_path, Path)
        assert report_path.exists()
        html = report_path.read_text(encoding="utf-8")
        assert provenance["fingerprint"][:12] in html
