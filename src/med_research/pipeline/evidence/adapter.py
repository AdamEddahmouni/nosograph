"""BasePipelineModule adapters for evidence gatherer, extractor, and monitor."""

from __future__ import annotations

from pathlib import Path
from typing import cast

from typing_extensions import Unpack

from med_research.pipeline.adapter_options import AdapterOptions
from med_research.pipeline.base import BasePipelineModule
from med_research.pipeline.provenance import build_provenance
from med_research.pipeline.registry import register_module
from med_research.pipeline.results import (
    EvidenceExtractionResult,
    EvidenceGatherResult,
    EvidenceMonitorResult,
)

_DEFAULT_GATHER_SOURCES = [
    "pubmed",
    "preprints",
    "clinical_trials",
    "fda_labels",
    "patents",
]
_DEFAULT_EXTRACT_SOURCES = ["pubmed", "preprints", "clinical_trials"]
_DEFAULT_MONITOR_SOURCES = ["pubmed", "preprints", "clinical_trials"]


def _default_query(disease_id: str) -> str:
    """Return the first curated PubMed query for a disease."""
    from med_research.diseases.base import Disease

    disease = Disease(disease_id)
    queries = disease.config.get("PUBMED_QUERIES", [])
    if queries:
        return str(queries[0])
    return f"treatment targets {disease.get_display_name()}"


@register_module
class EvidenceGathererModule(BasePipelineModule[EvidenceGatherResult]):
    """Adapter around ``evidence.gatherer`` multi-source search."""

    _COVERAGE_MODULE = "evidence_gather"

    @property
    def module_id(self) -> str:
        return "evidence_gather"

    @property
    def depends_on(self) -> tuple[str, ...]:
        return ("knowledge_graph",)

    def coverage_inputs(self) -> tuple[str, ...]:
        return ("genes", "drugs", "pathways", "pubmed_queries")

    def run(self, disease_id: str, **opts: Unpack[AdapterOptions]) -> EvidenceGatherResult:
        from med_research.pipeline.evidence.gatherer import gather_evidence

        query = opts.get("query") or _default_query(disease_id)
        sources = opts.get("sources")
        if not isinstance(sources, list):
            sources = list(_DEFAULT_GATHER_SOURCES)
        return gather_evidence(
            query,
            sources=sources,
            max_per_source=opts.get("max_per_source", 20),
            use_cache=opts.get("use_cache", True),
            cross_reference=opts.get("cross_reference", True),
            disease_id=disease_id,
            progress_callback=opts.get("progress_callback"),
        )

    def report(
        self,
        results: EvidenceGatherResult,
        disease_id: str,
        *,
        provenance: dict | None = None,
    ) -> Path:
        from med_research.pipeline.evidence.gatherer_report import generate_html_report

        return Path(generate_html_report(cast(dict, results), provenance=provenance))

    def build_provenance(self, disease_id: str, **opts: Unpack[AdapterOptions]) -> dict:
        use_cache = opts.get("use_cache", True)
        sources = opts.get("sources") or [
            "pubmed",
            "preprints",
            "clinical_trials",
            "fda_labels",
            "patents",
        ]
        return build_provenance(
            disease_id=disease_id,
            module=self.module_id,
            sources=sources,
            query=opts.get("query") or _default_query(disease_id),
            cache_or_live=opts.get(
                "cache_or_live", "cache" if use_cache else "live"
            ),
        )


