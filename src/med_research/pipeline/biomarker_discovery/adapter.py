"""Adapter around ``biomarker_discovery.discover`` scoring and reporting."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from typing_extensions import Unpack

from med_research.pipeline.adapter_options import AdapterOptions
from med_research.pipeline.base import BasePipelineModule
from med_research.pipeline.provenance import build_provenance
from med_research.pipeline.registry import register_module
from med_research.pipeline.results import BiomarkerResults


@register_module
class BiomarkerDiscoveryModule(BasePipelineModule[BiomarkerResults]):
    """Adapter around cross-module biomarker discovery and HTML reports."""

    _COVERAGE_MODULE = "biomarkers"

    @property
    def module_id(self) -> str:
        return "biomarker_discovery"

    @property
    def depends_on(self) -> tuple[str, ...]:
        return (
            "knowledge_graph",
            "gene_expression",
            "car_t_predictor",
            "drug_repurposing",
            "adverse_events",
            "drug_synergy",
        )

    def coverage_inputs(self) -> tuple[str, ...]:
        return ("genes",)

    def run(self, disease_id: str, **opts: Unpack[AdapterOptions]) -> BiomarkerResults:
        from med_research.pipeline.biomarker_discovery.discover import (
            compute_biomarker_matrix,
        )

        return compute_biomarker_matrix(
            progress_callback=opts.get("progress_callback"),
            disease_id=disease_id,
            save=opts.get("save", True),
        )

    def report(
        self,
        results: BiomarkerResults,
        disease_id: str,
        *,
        provenance: dict | None = None,
    ) -> Path:
        from med_research.pipeline.biomarker_discovery.report import generate_html_report

        report_path = generate_html_report(
            results,
            disease_id=disease_id,
            provenance=provenance,
        )
        return Path(report_path)

    def build_provenance(self, disease_id: str, **opts: Unpack[AdapterOptions]) -> dict:
        extra: dict[str, Any] = {
            key: value
            for key, value in opts.items()
            if key not in {"sources", "cache_or_live"}
        }
        return build_provenance(
            disease_id=disease_id,
            module=self.module_id,
            sources=[
                "knowledge_graph",
                "gene_expression",
                "car_t_predictor",
                "drug_repurposing",
                "adverse_events",
                "drug_synergy",
            ],
            cache_or_live="cache",
            **extra,
        )
