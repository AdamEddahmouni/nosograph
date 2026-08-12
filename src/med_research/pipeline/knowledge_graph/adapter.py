"""Registry adapter for the knowledge graph builder."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import networkx as nx
from typing_extensions import Unpack

from med_research.pipeline.adapter_options import AdapterOptions
from med_research.pipeline.base import BasePipelineModule
from med_research.pipeline.provenance import ProvenanceMetadata, build_provenance
from med_research.pipeline.registry import register_module


@register_module
class KnowledgeGraphModule(BasePipelineModule[nx.MultiDiGraph]):
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

    def run(self, disease_id: str, **opts: Unpack[AdapterOptions]) -> nx.MultiDiGraph:
        from med_research.pipeline.knowledge_graph.builder import build_graph

        return build_graph(disease_id, progress_callback=opts.get("progress_callback"))

    def report(
        self,
        results: nx.MultiDiGraph,
        disease_id: str,
        *,
        provenance: dict | None = None,
    ) -> Path:
        from med_research.pipeline.knowledge_graph.builder import export_for_web

        output_path = Path(__file__).parent / "web" / f"graph_data_{disease_id}.json"
        export_for_web(results, str(output_path), disease_id=disease_id)
        return output_path

    def build_provenance(self, disease_id: str, **opts: Unpack[AdapterOptions]) -> ProvenanceMetadata:
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
            scoring={"ranking": "composite_score"},
            **extra,
        )
