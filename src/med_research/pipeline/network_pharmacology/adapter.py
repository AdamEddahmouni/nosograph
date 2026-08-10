"""Registry adapter for network pharmacology analysis."""

from __future__ import annotations

from pathlib import Path
from typing import Any, cast

from typing_extensions import Unpack

from med_research.pipeline.adapter_options import AdapterOptions
from med_research.pipeline.base import BasePipelineModule
from med_research.pipeline.provenance import build_provenance
from med_research.pipeline.registry import register_module
from med_research.pipeline.results import CentralityEntry, NetworkModuleResult


@register_module
class NetworkPharmacologyModule(BasePipelineModule[NetworkModuleResult]):
    """Adapter around ``network_pharmacology.analyzer`` metrics and reporting."""

    _COVERAGE_MODULE = "network_pharm"

    @property
    def module_id(self) -> str:
        return "network_pharmacology"

    @property
    def depends_on(self) -> tuple[str, ...]:
        return ("knowledge_graph",)

    def coverage_inputs(self) -> tuple[str, ...]:
        return ("genes", "relationships")

    def run(self, disease_id: str, **opts: Unpack[AdapterOptions]) -> NetworkModuleResult:
        from med_research.pipeline.network_pharmacology.analyzer import (
            compute_all_metrics,
            compute_centrality,
            compute_communities,
            load_graph,
        )

        operation = opts.get("operation")
        progress_callback = opts.get("progress_callback")
        graph = opts.get("graph") or load_graph(disease_id)

        if operation == "centrality":
            metric = opts.get("metric", "betweenness")
            top_n = opts.get("top_n", 15)
            all_centrality = compute_centrality(graph, progress_callback=progress_callback)
            scores = all_centrality.get(metric, {})
            sorted_nodes = sorted(scores.items(), key=lambda x: x[1], reverse=True)[:top_n]
            nodes: list[CentralityEntry] = [
                {
                    "node_id": node,
                    "label": graph.nodes[node].get("label", node),
                    "type": graph.nodes[node].get("type", "unknown"),
                    "score": round(score, 4),
                }
                for node, score in sorted_nodes
            ]
            return {"metric": metric, "nodes": nodes, "total_nodes": graph.number_of_nodes()}

        if operation == "communities":
            return cast(NetworkModuleResult, compute_communities(graph, progress_callback=progress_callback))

        return cast(
            NetworkModuleResult,
            compute_all_metrics(
                progress_callback=progress_callback,
                disease_id=disease_id,
            ),
        )

    def report(
        self,
        results: NetworkModuleResult,
        disease_id: str,
        *,
        provenance: dict | None = None,
    ) -> Path:
        from med_research.pipeline.network_pharmacology.report import (
            generate_html_report,
        )

        report_path = generate_html_report(
            cast(dict, results),
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
            scoring={"ranking": "composite_score"},
            **extra,
        )
