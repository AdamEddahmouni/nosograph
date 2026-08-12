"""Registry adapter for the clinical trials tracker."""

from __future__ import annotations

from pathlib import Path
from typing import Any, cast

from typing_extensions import Unpack

from med_research.pipeline.adapter_options import AdapterOptions
from med_research.pipeline.base import BasePipelineModule
from med_research.pipeline.provenance import ProvenanceMetadata, build_provenance
from med_research.pipeline.registry import register_module
from med_research.pipeline.results import TrialRunResult


@register_module
class ClinicalTrialsModule(BasePipelineModule[TrialRunResult]):
    """Adapter around ``clinical_trials.tracker`` trial search and reporting."""

    _COVERAGE_MODULE = "clinical_trials"

    @property
    def module_id(self) -> str:
        return "clinical_trials"

    @property
    def depends_on(self) -> tuple[str, ...]:
        return ("knowledge_graph",)

    def coverage_inputs(self) -> tuple[str, ...]:
        return ("genes", "drugs", "trial_query")

    def run(self, disease_id: str, **opts: Unpack[AdapterOptions]) -> TrialRunResult:
        from med_research.pipeline.clinical_trials.tracker import track_trials

        return track_trials(
            query=opts.get("query", ""),
            max_results=opts.get("max_results", opts.get("max", 100)),
            use_cache=opts.get("use_cache", True),
            disease_id=disease_id,
            progress_callback=opts.get("progress_callback"),
        )

    def report(
        self,
        results: TrialRunResult,
        disease_id: str,
        *,
        provenance: dict | None = None,
    ) -> Path:
        from med_research.pipeline.clinical_trials.report import generate_ct_report

        report_path = generate_ct_report(
            cast(dict, results),
            disease_id=disease_id,
            provenance=provenance,
        )
        return Path(report_path)

    def build_provenance(self, disease_id: str, **opts: Unpack[AdapterOptions]) -> ProvenanceMetadata:
        from med_research.diseases.base import Disease

        use_cache = opts.get("use_cache", True)
        query = opts.get("query") or Disease(disease_id).get_trial_query()
        extra: dict[str, Any] = {
            key: value
            for key, value in opts.items()
            if key not in {"sources", "query", "cache_or_live", "use_cache"}
        }
        return build_provenance(
            disease_id=disease_id,
            module=self.module_id,
            sources=["clinicaltrials_gov"],
            query=query,
            cache_or_live=opts.get("cache_or_live", "cache" if use_cache else "live"),
            **extra,
        )
