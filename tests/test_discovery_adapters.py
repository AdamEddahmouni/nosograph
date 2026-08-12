"""Contract tests for Wave 2D discovery pipeline adapters."""

from __future__ import annotations

import pytest

import med_research.pipeline.clinical_trials.adapter  # noqa: F401
import med_research.pipeline.literature_mining.adapter  # noqa: F401
import med_research.pipeline.virtual_screening.adapter  # noqa: F401
from med_research.pipeline.clinical_trials.adapter import ClinicalTrialsModule
from med_research.pipeline.literature_mining.adapter import LiteratureMiningModule
from med_research.pipeline.provenance import build_provenance
from med_research.pipeline.virtual_screening.adapter import VirtualScreeningModule
from tests.test_pipeline_base import ModuleAdapterContract

pytestmark = pytest.mark.unit

pytestmark = pytest.mark.unit


class TestLiteratureMiningAdapter(ModuleAdapterContract):
    module_cls = LiteratureMiningModule
    module_id = "literature_mining"
    coverage_module = "literature"
    coverage_inputs = ("genes", "drugs", "pathways", "pubmed_queries")
    disease_id = "sle"

    def test_build_provenance_matches_engine_main(self):
        module = self.module_cls()
        provenance = module.build_provenance(self.disease_id, use_cache=True)
        expected = build_provenance(
            disease_id=self.disease_id,
            module=module.module_id,
            sources=["pubmed"],
            query="",
            cache_or_live="cache",
        )

        for key in ("disease_id", "module", "sources", "cache_or_live"):
            assert provenance[key] == expected[key]

    def test_run_matches_engine(self):
        module = self.module_cls()
        disease_id = self.disease_id

        from med_research.pipeline.literature_mining.miner import mine_literature

        direct_results, direct_entities, direct_candidates, direct_stats = mine_literature(
            use_cache=True,
            disease_id=disease_id,
        )
        direct = {
            "results": direct_results,
            "entities": direct_entities,
            "candidates": direct_candidates,
            "extraction_stats": direct_stats,
        }
        wrapped = module.run(disease_id, use_cache=True)

        assert isinstance(wrapped, dict)
        assert wrapped["results"]["status"] == direct["results"]["status"]
        assert wrapped["results"]["stats"] == direct["results"]["stats"]
        assert len(wrapped["candidates"]) == len(direct["candidates"])

    def test_report_returns_path(self):
        from pathlib import Path

        module = self.module_cls()
        disease_id = self.disease_id
        payload = module.run(disease_id, use_cache=True)
        assert payload["results"].get("status") != "blocked"

        provenance = module.build_provenance(
            disease_id, run_id="discovery-adapter-test", use_cache=True
        )
        report_path = module.report(payload, disease_id, provenance=provenance)

        assert isinstance(report_path, Path)
        assert report_path.exists()
        html = report_path.read_text(encoding="utf-8")
        assert provenance["fingerprint"][:12] in html


