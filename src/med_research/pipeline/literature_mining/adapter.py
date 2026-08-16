"""Registry adapter for the literature mining engine."""

from __future__ import annotations

from pathlib import Path
from typing import Any, cast

from typing_extensions import Unpack

from med_research.pipeline.adapter_options import AdapterOptions
from med_research.pipeline.base import BasePipelineModule
from med_research.pipeline.provenance import ProvenanceMetadata, build_provenance
from med_research.pipeline.registry import register_module
from med_research.pipeline.results import LiteratureMiningResult


@register_module
class LiteratureMiningModule(BasePipelineModule[LiteratureMiningResult]):
    """Adapter around ``literature_mining.miner`` PubMed search and reporting."""

    _COVERAGE_MODULE = "literature"

    @property
    def module_id(self) -> str:
        return "literature_mining"

    @property
    def depends_on(self) -> tuple[str, ...]:
        return ("knowledge_graph",)

    def coverage_inputs(self) -> tuple[str, ...]:
        return ("genes", "drugs", "pathways", "pubmed_queries")

    def run(self, disease_id: str, **opts: Unpack[AdapterOptions]) -> LiteratureMiningResult:
        from med_research.diseases.base import Disease
        from med_research.pipeline.literature_mining.miner import (
            mine_literature,
            resolve_entrez_email,
        )

        use_cache = opts.get("use_cache", True)
        queries = opts.get("queries")
        if not isinstance(queries, list):
            queries = Disease(disease_id).config.get("PUBMED_QUERIES", [])
        email = opts.get("email")
        resolved_email = resolve_entrez_email(
            email if isinstance(email, str) else None,
            live=not use_cache,
        )
        results, entities, candidates, extraction_stats = mine_literature(
            queries=queries,
            max_per_query=opts.get("max_per_query", opts.get("max", 30)),
            email=resolved_email,
            use_cache=use_cache,
            targeted_candidates=opts.get("targeted_candidates", opts.get("targeted", False)),
            extract_content=opts.get("extract_content", opts.get("extract", False)),
            disease_id=disease_id,
            progress_callback=opts.get("progress_callback"),
        )
        return {
            "results": results,
            "entities": entities,
            "candidates": candidates,
            "extraction_stats": extraction_stats,
        }

    def report(
        self,
        results: LiteratureMiningResult,
        disease_id: str,
        *,
        provenance: dict | None = None,
    ) -> Path:
        from med_research.pipeline.literature_mining.report import generate_literature_report

        report_path = generate_literature_report(
            cast(dict, results["results"]),
            results["entities"],
            results["candidates"],
            disease_id=disease_id,
            provenance=provenance,
        )
        return Path(report_path)

    def build_provenance(
        self, disease_id: str, **opts: Unpack[AdapterOptions]
    ) -> ProvenanceMetadata:
        use_cache = opts.get("use_cache", True)
        extra: dict[str, Any] = {
            key: value
            for key, value in opts.items()
            if key not in {"sources", "query", "cache_or_live", "use_cache"}
        }
        return build_provenance(
            disease_id=disease_id,
            module=self.module_id,
            sources=["pubmed"],
            query=opts.get("query", ""),
            cache_or_live=opts.get("cache_or_live", "cache" if use_cache else "live"),
            **extra,
        )
