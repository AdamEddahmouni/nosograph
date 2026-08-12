"""Registry bridge for web services and Celery tasks.

Dispatches pipeline work through the unified registry-backed execution and
reporting primitives instead of duplicating engine imports in each service.

Progress reporting uses a standard ``(step, current, total)`` callback that
bridges to the legacy ``(percent, message)`` format consumed by Celery and
WebSocket job streaming.
"""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import Any

from med_research.diseases.coverage import ModuleCoverage
from med_research.exceptions import ModuleNotAvailableError, PipelineExecutionError
from med_research.pipeline.base import PipelineRunResult
from med_research.pipeline.dispatch import (
    LegacyProgress,
    ProgressReporter,
    StandardProgress,
    standard_to_legacy,
)
from med_research.pipeline.gateway import pipeline_gateway
from med_research.pipeline.registry import list_modules, module_job_aliases
from med_research.web.config import USE_CACHE

# Re-export dispatch progress helpers for web services and tests.
__all__ = [
    "JOB_MODULE_IDS",
    "LegacyProgress",
    "ProgressReporter",
    "StandardProgress",
    "dispatch_sync_module",
    "execute_module",
    "make_progress_reporter",
    "report_module",
    "require_module_data",
    "require_runnable_coverage",
    "resolve_module_id",
    "run_all_pipeline",
    "run_module_job",
    "standard_to_legacy",
]

# Mirrors CLI ``run-all`` step lists (evidence/semantic modules excluded).
_RUN_ALL_CORE_STEPS: list[tuple[str, str | None]] = [
    ("Knowledge Graph", "knowledge_graph"),
    ("Drug Repurposing", "drug_repurposing"),
    ("Bioinformatics", None),
    ("Literature Mining", "literature_mining"),
    ("Virtual Screening", "virtual_screening"),
    ("Clinical Trials", "clinical_trials"),
    ("ML Predictor", "ml_predictor"),
    ("Drug Synergy", "drug_synergy"),
]
_RUN_ALL_FULL_STEPS: list[tuple[str, str | None]] = [
    ("Adverse Events", "adverse_events"),
    ("Network Pharmacology", "network_pharmacology"),
    ("Gene Expression", "gene_expression"),
    ("CAR-T Predictor", "car_t_predictor"),
    ("Biomarker Discovery", "biomarker_discovery"),
    ("Cross-Disease", "cross_disease"),
]
_BIOINFORMATICS_MODULE_IDS = ("gwas", "enrichment", "ppi")

# Compatibility export for existing Celery/web callers. The mapping is
# generated from the same registry catalog used by the system endpoint.
JOB_MODULE_IDS = module_job_aliases()

OptsMapper = Callable[[dict[str, Any], str], dict[str, Any]]


def _use_cache_from_opts(opts: dict[str, Any]) -> bool:
    if "use_cache" in opts:
        return bool(opts["use_cache"])
    return not opts.get("no_cache", False) and USE_CACHE


def _map_gwas_opts(opts: dict[str, Any], _disease_id: str) -> dict[str, Any]:
    return {
        "max_studies": opts.get("max_studies", 30),
        "use_cache": _use_cache_from_opts(opts),
        "resolve_snps": opts.get("resolve_snps", True),
    }


def _map_enrichment_opts(opts: dict[str, Any], _disease_id: str) -> dict[str, Any]:
    return {
        "untargeted_only": opts.get("untargeted_only", False),
        "use_cache": _use_cache_from_opts(opts),
    }


def _map_ppi_opts(opts: dict[str, Any], _disease_id: str) -> dict[str, Any]:
    return {
        "confidence": opts.get("confidence", 0.4),
        "expand_neighbors": opts.get("expand_neighbors", 0),
        "use_cache": _use_cache_from_opts(opts),
    }


def _map_literature_opts(opts: dict[str, Any], _disease_id: str) -> dict[str, Any]:
    mapped: dict[str, Any] = {
        "max_per_query": opts.get("max_articles", 30),
        "targeted_candidates": opts.get("targeted", False),
        "extract_content": opts.get("extract_content", False),
        "use_cache": _use_cache_from_opts(opts),
    }
    if opts.get("query"):
        mapped["query"] = opts["query"]
    if opts.get("sources"):
        mapped["sources"] = [item.strip() for item in opts["sources"].split(",")]
    if opts.get("queries"):
        mapped["queries"] = [item.strip() for item in opts["queries"].split(",")]
    if opts.get("email"):
        mapped["email"] = opts["email"]
    return mapped


