"""Registry bridge for web services and Celery tasks.

Dispatches pipeline work through ``get_module(module_id).run()`` / ``.report()``
or the unified ``execute_module()`` dispatch primitive instead of duplicating
engine imports in each service module.

Progress reporting uses a standard ``(step, current, total)`` callback that
bridges to the legacy ``(percent, message)`` format consumed by Celery and
WebSocket job streaming.
"""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import Any

from med_research.pipeline.dispatch import execute_module as _execute_module
from med_research.pipeline.registry import get_module, list_modules

# Standard: step label, units completed, total units.
StandardProgress = Callable[[str, int, int], None]
# Legacy: percent 0-100, human-readable message (Celery / WebSocket).
LegacyProgress = Callable[[int, str], None]

# Celery job route names → registry module_id (legacy aliases + module_ids).
JOB_MODULE_IDS: dict[str, str] = {
    "gwas": "gwas",
    "enrichment": "enrichment",
    "ppi": "ppi",
    "literature": "literature_mining",
    "screening": "virtual_screening",
    "trials": "clinical_trials",
    "ml": "ml_predictor",
    "synergy": "drug_synergy",
    "safety": "adverse_events",
    "kg": "knowledge_graph",
    "knowledge_graph": "knowledge_graph",
    "repurpose": "drug_repurposing",
    "drug_repurposing": "drug_repurposing",
    "network": "network_pharmacology",
    "network_pharmacology": "network_pharmacology",
    "expression": "gene_expression",
    "gene_expression": "gene_expression",
    "cart": "car_t_predictor",
    "car_t_predictor": "car_t_predictor",
    "biomarker": "biomarker_discovery",
    "biomarker_discovery": "biomarker_discovery",
    "cross_disease": "cross_disease",
    "semantic": "semantic_search",
    "semantic_search": "semantic_search",
    "evidence": "evidence_gather",
    "evidence_gather": "evidence_gather",
    "extractor": "llm_extractor",
    "llm_extractor": "llm_extractor",
    "monitor": "evidence_monitor",
    "evidence_monitor": "evidence_monitor",
    "workspace": "evidence_workspace",
    "evidence_workspace": "evidence_workspace",
}


def resolve_module_id(route_id: str) -> str:
    """Map a job route alias or module_id to a registered module identifier."""
    if route_id in JOB_MODULE_IDS:
        return JOB_MODULE_IDS[route_id]
    registered = list_modules()
    if route_id in registered:
        return route_id
    raise KeyError(
        f"Unknown job module '{route_id}'. "
        f"Known routes: {', '.join(sorted(JOB_MODULE_IDS))}"
    )


def standard_to_legacy(
    step: str,
    current: int,
    total: int,
    sink: LegacyProgress | None,
) -> None:
    """Convert a standard progress tick to legacy percent/message."""
    if sink is None:
        return
    if total <= 0:
        percent = 100 if current > 0 else 0
    else:
        percent = min(100, max(0, int(current / total * 100)))
    sink(percent, step)


class ProgressReporter:
    """Standard ``(step, current, total)`` callback backed by a legacy sink."""

    def __init__(self, sink: LegacyProgress | None = None) -> None:
        self._sink = sink

    def __call__(self, step: str, current: int, total: int) -> None:
        standard_to_legacy(step, current, total, self._sink)

    def legacy(self) -> LegacyProgress:
        """Return the underlying legacy callback for engines that expect it."""
        return self._sink or (lambda _p, _m: None)


def make_progress_reporter(sink: LegacyProgress | None) -> ProgressReporter:
    """Build a standard progress reporter from a legacy Celery/WebSocket sink."""
    return ProgressReporter(sink)


def execute_module(
    module_id: str,
    disease_id: str,
    *,
    export_html: bool = False,
    progress_callback: LegacyProgress | StandardProgress | None = None,
    **opts: Any,
) -> Any:
    """Run a registry module via the unified dispatch primitive."""
    return _execute_module(
        module_id,
        disease_id,
        export_html=export_html,
        progress_callback=progress_callback,
        **opts,
    )


def run_module(
    module_id: str,
    disease_id: str,
    *,
    progress_callback: LegacyProgress | StandardProgress | None = None,
    **opts: Any,
) -> Any:
    """Run a registry-backed module and return raw engine output."""
    module = get_module(module_id)
    if progress_callback is not None:
        # Engines still consume legacy (percent, message) callbacks.
        if _accepts_legacy(progress_callback):
            opts["progress_callback"] = progress_callback
        else:
            reporter = ProgressReporter(progress_callback)  # type: ignore[arg-type]
            opts["progress_callback"] = reporter.legacy()
    return module.run(disease_id, **opts)


def report_module(
    module_id: str,
    results: Any,
    disease_id: str,
    **provenance_opts: Any,
) -> Path:
    """Render an HTML report via the registry adapter."""
    module = get_module(module_id)
    provenance = module.build_provenance(disease_id, **provenance_opts)
    return module.report(results, disease_id, provenance=provenance)


