"""Common pipeline module interface (pilot).

This module introduces a minimal ABC so future work can add centralized
caching, progress callbacks, and uniform CLI/web wiring without refactoring
every engine at once. Migrate additional modules by subclassing
``BasePipelineModule`` and delegating to existing ``run``/``report`` helpers.

Pilot adapters: ``DrugRepurposingModule``, ``DrugSynergyModule``.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from med_research.pipeline.provenance import build_provenance
from med_research.pipeline.registry import register_module


@dataclass
class PipelineRunResult:
    """Normalized outcome from a registry-backed module run."""

    success: bool
    data: Any
    report_path: Path | None = None
    provenance: dict[str, Any] | None = None
    errors: list[str] = field(default_factory=list)


class BasePipelineModule(ABC):
    """Minimal contract shared by disease-aware analysis modules."""

    @property
    @abstractmethod
    def module_id(self) -> str:
        """Stable module identifier used in provenance metadata."""

    @abstractmethod
    def coverage_inputs(self) -> tuple[str, ...]:
        """Curated input keys passed to ``module_coverage()``."""

    @abstractmethod
    def run(self, disease_id: str, **opts: Any) -> Any:
        """Execute the module for a disease and return raw results."""

    @abstractmethod
    def report(
        self,
        results: Any,
        disease_id: str,
        *,
        provenance: dict[str, Any] | None = None,
    ) -> Path:
        """Render an HTML report from ``run()`` output and return its path."""

    @abstractmethod
    def build_provenance(self, disease_id: str, **opts: Any) -> dict[str, Any]:
        """Build reproducibility metadata for a disease run."""

    @property
    def depends_on(self) -> tuple[str, ...]:
        """Registry module IDs that must complete before this module runs."""

        return ()


@register_module
class DrugRepurposingModule(BasePipelineModule):
    """Adapter around ``drug_repurposing.engine`` scoring and reporting."""

    _COVERAGE_MODULE = "repurposing"

    @property
    def module_id(self) -> str:
        return "drug_repurposing"

    @property
    def depends_on(self) -> tuple[str, ...]:
        return ("knowledge_graph",)

    def coverage_inputs(self) -> tuple[str, ...]:
        return ("genes", "drugs", "relationships")

    def run(self, disease_id: str, **opts: Any) -> list:
        from med_research.diseases.coverage import module_coverage
        from med_research.pipeline.drug_repurposing.engine import (
            DATA_DIR,
            identify_untargeted_genes,
            load_genes,
            load_json,
            load_knowledge_graph,
            score_candidates,
        )

        coverage = module_coverage(
            disease_id, self._COVERAGE_MODULE, self.coverage_inputs()
        )
        if not coverage.is_runnable:
            return []

        graph = load_knowledge_graph(disease_id)
        genes = load_genes(disease_id)
        candidates_data = load_json(DATA_DIR / "candidates.json")
        candidates = candidates_data["repurposing_candidates"]

        untargeted = identify_untargeted_genes(graph, disease_id)
        untargeted_ids = {gene["id"] for gene in untargeted}

        scored = score_candidates(graph, candidates, genes, disease_id=disease_id)
        gene_id = opts.get("gene_id")
        untargeted_only = opts.get("untargeted_only", gene_id is None)
        if gene_id:
            scored = [candidate for candidate in scored if candidate["gene_id"] == gene_id]
        elif untargeted_only:
            scored = [
                candidate for candidate in scored if candidate["gene_id"] in untargeted_ids
            ]
        return scored

    def report(
        self,
        results: list,
        disease_id: str,
        *,
        provenance: dict[str, Any] | None = None,
    ) -> Path:
        from med_research.pipeline.drug_repurposing.engine import (
            identify_untargeted_genes,
            load_genes,
            load_knowledge_graph,
        )
        from med_research.pipeline.drug_repurposing.report import generate_html_report

        graph = load_knowledge_graph(disease_id)
        genes = load_genes(disease_id)
        untargeted = identify_untargeted_genes(graph, disease_id)

        report_path = generate_html_report(
            results,
            untargeted,
            genes,
            graph,
            disease_id=disease_id,
            provenance=provenance,
        )
        return Path(report_path)

    def build_provenance(self, disease_id: str, **opts: Any) -> dict[str, Any]:
        return build_provenance(
            disease_id=disease_id,
            module=self.module_id,
            sources=["knowledge_graph"],
            cache_or_live="cache",
            scoring={"ranking": "composite_score"},
            **opts,
        )


@register_module
class DrugSynergyModule(BasePipelineModule):
    """Adapter around ``drug_synergy.engine`` scoring and reporting."""

    _COVERAGE_MODULE = "synergy"

    @property
    def module_id(self) -> str:
        return "drug_synergy"

    @property
    def depends_on(self) -> tuple[str, ...]:
        return ("knowledge_graph",)

    def coverage_inputs(self) -> tuple[str, ...]:
        return ("genes", "drugs")

    def run(self, disease_id: str, **opts: Any) -> list:
        from med_research.pipeline.drug_synergy.engine import compute_synergy

        return compute_synergy(
            progress_callback=opts.get("progress_callback"),
            disease_id=disease_id,
            save=opts.get("save", True),
        )

    def report(
        self,
        results: list,
        disease_id: str,
        *,
        provenance: dict[str, Any] | None = None,
    ) -> Path:
        from med_research.pipeline.drug_synergy.report import generate_html_report

        report_path = generate_html_report(
            results,
            disease_id=disease_id,
            provenance=provenance,
        )
        return Path(report_path)

    def build_provenance(self, disease_id: str, **opts: Any) -> dict[str, Any]:
        return build_provenance(
            disease_id=disease_id,
            module=self.module_id,
            sources=["knowledge_graph"],
            cache_or_live="cache",
            scoring={"ranking": "composite_score"},
            **opts,
        )