def _map_screening_opts(opts: dict[str, Any], _disease_id: str) -> dict[str, Any]:
    mapped: dict[str, Any] = {
        "top_n": opts.get("top_n", 15),
        "use_vina": opts.get("use_vina", False),
    }
    if opts.get("gene_id"):
        mapped["gene"] = opts["gene_id"]
    if opts.get("operation"):
        mapped["operation"] = opts["operation"]
    return mapped


def _map_trials_opts(opts: dict[str, Any], disease_id: str) -> dict[str, Any]:
    query = opts.get("query", "")
    if not query or query == "lupus OR SLE":
        try:
            from med_research.diseases.base import Disease

            query = Disease(disease_id).get_trial_query()
        except ValueError:
            query = "lupus OR SLE"
    return {
        "query": query,
        "max_results": opts.get("max_trials", 100),
        "use_cache": _use_cache_from_opts(opts),
    }


def _map_ml_opts(opts: dict[str, Any], _disease_id: str) -> dict[str, Any]:
    return {"top": opts.get("top_n", 15)}


def _map_synergy_opts(opts: dict[str, Any], _disease_id: str) -> dict[str, Any]:
    return {"save": opts.get("save", True)}


def _map_repurposing_opts(opts: dict[str, Any], _disease_id: str) -> dict[str, Any]:
    mapped: dict[str, Any] = {}
    for key in ("gene_id", "untargeted_only", "save"):
        if key in opts:
            mapped[key] = opts[key]
    return mapped


def _map_semantic_opts(opts: dict[str, Any], _disease_id: str) -> dict[str, Any]:
    return {
        "query": opts.get("query", ""),
        "top": opts.get("top_k", opts.get("top", 20)),
    }


def _map_evidence_gather_opts(opts: dict[str, Any], _disease_id: str) -> dict[str, Any]:
    sources = opts.get("sources") or ""
    return {
        "query": opts.get("query", ""),
        "sources": [item.strip() for item in sources.split(",") if item.strip()],
        "max_per_source": opts.get("max_per_source", 20),
        "use_cache": opts.get("use_cache", True),
        "cross_reference": opts.get("cross_reference", True),
    }


def _map_llm_extractor_opts(opts: dict[str, Any], _disease_id: str) -> dict[str, Any]:
    mapped: dict[str, Any] = {
        "query": opts.get("query", ""),
        "sources": opts.get("sources") or [],
        "max_articles": opts.get("max_articles", 20),
        "use_cache": opts.get("use_cache", True),
    }
    model = opts.get("model")
    if model:
        mapped["model"] = model
    return mapped


def _map_evidence_monitor_opts(opts: dict[str, Any], _disease_id: str) -> dict[str, Any]:
    sources = opts.get("sources") or ""
    return {
        "sources": [item.strip() for item in sources.split(",") if item.strip()],
        "max_per_query": opts.get("max_per_query", 10),
        "diff": opts.get("diff", False),
    }


def _map_pass_through_opts(opts: dict[str, Any], _disease_id: str) -> dict[str, Any]:
    return dict(opts)


MODULE_OPTS_MAPPERS: dict[str, OptsMapper] = {
    "gwas": _map_gwas_opts,
    "enrichment": _map_enrichment_opts,
    "ppi": _map_ppi_opts,
    "literature_mining": _map_literature_opts,
    "virtual_screening": _map_screening_opts,
    "clinical_trials": _map_trials_opts,
    "ml_predictor": _map_ml_opts,
    "drug_synergy": _map_synergy_opts,
    "adverse_events": _map_pass_through_opts,
    "knowledge_graph": _map_pass_through_opts,
    "drug_repurposing": _map_repurposing_opts,
    "network_pharmacology": _map_pass_through_opts,
    "gene_expression": _map_pass_through_opts,
    "car_t_predictor": _map_pass_through_opts,
    "biomarker_discovery": _map_pass_through_opts,
    "cross_disease": _map_pass_through_opts,
    "semantic_search": _map_semantic_opts,
    "evidence_gather": _map_evidence_gather_opts,
    "llm_extractor": _map_llm_extractor_opts,
    "evidence_monitor": _map_evidence_monitor_opts,
    "evidence_workspace": _map_pass_through_opts,
}


