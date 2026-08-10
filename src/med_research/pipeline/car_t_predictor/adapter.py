"""Adapter around ``car_t_predictor.predictor`` scoring and reporting."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from typing_extensions import Unpack

from med_research.pipeline.adapter_options import AdapterOptions
from med_research.pipeline.base import BasePipelineModule
from med_research.pipeline.provenance import build_provenance
from med_research.pipeline.registry import register_module
from med_research.pipeline.results import CarTResults


@register_module
class CarTPredictorModule(BasePipelineModule[CarTResults]):
    """Adapter around CAR-T gene suitability scoring and HTML reports."""

    _COVERAGE_MODULE = "car_t"

    @property
    def module_id(self) -> str:
        return "car_t_predictor"

    @property
    def depends_on(self) -> tuple[str, ...]:
        return ("knowledge_graph",)

    def coverage_inputs(self) -> tuple[str, ...]:
        return ("genes", "car_t_scores")

    def run(self, disease_id: str, **opts: Unpack[AdapterOptions]) -> CarTResults:
        from med_research.pipeline.car_t_predictor.predictor import compute_all_scores

        return compute_all_scores(
            progress_callback=opts.get("progress_callback"),
            disease_id=disease_id,
        )

    def report(
        self,
        results: CarTResults,
        disease_id: str,
        *,
        provenance: dict | None = None,
    ) -> Path:
        from med_research.pipeline.car_t_predictor.report import generate_html_report

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
            if key not in {"sources", "cache_or_live", "scoring"}
        }
        return build_provenance(
            disease_id=disease_id,
            module=self.module_id,
            sources=["knowledge_graph"],
            cache_or_live="cache",
            scoring={"ranking": "car_t_heuristic"},
            **extra,
        )
