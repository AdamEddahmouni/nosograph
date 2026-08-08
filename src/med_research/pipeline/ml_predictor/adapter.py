"""Registry adapter for the ML target predictor module."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from med_research.pipeline.base import BasePipelineModule
from med_research.pipeline.provenance import build_provenance
from med_research.pipeline.registry import register_module


@register_module
class MlPredictorModule(BasePipelineModule):
    """Adapter around ``ml_predictor.predictor`` training and reporting."""

    _COVERAGE_MODULE = "ml_predictor"

    @property
    def module_id(self) -> str:
        return "ml_predictor"

    @property
    def depends_on(self) -> tuple[str, ...]:
        return ("knowledge_graph",)

    def coverage_inputs(self) -> tuple[str, ...]:
        return ("genes", "relationships")

    def run(self, disease_id: str, **opts: Any) -> dict:
        from med_research.diseases.coverage import module_coverage
        from med_research.pipeline.knowledge_graph.builder import build_graph
        from med_research.pipeline.ml_predictor.predictor import train_and_predict

        coverage = module_coverage(
            disease_id, self._COVERAGE_MODULE, self.coverage_inputs()
        )
        if not coverage.is_runnable:
            return {"error": "blocked", "coverage": coverage.to_dict()}

        graph = build_graph(disease_id, progress_callback=opts.get("progress_callback"))
        return train_and_predict(
            graph,
            top_n=opts.get("top", 15),
            progress_callback=opts.get("progress_callback"),
        )

    def report(
        self,
        results: dict,
        disease_id: str,
        *,
        provenance: dict | None = None,
    ) -> Path:
        from med_research.pipeline.ml_predictor.report import generate_ml_report

        report_path = generate_ml_report(
            results,
            disease_id=disease_id,
            provenance=provenance,
        )
        return Path(report_path)

    def build_provenance(self, disease_id: str, **opts: Any) -> dict:
        return build_provenance(
            disease_id=disease_id,
            module=self.module_id,
            sources=["knowledge_graph"],
            cache_or_live=opts.get("cache_or_live", "cache"),
            scoring={"ranking": "druggability_score"},
            **{
                key: value
                for key, value in opts.items()
                if key not in {"cache_or_live"}
            },
        )