class TestClinicalTrialsAdapter(ModuleAdapterContract):
    module_cls = ClinicalTrialsModule
    module_id = "clinical_trials"
    coverage_module = "clinical_trials"
    coverage_inputs = ("genes", "drugs", "trial_query")

    def test_build_provenance_matches_engine_main(self):
        from med_research.diseases.base import Disease

        module = self.module_cls()
        disease_id = self.disease_id
        provenance = module.build_provenance(disease_id, use_cache=True)
        expected = build_provenance(
            disease_id=disease_id,
            module=module.module_id,
            sources=["clinicaltrials_gov"],
            query=Disease(disease_id).get_trial_query(),
            cache_or_live="cache",
        )

        for key in ("disease_id", "module", "sources", "query", "cache_or_live"):
            assert provenance[key] == expected[key]

    def test_run_matches_engine(self, monkeypatch):
        module = self.module_cls()
        disease_id = self.disease_id

        from med_research.pipeline.clinical_trials import tracker

        fixture = {
            "trials": [
                {
                    "nct_id": "NCT00000001",
                    "title": "RA biologic study",
                    "summary": "Phase 2 JAK inhibitor trial.",
                    "status": "RECRUITING",
                    "phases": ["PHASE2"],
                    "primary_phase": "PHASE2",
                    "phase_label": "Phase 2",
                    "interventions": ["Baricitinib"],
                    "intervention_types": ["DRUG"],
                    "sponsor_name": "Example Sponsor",
                    "sponsor_class": "INDUSTRY",
                    "enrollment": 120,
                    "start_date": "2024-01",
                    "completion_date": "",
                    "why_stopped": "",
                    "conditions": ["Rheumatoid Arthritis"],
                    "moa_category": "Type I IFN / JAK-STAT",
                    "kg_matches": {
                        "genes": [],
                        "drugs": [],
                        "gene_count": 0,
                        "drug_count": 0,
                        "has_match": False,
                    },
                }
            ],
            "stats": {
                "total_trials": 1,
                "statuses": {"RECRUITING": 1},
                "phases": {"Phase 2": 1},
                "moas": {"Type I IFN / JAK-STAT": 1},
                "top_sponsors": {"Example Sponsor": 1},
                "kg_matched_trials": 0,
                "total_enrollment": 120,
                "avg_enrollment": 120,
            },
            "kg_crossref": {
                "gene_hits": {},
                "drug_hits": {},
                "trials_with_matches": [],
                "total_matched": 0,
            },
        }

        def fake_track(**kwargs):
            assert kwargs["disease_id"] == disease_id
            return fixture

        monkeypatch.setattr(tracker, "track_trials", fake_track)

        direct = tracker.track_trials(disease_id=disease_id, use_cache=False)
        wrapped = module.run(disease_id, use_cache=False)

        assert wrapped == direct
        assert wrapped["stats"]["total_trials"] == 1

    def test_report_returns_path(self):
        from pathlib import Path

        module = self.module_cls()
        disease_id = self.disease_id
        results = {
            "trials": [],
            "stats": {
                "total_trials": 0,
                "statuses": {},
                "phases": {},
                "moas": {},
                "top_sponsors": {},
                "kg_matched_trials": 0,
                "total_enrollment": 0,
                "avg_enrollment": 0,
            },
            "kg_crossref": {
                "gene_hits": {},
                "drug_hits": {},
                "trials_with_matches": [],
                "total_matched": 0,
            },
        }

        provenance = module.build_provenance(
            disease_id, run_id="discovery-adapter-test", use_cache=True
        )
        report_path = module.report(results, disease_id, provenance=provenance)

        assert isinstance(report_path, Path)
        assert report_path.exists()
        html = report_path.read_text(encoding="utf-8")
        assert provenance["fingerprint"][:12] in html


class TestVirtualScreeningAdapter(ModuleAdapterContract):
    module_cls = VirtualScreeningModule
    module_id = "virtual_screening"
    coverage_module = "screening"
    coverage_inputs = ("genes", "drugs", "pathways", "screening_profile")

    def test_build_provenance_matches_engine_main(self):
        from med_research.pipeline.virtual_screening.screening_strategy import (
            strategy_fingerprint,
            strategy_for_disease,
        )

        module = self.module_cls()
        disease_id = self.disease_id
        strategy = strategy_for_disease(disease_id)
        provenance = module.build_provenance(disease_id)
        expected = build_provenance(
            disease_id=disease_id,
            module=module.module_id,
            sources=["knowledge_graph"],
            cache_or_live="cache",
            scoring={
                "strategy_id": strategy.strategy_id,
                "strategy_fingerprint": strategy_fingerprint(strategy),
            },
        )

        for key in ("disease_id", "module", "sources", "cache_or_live", "scoring"):
            assert provenance[key] == expected[key]

    def test_run_matches_engine(self):
        module = self.module_cls()
        disease_id = self.disease_id

        from med_research.pipeline.virtual_screening.screening import (
            build_compound_library,
            screen_compounds,
        )

        library = build_compound_library(disease_id)
        direct = screen_compounds(
            target_genes=["PTPN22"],
            compound_library=library,
            top_n=5,
            disease_id=disease_id,
        )
        wrapped = module.run(
            disease_id,
            gene="PTPN22",
            compound_library=library,
            top_n=5,
        )

        assert isinstance(wrapped, dict)
        assert wrapped["status"] == direct["status"]
        assert wrapped["stats"]["total_pairings"] == direct["stats"]["total_pairings"]
        assert (
            wrapped["all_results"][0]["composite_score"]
            == direct["all_results"][0]["composite_score"]
        )

    def test_report_returns_path(self):
        from pathlib import Path

        module = self.module_cls()
        disease_id = self.disease_id
        results = module.run(disease_id, gene="PTPN22", top_n=3)
        assert results.get("status") != "blocked"

        provenance = module.build_provenance(disease_id, run_id="discovery-adapter-test")
        report_path = module.report(results, disease_id, provenance=provenance)

        assert isinstance(report_path, Path)
        assert report_path.exists()
        html = report_path.read_text(encoding="utf-8")
        assert provenance["fingerprint"][:12] in html
