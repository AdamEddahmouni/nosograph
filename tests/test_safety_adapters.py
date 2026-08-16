"""Contract tests for Wave 2B safety pipeline adapters."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent))

from test_pipeline_base import ModuleAdapterContract

from med_research.diseases.coverage import module_coverage
from med_research.pipeline.adverse_events.adapter import AdverseEventsModule
from med_research.pipeline.biomarker_discovery.adapter import BiomarkerDiscoveryModule
from med_research.pipeline.car_t_predictor.adapter import CarTPredictorModule
from med_research.pipeline.provenance import build_provenance

pytestmark = pytest.mark.unit


class TestAdverseEventsAdapter(ModuleAdapterContract):
    module_cls = AdverseEventsModule
    module_id = "adverse_events"
    coverage_module = "safety"
    coverage_inputs = ("symptoms", "adverse_event_profile", "safety_risk")

    def test_build_provenance_matches_engine_main(self):
        module = self.module_cls()
        provenance = module.build_provenance(self.disease_id)
        expected = build_provenance(
            disease_id=self.disease_id,
            module=module.module_id,
            sources=["fda_labels"],
            cache_or_live="cache",
        )

        for key in ("disease_id", "module", "sources", "cache_or_live", "scoring"):
            assert provenance[key] == expected[key]

        coverage = module_coverage(self.disease_id, self.coverage_module, module.coverage_inputs())
        assert coverage.is_runnable

    def test_run_matches_engine(self):
        module = self.module_cls()
        disease_id = self.disease_id

        from med_research.pipeline.adverse_events.profiler import score_all_drugs

        direct = score_all_drugs(disease_id=disease_id)
        wrapped = module.run(disease_id)

        assert isinstance(wrapped, list)
        assert len(wrapped) == len(direct)
        assert wrapped[0].keys() == direct[0].keys()
        assert wrapped[0]["composite_safety_score"] == direct[0]["composite_safety_score"]

    def test_report_returns_path(self):
        module = self.module_cls()
        disease_id = self.disease_id
        scored = module.run(disease_id)
        assert scored

        provenance = module.build_provenance(disease_id, run_id="safety-adapter-test")
        report_path = module.report(scored, disease_id, provenance=provenance)

        assert isinstance(report_path, Path)
        assert report_path.exists()
        html = report_path.read_text(encoding="utf-8")
        assert provenance["fingerprint"][:12] in html


class TestCarTPredictorAdapter(ModuleAdapterContract):
    module_cls = CarTPredictorModule
    module_id = "car_t_predictor"
    coverage_module = "car_t"
    coverage_inputs = ("genes", "car_t_scores")

    def test_build_provenance_matches_engine_main(self):
        module = self.module_cls()
        provenance = module.build_provenance(self.disease_id)
        expected = build_provenance(
            disease_id=self.disease_id,
            module=module.module_id,
            sources=["knowledge_graph"],
            cache_or_live="cache",
            scoring={"ranking": "car_t_heuristic"},
        )

        for key in ("disease_id", "module", "sources", "cache_or_live", "scoring"):
            assert provenance[key] == expected[key]

        coverage = module_coverage(self.disease_id, self.coverage_module, module.coverage_inputs())
        assert coverage.is_runnable

    def test_run_matches_engine(self):
        module = self.module_cls()
        disease_id = self.disease_id

        from med_research.pipeline.car_t_predictor.predictor import compute_all_scores

        direct = compute_all_scores(disease_id=disease_id)
        wrapped = module.run(disease_id)

        assert isinstance(wrapped, list)
        assert len(wrapped) == len(direct)
        assert wrapped[0].keys() == direct[0].keys()
        assert wrapped[0]["composite_score"] == direct[0]["composite_score"]

    def test_report_returns_path(self):
        module = self.module_cls()
        disease_id = self.disease_id
        scored = module.run(disease_id)
        assert scored

        provenance = module.build_provenance(disease_id, run_id="safety-adapter-test")
        report_path = module.report(scored, disease_id, provenance=provenance)

        assert isinstance(report_path, Path)
        assert report_path.exists()
        html = report_path.read_text(encoding="utf-8")
        assert provenance["fingerprint"][:12] in html


class TestBiomarkerDiscoveryAdapter(ModuleAdapterContract):
    module_cls = BiomarkerDiscoveryModule
    module_id = "biomarker_discovery"
    coverage_module = "biomarkers"
    coverage_inputs = ("genes",)

    def test_build_provenance_matches_engine_main(self):
        module = self.module_cls()
        provenance = module.build_provenance(self.disease_id)
        expected = build_provenance(
            disease_id=self.disease_id,
            module=module.module_id,
            sources=[
                "knowledge_graph",
                "gene_expression",
                "car_t_predictor",
                "drug_repurposing",
                "adverse_events",
                "drug_synergy",
            ],
            cache_or_live="cache",
        )

        for key in ("disease_id", "module", "sources", "cache_or_live", "scoring"):
            assert provenance[key] == expected[key]

        coverage = module_coverage(self.disease_id, self.coverage_module, module.coverage_inputs())
        assert coverage.is_runnable

    def test_run_matches_engine(self):
        module = self.module_cls()
        disease_id = self.disease_id

        from med_research.pipeline.biomarker_discovery.discover import (
            compute_biomarker_matrix,
        )

        direct = compute_biomarker_matrix(disease_id=disease_id, save=False)
        wrapped = module.run(disease_id, save=False)

        assert isinstance(wrapped, list)
        assert len(wrapped) == len(direct)
        assert wrapped[0].keys() == direct[0].keys()
        assert wrapped[0]["composite_score"] == direct[0]["composite_score"]

    def test_report_returns_path(self):
        module = self.module_cls()
        disease_id = self.disease_id
        scored = module.run(disease_id, save=False)
        assert scored

        provenance = module.build_provenance(disease_id, run_id="safety-adapter-test")
        report_path = module.report(scored, disease_id, provenance=provenance)

        assert isinstance(report_path, Path)
        assert report_path.exists()
        html = report_path.read_text(encoding="utf-8")
        assert provenance["fingerprint"][:12] in html
