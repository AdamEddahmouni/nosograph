"""Unit tests for BasePipelineModule pilot adapters and registry."""

from __future__ import annotations

import pytest

from med_research.diseases.coverage import module_coverage
from med_research.pipeline.base import BasePipelineModule, PipelineRunResult
from med_research.pipeline.drug_repurposing.adapter import DrugRepurposingModule
from med_research.pipeline.drug_synergy.adapter import DrugSynergyModule
from med_research.pipeline.provenance import build_provenance
from med_research.pipeline.registry import (
    MODULE_REGISTRY,
    get_module,
)

pytestmark = pytest.mark.unit


def assert_monotonic_progress(calls: list[tuple[str, int, int]]) -> None:
    """Assert standard progress ticks stay within bounds and advance per step."""

    assert calls, "expected at least one progress tick"
    prev_by_step: dict[str, int] = {}
    for step, current, total in calls:
        assert total >= 0
        assert 0 <= current <= total, f"current {current} exceeds total {total} for step {step!r}"
        prev = prev_by_step.get(step, 0)
        assert current >= prev, f"non-monotonic progress for {step!r}: {prev} -> {current}"
        prev_by_step[step] = current


class ModuleAdapterContract:
    """Reusable pytest contract for ``BasePipelineModule`` adapters.

    Subclass per module and set ``module_cls``, ``module_id``, ``coverage_module``,
    and ``coverage_inputs``. Override ``test_run_matches_engine`` and
    ``test_report_returns_path`` when the adapter delegates to a known engine.
    """

    module_cls: type[BasePipelineModule]
    module_id: str
    coverage_module: str
    coverage_inputs: tuple[str, ...]
    disease_id: str = "ra"

    def test_module_id_and_coverage_inputs(self):
        module = self.module_cls()
        assert module.module_id == self.module_id
        assert module.coverage_inputs() == self.coverage_inputs

        coverage = module_coverage(self.disease_id, self.coverage_module, module.coverage_inputs())
        assert coverage.is_runnable
        assert set(module.coverage_inputs()).issubset(set(coverage.curated_inputs))

    def test_build_provenance_matches_engine_main(self):
        module = self.module_cls()

        provenance = module.build_provenance(self.disease_id)
        expected = build_provenance(
            disease_id=self.disease_id,
            module=module.module_id,
            sources=["knowledge_graph"],
            cache_or_live="cache",
            scoring={"ranking": "composite_score"},
        )

        for key in ("disease_id", "module", "sources", "cache_or_live", "scoring"):
            assert provenance[key] == expected[key]

        coverage = module_coverage(self.disease_id, self.coverage_module, module.coverage_inputs())
        assert coverage.is_runnable

    def test_registered_in_module_registry(self):
        assert self.module_id in MODULE_REGISTRY
        assert MODULE_REGISTRY[self.module_id] is self.module_cls
        instance = get_module(self.module_id)
        assert isinstance(instance, self.module_cls)
        assert instance.module_id == self.module_id


class TestDrugRepurposingAdapter(ModuleAdapterContract):
    module_cls = DrugRepurposingModule
    module_id = "drug_repurposing"
    coverage_module = "repurposing"
    coverage_inputs = ("genes", "drugs", "relationships")

    def test_run_matches_engine(self):
        module = self.module_cls()
        disease_id = self.disease_id

        from med_research.pipeline.drug_repurposing.engine import (
            DATA_DIR,
            identify_untargeted_genes,
            load_genes,
            load_json,
            load_knowledge_graph,
            score_candidates,
        )

        coverage = module_coverage(disease_id, self.coverage_module, module.coverage_inputs())
        assert coverage.is_runnable

        graph = load_knowledge_graph(disease_id)
        genes = load_genes(disease_id)
        candidates = load_json(DATA_DIR / "candidates.json")["repurposing_candidates"]
        untargeted_ids = {gene["id"] for gene in identify_untargeted_genes(graph, disease_id)}
        direct = [
            candidate
            for candidate in score_candidates(graph, candidates, genes, disease_id=disease_id)
            if candidate["gene_id"] in untargeted_ids
        ]

        wrapped = module.run(disease_id)

        assert isinstance(wrapped, list)
        assert len(wrapped) == len(direct)
        assert wrapped[0].keys() == direct[0].keys()
        assert wrapped[0]["composite_score"] == direct[0]["composite_score"]

    def test_report_returns_path(self):
        from pathlib import Path

        module = self.module_cls()
        disease_id = self.disease_id
        scored = module.run(disease_id)
        assert scored

        provenance = module.build_provenance(disease_id, run_id="pipeline-base-test")
        report_path = module.report(scored, disease_id, provenance=provenance)

        assert isinstance(report_path, Path)
        assert report_path.exists()
        html = report_path.read_text(encoding="utf-8")
        assert provenance["fingerprint"][:12] in html


