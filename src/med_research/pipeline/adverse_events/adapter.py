"""Adapter around ``adverse_events.profiler`` scoring and reporting."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from typing_extensions import Unpack

from med_research.pipeline.adapter_options import AdapterOptions
from med_research.pipeline.base import BasePipelineModule
from med_research.pipeline.provenance import build_provenance
from med_research.pipeline.registry import register_module
from med_research.pipeline.results import AdverseEventResults


@register_module
class AdverseEventsModule(BasePipelineModule[AdverseEventResults]):
    """Adapter around adverse-event safety profiling and HTML reports."""

    _COVERAGE_MODULE = "safety"

    @property
    def module_id(self) -> str:
        return "adverse_events"

    @property
    def depends_on(self) -> tuple[str, ...]:
        return ("knowledge_graph",)

    def coverage_inputs(self) -> tuple[str, ...]:
        return ("symptoms", "adverse_event_profile", "safety_risk")

    def run(self, disease_id: str, **opts: Unpack[AdapterOptions]) -> AdverseEventResults:
        from med_research.pipeline.adverse_events.profiler import score_all_drugs

        return score_all_drugs(
            progress_callback=opts.get("progress_callback"),
            disease_id=disease_id,
        )

    def report(
        self,
        results: AdverseEventResults,
        disease_id: str,
        *,
        provenance: dict | None = None,
    ) -> Path:
        from med_research.pipeline.adverse_events.report import generate_html_report

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
            sources=["fda_labels"],
            cache_or_live="cache",
            **extra,
        )