def run_module_job(
    module_id: str,
    disease_id: str = "sle",
    progress_callback: LegacyProgress | None = None,
    **opts: Any,
) -> Any:
    """Dispatch a Celery job to the appropriate web service function."""
    resolved = resolve_module_id(module_id)

    if resolved == "gwas":
        from med_research.web.services.bioinformatics_service import run_gwas

        return run_gwas(
            max_studies=opts.get("max_studies", 30),
            no_cache=opts.get("no_cache", False),
            disease_id=disease_id,
            progress_callback=progress_callback,
        )
    if resolved == "enrichment":
        from med_research.web.services.bioinformatics_service import run_enrichment

        return run_enrichment(
            untargeted_only=opts.get("untargeted_only", False),
            no_cache=opts.get("no_cache", False),
            disease_id=disease_id,
            progress_callback=progress_callback,
        )
    if resolved == "ppi":
        from med_research.web.services.bioinformatics_service import run_ppi

        return run_ppi(
            confidence=opts.get("confidence", 0.4),
            no_cache=opts.get("no_cache", False),
            disease_id=disease_id,
            progress_callback=progress_callback,
        )
    if resolved == "literature_mining":
        from med_research.web.services.shared_services import run_literature

        return run_literature(
            max_articles=opts.get("max_articles", 30),
            targeted=opts.get("targeted", False),
            no_cache=opts.get("no_cache", False),
            disease_id=disease_id,
            progress_callback=progress_callback,
        )
    if resolved == "virtual_screening":
        from med_research.web.services.shared_services import run_screening

        return run_screening(
            gene_id=opts.get("gene_id"),
            top_n=opts.get("top_n", 15),
            use_vina=opts.get("use_vina", False),
            disease_id=disease_id,
            progress_callback=progress_callback,
        )
    if resolved == "clinical_trials":
        from med_research.web.services.shared_services import run_trials

        return run_trials(
            max_trials=opts.get("max_trials", 100),
            query=opts.get("query", ""),
            no_cache=opts.get("no_cache", False),
            disease_id=disease_id,
            progress_callback=progress_callback,
        )
    if resolved == "ml_predictor":
        from med_research.web.services.shared_services import run_ml_prediction

        return run_ml_prediction(
            top_n=opts.get("top_n", 15),
            no_shap=opts.get("no_shap", False),
            disease_id=disease_id,
            progress_callback=progress_callback,
        )
    if resolved == "drug_synergy":
        from med_research.web.services.synergy_service import run_synergy

        return run_synergy(
            top_n=opts.get("top_n", 20),
            disease_id=disease_id,
            progress_callback=progress_callback,
        )
    if resolved == "adverse_events":
        from med_research.web.services.adverse_events_service import run_safety_profiling

        return run_safety_profiling(
            drug_id=opts.get("drug_id"),
            disease_id=disease_id,
            progress_callback=progress_callback,
        )
    if resolved == "knowledge_graph":
        result = execute_module(
            "knowledge_graph",
            disease_id,
            progress_callback=progress_callback,
        )
        if not result.success:
            raise RuntimeError(result.errors[0] if result.errors else "Knowledge graph blocked")
        return {
            "nodes": result.data.number_of_nodes() if result.data is not None else 0,
            "edges": result.data.number_of_edges() if result.data is not None else 0,
            "status": "ready",
        }
    if resolved == "drug_repurposing":
        from med_research.web.services.repurpose_service import run_repurposing

        return run_repurposing(
            top_n=opts.get("top_n", 15),
            gene_id=opts.get("gene_id"),
            disease_id=disease_id,
        )
    if resolved == "network_pharmacology":
        return run_module(
            "network_pharmacology",
            disease_id,
            progress_callback=progress_callback,
        )
    if resolved == "gene_expression":
        from med_research.web.services.expression_service import run_correlation_analysis

        return run_correlation_analysis(
            top_n=opts.get("top_n", 26),
            disease_id=disease_id,
        )
    if resolved == "car_t_predictor":
        from med_research.web.services.car_t_service import run_cart_analysis

        return run_cart_analysis(
            top_n=opts.get("top_n", 35),
            disease_id=disease_id,
        )
    if resolved == "biomarker_discovery":
        from med_research.web.services.biomarker_service import run_biomarker_analysis

        return run_biomarker_analysis(
            top_n=opts.get("top_n", 35),
            disease_id=disease_id,
        )
    if resolved == "cross_disease":
        from med_research.web.services.cross_disease_service import run_cross_disease_analysis

        return run_cross_disease_analysis(disease_id=disease_id)
    if resolved == "semantic_search":
        from med_research.web.services.semantic_service import run_semantic_search

        return run_semantic_search(
            query=opts.get("query", ""),
            top_k=opts.get("top_k", opts.get("top", 20)),
            disease_id=disease_id,
        )
    if resolved == "evidence_gather":
        from med_research.web.services.evidence_service import run_evidence_gather

        return run_evidence_gather(
            query=opts.get("query", ""),
            sources=opts.get("sources") or [],
            max_per_source=opts.get("max_per_source", 20),
            use_cache=opts.get("use_cache", True),
            disease_id=disease_id,
        )
    if resolved == "llm_extractor":
        from med_research.web.services.extractor_service import run_llm_extraction

        return run_llm_extraction(
            query=opts.get("query", ""),
            sources=opts.get("sources") or [],
            max_articles=opts.get("max_articles", 20),
            model=str(opts.get("model") or ""),
            use_cache=opts.get("use_cache", True),
            disease_id=disease_id,
        )
    if resolved == "evidence_monitor":
        from med_research.web.services.monitor_service import run_snapshot

        return run_snapshot(
            sources=opts.get("sources") or [],
            max_per_query=opts.get("max_per_query", 10),
            disease_id=disease_id,
        )

    raise KeyError(f"No Celery handler registered for module '{resolved}'")


def _accepts_legacy(callback: LegacyProgress | StandardProgress) -> bool:
    """Heuristic: legacy callbacks are typed for two positional args."""
    import inspect

    try:
        sig = inspect.signature(callback)
        params = [
            p
            for p in sig.parameters.values()
            if p.default is inspect.Parameter.empty
            and p.kind in (inspect.Parameter.POSITIONAL_ONLY, inspect.Parameter.POSITIONAL_OR_KEYWORD)
        ]
        return len(params) == 2
    except (TypeError, ValueError):
        return True