@register_module
class LLMExtractorModule(BasePipelineModule[EvidenceExtractionResult]):
    """Adapter around ``evidence.extractor`` LLM structured extraction."""

    _COVERAGE_MODULE = "evidence_extract"

    @property
    def module_id(self) -> str:
        return "llm_extractor"

    @property
    def depends_on(self) -> tuple[str, ...]:
        return ("knowledge_graph",)

    def coverage_inputs(self) -> tuple[str, ...]:
        return ()

    def run(self, disease_id: str, **opts: Unpack[AdapterOptions]) -> EvidenceExtractionResult:
        from med_research.pipeline.evidence.extractor import extract_all

        query = opts.get("query") or _default_query(disease_id)
        sources = opts.get("sources")
        if not isinstance(sources, list):
            sources = list(_DEFAULT_EXTRACT_SOURCES)
        model_raw = opts.get("model")
        model = model_raw if isinstance(model_raw, str) else ""
        return extract_all(
            query,
            sources=sources,
            max_articles=opts.get("max_articles", 20),
            model=model,
            use_cache=opts.get("use_cache", True),
            disease_id=disease_id,
            progress_callback=opts.get("progress_callback"),
        )

    def report(
        self,
        results: EvidenceExtractionResult,
        disease_id: str,
        *,
        provenance: dict | None = None,
    ) -> Path:
        from med_research.pipeline.evidence.extractor_report import generate_html_report

        return Path(generate_html_report(cast(dict, results), provenance=provenance))

    def build_provenance(self, disease_id: str, **opts: Unpack[AdapterOptions]) -> dict:
        use_cache = opts.get("use_cache", True)
        sources = opts.get("sources") or ["pubmed", "preprints", "clinical_trials"]
        return build_provenance(
            disease_id=disease_id,
            module=self.module_id,
            sources=sources,
            query=opts.get("query") or _default_query(disease_id),
            cache_or_live=opts.get(
                "cache_or_live", "cache" if use_cache else "live"
            ),
            model=opts.get("model"),
        )


@register_module
class EvidenceMonitorModule(BasePipelineModule[EvidenceMonitorResult]):
    """Adapter around ``evidence.monitor`` snapshot and diff workflows."""

    _COVERAGE_MODULE = "evidence_monitor"

    @property
    def module_id(self) -> str:
        return "evidence_monitor"

    @property
    def depends_on(self) -> tuple[str, ...]:
        return ("knowledge_graph",)

    def coverage_inputs(self) -> tuple[str, ...]:
        return ("genes", "pubmed_queries")

    def run(self, disease_id: str, **opts: Unpack[AdapterOptions]) -> EvidenceMonitorResult:
        from med_research.pipeline.evidence.monitor import (
            compare_snapshots,
            load_latest_snapshots,
            take_snapshot,
        )

        sources = opts.get("sources")
        if not isinstance(sources, list):
            sources = list(_DEFAULT_MONITOR_SOURCES)
        max_per_query = opts.get("max_per_query", 10)

        if opts.get("diff"):
            snapshots = load_latest_snapshots(2)
            if len(snapshots) < 2:
                prev = take_snapshot(
                    sources=sources,
                    max_per_query=max_per_query,
                    disease_id=disease_id,
                    progress_callback=opts.get("progress_callback"),
                )
                curr = take_snapshot(
                    sources=sources,
                    max_per_query=max_per_query,
                    disease_id=disease_id,
                    progress_callback=opts.get("progress_callback"),
                )
            else:
                prev, curr = snapshots[1], snapshots[0]
            diff = compare_snapshots(prev, curr)
            return {
                "diff": diff,
                "prev_snapshot": prev,
                "curr_snapshot": curr,
            }

        snapshot = take_snapshot(
            sources=sources,
            max_per_query=max_per_query,
            disease_id=disease_id,
            progress_callback=opts.get("progress_callback"),
        )
        return {"snapshot": snapshot}

    def report(
        self,
        results: EvidenceMonitorResult,
        disease_id: str,
        *,
        provenance: dict | None = None,
    ) -> Path:
        from med_research.pipeline.evidence.monitor import compare_snapshots
        from med_research.pipeline.evidence.monitor_report import generate_html_report

        if "diff" in results:
            report_path = generate_html_report(
                cast(dict, results["diff"]),
                cast(dict, results["prev_snapshot"]),
                cast(dict, results["curr_snapshot"]),
                provenance=provenance,
            )
        else:
            snapshot = cast(dict, results.get("snapshot", results))
            diff = compare_snapshots(snapshot, snapshot)
            report_path = generate_html_report(
                diff,
                snapshot,
                snapshot,
                provenance=provenance,
            )
        return Path(report_path)

    def build_provenance(self, disease_id: str, **opts: Unpack[AdapterOptions]) -> dict:
        sources = opts.get("sources") or ["pubmed", "preprints", "clinical_trials"]
        return build_provenance(
            disease_id=disease_id,
            module=self.module_id,
            sources=sources,
            cache_or_live=opts.get("cache_or_live", "cache"),
        )