def resolve_module_id(route_id: str) -> str:
    """Map a job route alias or module_id to a registered module identifier."""
    if route_id in JOB_MODULE_IDS:
        return JOB_MODULE_IDS[route_id]
    registered = list_modules()
    if route_id in registered:
        return route_id
    raise KeyError(
        f"Unknown job module '{route_id}'. Known routes: {', '.join(sorted(JOB_MODULE_IDS))}"
    )


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
) -> PipelineRunResult[Any]:
    """Run a registry module via the unified dispatch primitive."""
    return pipeline_gateway.execute(
        module_id,
        disease_id,
        export_html=export_html,
        progress_callback=progress_callback,
        **opts,
    )


def require_runnable_coverage(coverage: ModuleCoverage, module_id: str = "") -> None:
    """Raise :class:`ModuleNotAvailableError` when coverage blocks execution."""
    if coverage.is_runnable:
        return
    if coverage.limitations:
        detail = coverage.limitations[0]
    elif coverage.missing_inputs:
        detail = f"Required curated inputs are missing: {', '.join(coverage.missing_inputs)}."
    else:
        label = module_id or coverage.module
        detail = f"Module '{label}' is not available for disease '{coverage.disease_id}'."
    raise ModuleNotAvailableError(detail)


def require_module_data(result: PipelineRunResult[Any], module_id: str) -> Any:
    """Return dispatch data or raise :class:`ModuleNotAvailableError`."""
    if result.success:
        return result.data
    message = result.errors[0] if result.errors else f"Module '{module_id}' is not available"
    raise ModuleNotAvailableError(message)


def dispatch_sync_module(
    module_id: str,
    disease_id: str,
    *,
    export_html: bool = False,
    progress_callback: LegacyProgress | StandardProgress | None = None,
    **opts: Any,
) -> Any:
    """Sync web dispatch: ``execute_module()`` with HTTP 409 semantics on block."""
    result = execute_module(
        module_id,
        disease_id,
        export_html=export_html,
        progress_callback=progress_callback,
        **opts,
    )
    return require_module_data(result, module_id)


def report_module(
    module_id: str,
    results: Any,
    disease_id: str,
    **provenance_opts: Any,
) -> Path:
    """Render an HTML report through the centralized dispatch path."""
    return pipeline_gateway.report(module_id, results, disease_id, **provenance_opts)


def _kg_job_result(data: Any) -> dict[str, Any]:
    return {
        "nodes": data.number_of_nodes() if data is not None else 0,
        "edges": data.number_of_edges() if data is not None else 0,
        "status": "ready",
    }


def _single_drug_safety_result(drug_id: str, disease_id: str) -> Any:
    from med_research.pipeline.adverse_events.profiler import get_drug_profile
    from med_research.web.dependencies import safe_serialize

    profile = get_drug_profile(drug_id, disease_id=disease_id)
    if not profile:
        raise PipelineExecutionError(f"Drug '{drug_id}' not found")
    return safe_serialize(profile)


def _run_all_steps(*, full: bool, skip_ml: bool) -> list[tuple[str, str | None]]:
    steps = list(_RUN_ALL_CORE_STEPS)
    if full:
        steps.extend(_RUN_ALL_FULL_STEPS)
    if skip_ml:
        steps = [step for step in steps if step[1] != "ml_predictor"]
    return steps


def _steps_to_parallel_modules(steps: list[tuple[str, str | None]]) -> list[str]:
    modules: list[str] = []
    for _name, module_id in steps:
        if module_id is None:
            modules.extend(_BIOINFORMATICS_MODULE_IDS)
        else:
            modules.append(module_id)
    return modules


