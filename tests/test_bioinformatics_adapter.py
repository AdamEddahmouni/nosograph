"""Contract tests for bioinformatics BasePipelineModule adapters."""

from __future__ import annotations

from pathlib import Path

import pytest

from med_research.pipeline.bioinformatics.adapter import (
    EnrichmentModule,
    GwasModule,
    PpiModule,
)
from med_research.pipeline.provenance import build_provenance
from tests.test_pipeline_base import ModuleAdapterContract

pytestmark = pytest.mark.unit


class BioinformaticsAdapterContract(ModuleAdapterContract):
    """Shared provenance assertions for bioinformatics adapters."""

    provenance_sources: list[str]
    provenance_scoring: dict

    def test_build_provenance_matches_engine_main(self):
        module = self.module_cls()

        provenance = module.build_provenance(self.disease_id)
        expected = build_provenance(
            disease_id=self.disease_id,
            module=module.module_id,
            sources=self.provenance_sources,
            cache_or_live="cache",
            scoring=self.provenance_scoring,
        )

        for key in ("disease_id", "module", "sources", "cache_or_live", "scoring"):
            assert provenance[key] == expected[key]


class TestGwasAdapter(BioinformaticsAdapterContract):
    module_cls = GwasModule
    module_id = "gwas"
    coverage_module = "gwas"
    coverage_inputs = ("genes", "gwas_search_terms")
    provenance_sources = ["gwas_catalog"]
    provenance_scoring = {"analysis": "gwas_crossref"}

    def test_run_matches_engine(self):
        module = self.module_cls()
        disease_id = self.disease_id

        from med_research.pipeline.bioinformatics.gwas import run_gwas_analysis

        direct = run_gwas_analysis(disease_id=disease_id, use_cache=True)
        wrapped = module.run(disease_id, use_cache=True)

        assert wrapped["status"] == direct["status"]
        assert wrapped["gwas_results"] == direct["gwas_results"]
        assert wrapped["crossref"] == direct["crossref"]

    def test_report_returns_path(self):
        module = self.module_cls()
        disease_id = self.disease_id
        results = module.run(disease_id, use_cache=True)
        assert results.get("status") == "ready"

        provenance = module.build_provenance(disease_id, run_id="bioinformatics-adapter-test")
        report_path = module.report(results, disease_id, provenance=provenance)

        assert isinstance(report_path, Path)
        assert report_path.exists()
        html = report_path.read_text(encoding="utf-8")
        assert provenance["fingerprint"][:12] in html


class TestEnrichmentAdapter(BioinformaticsAdapterContract):
    module_cls = EnrichmentModule
    module_id = "enrichment"
    coverage_module = "enrichment"
    coverage_inputs = ("genes", "pathways")
    provenance_sources = ["enrichr"]
    provenance_scoring = {"analysis": "pathway_enrichment"}

    @pytest.fixture(autouse=True)
    def _stub_enrichr(self, monkeypatch):
        """Exercise the real engine and adapter without calling Enrichr."""
        monkeypatch.setattr(
            "med_research.pipeline.bioinformatics.enrichment.run_enrichment",
            lambda gene_list, **_kwargs: {
                "GO_Biological_Process_2023": {
                    "library": "GO_Biological_Process_2023",
                    "terms": [
                        {
                            "term": "immune system process",
                            "overlap": "3/100",
                            "p_value": 0.001,
                            "adj_p_value": 0.01,
                            "odds_ratio": 2.5,
                            "combined_score": 30.0,
                            "genes": [gene["symbol"] for gene in gene_list[:3]],
                        }
                    ],
                    "total_significant": 1,
                }
            },
        )

    def test_run_matches_engine(self):
        module = self.module_cls()
        disease_id = self.disease_id

        from med_research.pipeline.bioinformatics.enrichment import run_enrichment_analysis

        direct = run_enrichment_analysis(disease_id=disease_id, use_cache=True)
        wrapped = module.run(disease_id, use_cache=True)

        assert wrapped["status"] == direct["status"]
        assert wrapped["enrichment_results"] == direct["enrichment_results"]
        assert wrapped["gene_list"] == direct["gene_list"]
        assert wrapped["kg_pathway_matches"] == direct["kg_pathway_matches"]

    def test_report_returns_path(self):
        module = self.module_cls()
        disease_id = self.disease_id
        results = module.run(disease_id, use_cache=True)
        assert results.get("status") == "ready"

        provenance = module.build_provenance(disease_id, run_id="bioinformatics-adapter-test")
        report_path = module.report(results, disease_id, provenance=provenance)

        assert isinstance(report_path, Path)
        assert report_path.exists()
        html = report_path.read_text(encoding="utf-8")
        assert provenance["fingerprint"][:12] in html


class TestPpiAdapter(BioinformaticsAdapterContract):
    module_cls = PpiModule
    module_id = "ppi"
    coverage_module = "ppi"
    coverage_inputs = ("genes",)
    provenance_sources = ["string"]
    provenance_scoring = {"analysis": "ppi_hub"}

    @pytest.fixture(autouse=True)
    def _stub_string(self, monkeypatch):
        """Exercise the real engine and adapter without calling STRING."""

        def fake_fetch(symbols, confidence):
            id_map = {symbol: f"string-{index}" for index, symbol in enumerate(symbols)}
            string_ids = list(id_map.values())
            interactions = [
                {
                    "stringId_A": source,
                    "stringId_B": target,
                    "score": max(confidence, 0.9),
                }
                for source, target in zip(string_ids, string_ids[1:], strict=False)
            ]
            return id_map, interactions

        monkeypatch.setattr(
            "med_research.pipeline.bioinformatics.ppi._fetch_ppi",
            fake_fetch,
        )

    def test_run_matches_engine(self):
        module = self.module_cls()
        disease_id = self.disease_id

        from med_research.pipeline.bioinformatics.ppi import run_ppi_analysis

        direct = run_ppi_analysis(disease_id=disease_id, use_cache=True)
        wrapped = module.run(disease_id, use_cache=True)

        assert wrapped["status"] == direct["status"]
        assert wrapped["hub_scores"] == direct["hub_scores"]
        assert wrapped["crossref"] == direct["crossref"]
        assert wrapped["graph"] == direct["graph"]

    def test_report_returns_path(self):
        module = self.module_cls()
        disease_id = self.disease_id
        results = module.run(disease_id, use_cache=True)
        assert results.get("hub_scores")

        provenance = module.build_provenance(disease_id, run_id="bioinformatics-adapter-test")
        report_path = module.report(results, disease_id, provenance=provenance)

        assert isinstance(report_path, Path)
        assert report_path.exists()
        html = report_path.read_text(encoding="utf-8")
        assert provenance["fingerprint"][:12] in html