class TestDrugSynergyAdapter(ModuleAdapterContract):
    module_cls = DrugSynergyModule
    module_id = "drug_synergy"
    coverage_module = "synergy"
    coverage_inputs = ("genes", "drugs")

    def test_run_matches_engine(self):
        module = self.module_cls()
        disease_id = self.disease_id

        direct = __import__(
            "med_research.pipeline.drug_synergy.engine",
            fromlist=["compute_synergy"],
        ).compute_synergy(disease_id=disease_id, save=False)
        wrapped = module.run(disease_id, save=False)

        assert isinstance(wrapped, list)
        assert len(wrapped) == len(direct)
        assert wrapped[0].keys() == direct[0].keys()
        assert wrapped[0]["composite_score"] == direct[0]["composite_score"]

    def test_report_returns_path(self):
        from pathlib import Path

        module = self.module_cls()
        disease_id = self.disease_id
        pairs = module.run(disease_id, save=False)
        assert pairs

        provenance = module.build_provenance(disease_id, run_id="pipeline-base-test")
        report_path = module.report(pairs, disease_id, provenance=provenance)

        assert isinstance(report_path, Path)
        assert report_path.exists()
        html = report_path.read_text(encoding="utf-8")
        assert provenance["fingerprint"][:12] in html


def test_list_modules_auto_registers_on_registry_import():
    import sys

    from med_research.pipeline import registry as registry_module

    # Purge only the adapter modules so their ``@register_module`` decorators
    # re-run on import. Purging the entire ``med_research.pipeline`` module
    # tree (as this test once did) leaves ``sys.modules`` entries pointing at
    # different objects than the package attribute chains, which silently
    # breaks later ``monkeypatch.setattr`` on engine modules (e.g. the CLI
    # coverage-boost tests in test_web_registry.py).
    adapter_keys = sorted(
        key
        for key in sys.modules
        if key.startswith("med_research.pipeline.") and key.endswith(".adapter")
    )
    saved_registry = dict(MODULE_REGISTRY)
    saved_adapters = {key: sys.modules[key] for key in adapter_keys}

    try:
        MODULE_REGISTRY.clear()
        registry_module._REGISTRATION_COMPLETE = False
        for key in adapter_keys:
            del sys.modules[key]

        modules = registry_module.list_modules()
        assert len(modules) >= 2
        assert "drug_repurposing" in modules
        assert "drug_synergy" in modules
        assert modules == sorted(registry_module.MODULE_REGISTRY.keys())
    finally:
        MODULE_REGISTRY.clear()
        MODULE_REGISTRY.update(saved_registry)
        registry_module._REGISTRATION_COMPLETE = True
        for key, module in saved_adapters.items():
            sys.modules[key] = module


def test_get_module_unknown_raises_key_error():
    with pytest.raises(KeyError, match="Unknown pipeline module"):
        get_module("not_a_real_module")


def test_pipeline_run_result_defaults():
    result = PipelineRunResult(success=True, data=[])
    assert result.report_path is None
    assert result.provenance is None
    assert result.errors == []