def _run_all_module_opts(module_id: str, disease_id: str, *, no_cache: bool) -> dict[str, Any]:
    opts: dict[str, Any] = {}
    if no_cache:
        opts["use_cache"] = False
    if module_id == "clinical_trials":
        try:
            from med_research.diseases.base import Disease

            opts["query"] = Disease(disease_id).get_trial_query()
        except ValueError:
            opts["query"] = "lupus OR SLE"
        opts["max_results"] = 20
    elif module_id == "literature_mining":
        opts["max_per_query"] = 20
    elif module_id in {"ml_predictor", "virtual_screening", "drug_synergy"}:
        opts["top"] = 10
    elif module_id == "adverse_events":
        opts["top"] = 15
    return opts


def _finalize_run_all_module(
    module_id: str,
    disease_id: str,
    result: PipelineRunResult[Any],
    report_paths: dict[str, str],
) -> None:
    if result.report_path is not None:
        report_paths[module_id] = str(result.report_path)
    if module_id == "knowledge_graph" and result.data is not None:
        from med_research.pipeline.knowledge_graph.builder import export_for_web

        export_for_web(result.data, disease_id=disease_id)


def run_all_pipeline(
    disease_id: str,
    *,
    full: bool = False,
    parallel: bool = False,
    skip_ml: bool = False,
    export_html: bool = False,
    no_cache: bool = False,
    progress_callback: LegacyProgress | StandardProgress | None = None,
) -> dict[str, Any]:
    """Orchestrate a full pipeline run via the DAG scheduler and ``execute_module()``."""
    from med_research.pipeline.scheduler import run_levels, validate_dag

    steps = _run_all_steps(full=full, skip_ml=skip_ml)
    completed: list[str] = []
    report_paths: dict[str, str] = {}
    errors: list[dict[str, str]] = []

    def _run_one(module_id: str) -> None:
        opts = _run_all_module_opts(module_id, disease_id, no_cache=no_cache)
        result = execute_module(
            module_id,
            disease_id,
            export_html=export_html,
            progress_callback=progress_callback,
            **opts,
        )
        if not result.success:
            message = result.errors[0] if result.errors else f"Module '{module_id}' failed"
            errors.append({"module_id": module_id, "error": message})
            raise ModuleNotAvailableError(message)
        _finalize_run_all_module(module_id, disease_id, result, report_paths)
        completed.append(module_id)

    if parallel:
        module_ids = _steps_to_parallel_modules(steps)
        levels = validate_dag(module_ids)
        for level in levels:
            run_levels([level], _run_one, parallel=True)
    else:
        for _name, module_id in steps:
            try:
                if module_id is None:
                    for sub_id in _BIOINFORMATICS_MODULE_IDS:
                        _run_one(sub_id)
                else:
                    _run_one(module_id)
            except ModuleNotAvailableError:
                continue

    return {
        "disease_id": disease_id,
        "modules_completed": completed,
        "report_paths": report_paths,
        "errors": errors,
        "status": "success" if not errors else "partial_failure",
    }


def run_module_job(
    module_id: str,
    disease_id: str = "sle",
    progress_callback: LegacyProgress | None = None,
    **opts: Any,
) -> Any:
    """Dispatch a Celery job through the unified execute_module primitive."""
    resolved = resolve_module_id(module_id)
    export_html = bool(opts.pop("export_html", False))

    if resolved == "adverse_events" and opts.get("drug_id"):
        return _single_drug_safety_result(opts["drug_id"], disease_id)

    mapper = MODULE_OPTS_MAPPERS.get(resolved, _map_pass_through_opts)
    mapped_opts = mapper(opts, disease_id)

    result = execute_module(
        resolved,
        disease_id,
        export_html=export_html,
        progress_callback=progress_callback,
        **mapped_opts,
    )

    if not result.success:
        message = result.errors[0] if result.errors else f"Module '{resolved}' failed"
        raise PipelineExecutionError(message)

    if resolved == "knowledge_graph":
        payload: Any = _kg_job_result(result.data)
    else:
        payload = result.data

    if export_html and result.report_path is not None:
        report_path = str(result.report_path)
        if isinstance(payload, dict):
            return {**payload, "report_path": report_path}
        return {"result": payload, "report_path": report_path}

    return payload
