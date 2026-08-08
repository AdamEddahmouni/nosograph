"""Registry adapter for the knowledge graph builder."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from med_research.pipeline.base import BasePipelineModule
from med_research.pipeline.provenance import build_provenance
from med_research.pipeline.registry import register_module


@register_module
class KnowledgeGraphModule(BasePipelineModule):
    """Adapter around ``knowledge_graph.builder`` graph construction and export."""

    _COVERAGE_MODULE = "kg"

    @property
    def module_id(self) -> str:
        return "knowledge_graph"

    @property
    def depends_on(self) -> tuple[str, ...]:
        return ()

    def coverage_inputs(self) -> tuple[str, ...]:
        return ("genes", "drugs", "pathways", "relationships")

    def run(self, disease_id: str, **opts: Any) -> Any:
        from med_research.diseases.coverage import module_coverage
        from med_research.pipeline.knowledge_graph.builder import build_graph

        coverage = module_coverage(
            disease_id, self._COVERAGE_MODULE, self.coverage_inputs()
        )
        if not coverage.is_runnable:
            return None

        return build_graph(disease_id)

    def report(
        self,
        results: Any,
        disease_id: str,
        *,
        provenance: dict | None = None,
    ) -> Path:
        from med_research.pipeline.knowledge_graph.builder import export_for_web

        if results is None:
            raise ValueError("Cannot export knowledge graph: module run was blocked")

        output_path = Path(__file__).parent / "web" / f"graph_data_{disease_id}.json"
        export_for_web(results, str(output_path), disease_id=disease_id)
        return output_path

    def build_provenance(self, disease_id: str, **opts: Any) -> dict:
        return build_provenance(
            disease_id=disease_id,
            module=self.module_id,
            sources=["knowledge_graph"],
            cache_or_live="cache",
            scoring={"ranking": "composite_score"},
            **opts,
        )
