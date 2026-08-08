"""Registry adapter for the semantic literature search module."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from med_research.pipeline.base import BasePipelineModule
from med_research.pipeline.provenance import build_provenance
from med_research.pipeline.registry import register_module


def _default_query(disease_id: str) -> str:
    from med_research.diseases.base import Disease

    disease = Disease(disease_id)
    queries = disease.config.get("PUBMED_QUERIES", [])
    if queries:
        return str(queries[0])
    return f"treatment targets {disease.get_display_name()}"


@register_module
class SemanticSearchModule(BasePipelineModule):
    """Adapter around ``semantic_search.engine`` search and reporting."""

    _COVERAGE_MODULE = "semantic"

    @property
    def module_id(self) -> str:
        return "semantic_search"

    @property
    def depends_on(self) -> tuple[str, ...]:
        return ("knowledge_graph",)

    def coverage_inputs(self) -> tuple[str, ...]:
        return ("genes", "drugs", "pubmed_queries")

    def run(self, disease_id: str, **opts: Any) -> dict:
        from med_research.pipeline.semantic_search.engine import SemanticSearchEngine

        engine = SemanticSearchEngine(disease_id=disease_id)
        query = opts.get("query") or _default_query(disease_id)
        results = engine.search(
            query,
            top_k=opts.get("top", 20),
            progress_callback=opts.get("progress_callback"),
        )
        return {
            "results": results,
            "query": query,
            "indexed_count": engine.get_indexed_count(),
        }

    def report(
        self,
        results: dict,
        disease_id: str,
        *,
        provenance: dict | None = None,
    ) -> Path:
        from med_research.pipeline.semantic_search.report import generate_semantic_report

        report_path = generate_semantic_report(
            results["results"],
            results["query"],
            results["indexed_count"],
            disease_id=disease_id,
            provenance=provenance,
        )
        return Path(report_path)

    def build_provenance(self, disease_id: str, **opts: Any) -> dict:
        query = opts.get("query") or _default_query(disease_id)
        return build_provenance(
            disease_id=disease_id,
            module=self.module_id,
            sources=["pubmed"],
            query=query,
            cache_or_live=opts.get("cache_or_live", "cache"),
            **{
                key: value
                for key, value in opts.items()
                if key not in {"query", "cache_or_live"}
            },
        )
