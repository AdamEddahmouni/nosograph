"""Celery application and analysis tasks — with real-time progress reporting."""

from datetime import datetime, timezone
from typing import Any, Callable
from uuid import uuid4

from celery import Celery

from med_research.pipeline.progress import StandardProgress
from med_research.pipeline.registry import celery_task_routes, module_catalog
from med_research.web.config import CELERY_BROKER_URL, CELERY_RESULT_BACKEND

celery_app = Celery(
    "med_research",
    broker=CELERY_BROKER_URL,
    backend=CELERY_RESULT_BACKEND,
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
    task_time_limit=600,
    task_soft_time_limit=540,
    # Route every registered module task from the same catalog used by the
    # CLI and web job alias resolver. ``run_module`` remains the generic
    # compatibility task for callers that submit a module ID dynamically.
    task_routes={**celery_task_routes(), "run_module": {"queue": "pipeline"}},
    beat_schedule={
        "workspace-digest-dispatcher": {
            "task": "dispatch_workspace_digests",
            "schedule": 60.0,
        },
    },
)


def _make_progress(self: Any) -> Callable[[int, str], None]:
    """Return a legacy progress callback that emits Celery task state updates."""

    def report(percent: int, message: str) -> None:
        self.update_state(
            state="PROGRESS",
            meta={"percent": percent, "message": message},
        )

    return report


def _make_workspace_progress(self: Any) -> StandardProgress:
    """Return a ``(step, current, total)`` progress callback for workspace runs."""

    def report(step: str, current: int, total: int) -> None:
        percent = round(current * 100 / total) if total > 0 else 100
        self.update_state(
            state="PROGRESS",
            meta={"percent": percent, "message": step},
        )

    return report


def _dispatch_module(self: Any, route_id: str, disease_id: str = "sle", **opts: Any) -> Any:
    """Shared Celery dispatch path for registry-backed module jobs."""
    from med_research.web.services.registry_service import run_module_job

    return run_module_job(
        route_id,
        disease_id,
        progress_callback=_make_progress(self),
        **opts,
    )


# ── Generic module dispatch ─────────────────────────────────────────────────


@celery_app.task(bind=True, name="run_module")
def task_run_module(self: Any, module_id: str, disease_id: str = "sle", **opts: Any) -> Any:
    """Celery task: run any module through the registry dispatch path."""
    return _dispatch_module(self, module_id, disease_id, **opts)


@celery_app.task(bind=True, name="run_all")
def task_run_all(
    self: Any,
    disease_id: str = "sle",
    full: bool = False,
    parallel: bool = False,
    skip_ml: bool = False,
    export_html: bool = False,
    no_cache: bool = False,
) -> dict[str, Any]:
    """Celery task: orchestrate a full pipeline run via the DAG scheduler."""
    from med_research.web.services.registry_service import run_all_pipeline

    self.update_state(
        state="PROGRESS",
        meta={"percent": 0, "message": "Pipeline run accepted"},
    )
    return run_all_pipeline(
        disease_id,
        full=full,
        parallel=parallel,
        skip_ml=skip_ml,
        export_html=export_html,
        no_cache=no_cache,
        progress_callback=_make_progress(self),
    )


# ── Evidence-to-Hypothesis Workspace ───────────────────────────────────────


@celery_app.task(bind=True, name="run_workspace")
def task_run_workspace(
    self: Any,
    question: str,
    disease_id: str = "sle",
    sources: list[str] | tuple[str, ...] | str = ("pubmed", "clinical_trials"),
    date_from: str | None = None,
    date_to: str | None = None,
    candidate_type: str = "both",
    max_evidence: int = 50,
    enable_llm: bool = True,
    researcher_id: str = "anonymous",
    model: str | None = None,
) -> dict[str, Any]:
    """Run an evidence dossier with progress updates for the dashboard."""
    from med_research.pipeline.evidence_workspace.report import render_html
    from med_research.pipeline.evidence_workspace.schemas import ResearchRequest
    from med_research.pipeline.evidence_workspace.workspace import (
        run_workspace,
        validate_disease_contract,
    )
    from med_research.web.config import WORKSPACE_DB_PATH
    from med_research.web.services.workspace_store import WorkspaceRunStore

    request = ResearchRequest.model_validate(
        {
            "question": question,
            "disease_id": disease_id,
            "sources": sources,
            "date_from": date_from,
            "date_to": date_to,
            "candidate_type": candidate_type,
            "max_evidence": max_evidence,
            "enable_llm": enable_llm,
            "model": model,
        }
    )
    validate_disease_contract(request.disease_id)

    store = WorkspaceRunStore(WORKSPACE_DB_PATH)
    task_id = getattr(self.request, "id", None) or uuid4().hex
    run_id = f"ew-{task_id}"
    store.create_run(run_id, request, researcher_id=researcher_id)

    self.update_state(state="PROGRESS", meta={"percent": 1, "message": "Workspace job accepted"})
    try:
        workspace_options: dict[str, Any] = {
            "progress_callback": _make_workspace_progress(self),
        }
        if model is not None:
            workspace_options["model"] = model
        dossier = run_workspace(request, **workspace_options)
        dossier.run_id = run_id
        html = render_html(dossier)
        store.save_success(dossier, html)
    except (OSError, ValueError, TypeError, KeyError, RuntimeError) as exc:
        store.mark_failed(run_id, f"{type(exc).__name__}: {exc}")
        raise
    return {"dossier": dossier.model_dump(mode="json"), "html": html}


@celery_app.task(name="dispatch_workspace_digests")
def task_dispatch_workspace_digests() -> dict[str, object]:
    """Queue due researcher digests; Celery Beat invokes this every minute."""
    from med_research.web.config import WORKSPACE_DB_PATH
    from med_research.web.services.workspace_store import WorkspaceRunStore

    store = WorkspaceRunStore(WORKSPACE_DB_PATH)
    researcher_ids = store.due_weekly_digest_researchers(datetime.now(timezone.utc))
    for researcher_id in researcher_ids:
        task_dispatch_workspace_digest.delay(researcher_id)
    return {"queued": len(researcher_ids), "researcher_ids": researcher_ids}


@celery_app.task(
    bind=True,
    name="dispatch_workspace_digest",
    autoretry_for=(Exception,),
    retry_backoff=True,
    retry_backoff_max=3600,
    retry_jitter=True,
    max_retries=5,
)
def task_dispatch_workspace_digest(self: Any, researcher_id: str) -> dict[str, object]:
    """Deliver one researcher's digest with exponential retry on channel failures."""
    from med_research.web.config import WORKSPACE_DB_PATH
    from med_research.web.services.notifications import dispatch_weekly_digest
    from med_research.web.services.workspace_store import WorkspaceRunStore

    store = WorkspaceRunStore(WORKSPACE_DB_PATH)
    return dispatch_weekly_digest(
        store,
        researcher_id,
        raise_on_failure=True,
    )


# ── Bioinformatics tasks ────────────────────────────────────────────────────


@celery_app.task(bind=True, name="run_gwas")
def task_run_gwas(
    self: Any,
    max_studies: int = 30,
    no_cache: bool = False,
    disease_id: str = "sle",
    use_cache: bool | None = None,
    resolve_snps: bool | None = None,
) -> Any:
    """Celery task: Run GWAS catalog annotation with progress updates."""
    options: dict[str, Any] = {
        "max_studies": max_studies,
        "no_cache": no_cache,
    }
    if use_cache is not None:
        options["use_cache"] = use_cache
    if resolve_snps is not None:
        options["resolve_snps"] = resolve_snps
    return _dispatch_module(self, "gwas", disease_id, **options)


@celery_app.task(bind=True, name="run_enrichment")
def task_run_enrichment(
    self: Any,
    untargeted_only: bool = False,
    no_cache: bool = False,
    disease_id: str = "sle",
    use_cache: bool | None = None,
) -> Any:
    """Celery task: Run pathway enrichment analysis with progress updates."""
    options: dict[str, Any] = {
        "untargeted_only": untargeted_only,
        "no_cache": no_cache,
    }
    if use_cache is not None:
        options["use_cache"] = use_cache
    return _dispatch_module(self, "enrichment", disease_id, **options)


@celery_app.task(bind=True, name="run_ppi")
def task_run_ppi(
    self: Any,
    confidence: float = 0.4,
    no_cache: bool = False,
    disease_id: str = "sle",
    expand_neighbors: int | None = None,
    use_cache: bool | None = None,
) -> Any:
    """Celery task: Build PPI network and compute hub scores with progress updates."""
    options: dict[str, Any] = {
        "confidence": confidence,
        "no_cache": no_cache,
    }
    if expand_neighbors is not None:
        options["expand_neighbors"] = expand_neighbors
    if use_cache is not None:
        options["use_cache"] = use_cache
    return _dispatch_module(self, "ppi", disease_id, **options)


# ── Shared analysis tasks ─────────────────────────────────────────────────────


@celery_app.task(bind=True, name="run_literature")
def task_run_literature(
    self: Any,
    max_articles: int = 30,
    targeted: bool = False,
    no_cache: bool = False,
    disease_id: str = "sle",
    query: str | None = None,
    sources: str | None = None,
    queries: str | None = None,
    extract_content: bool | None = None,
    use_cache: bool | None = None,
    email: str | None = None,
) -> Any:
    """Celery task: Mine PubMed for disease articles with progress updates."""
    options: dict[str, Any] = {
        "max_articles": max_articles,
        "targeted": targeted,
        "no_cache": no_cache,
    }
    for name, value in (
        ("query", query),
        ("sources", sources),
        ("queries", queries),
        ("extract_content", extract_content),
        ("use_cache", use_cache),
        ("email", email),
    ):
        if value is not None:
            options[name] = value
    return _dispatch_module(self, "literature", disease_id, **options)


@celery_app.task(bind=True, name="run_screening")
def task_run_screening(
    self: Any,
    gene_id: str | None = None,
    top_n: int = 15,
    use_vina: bool = False,
    disease_id: str = "sle",
    operation: str | None = None,
) -> Any:
    """Celery task: Run virtual drug screening with progress updates."""
    options: dict[str, Any] = {
        "gene_id": gene_id,
        "top_n": top_n,
        "use_vina": use_vina,
    }
    if operation is not None:
        options["operation"] = operation
    return _dispatch_module(self, "screening", disease_id, **options)


@celery_app.task(bind=True, name="run_trials")
def task_run_trials(
    self: Any,
    max_trials: int = 100,
    query: str = "",
    no_cache: bool = False,
    disease_id: str = "sle",
    use_cache: bool | None = None,
) -> Any:
    """Celery task: Track disease-specific clinical trials with progress updates."""
    options: dict[str, Any] = {
        "max_trials": max_trials,
        "query": query,
        "no_cache": no_cache,
    }
    if use_cache is not None:
        options["use_cache"] = use_cache
    return _dispatch_module(self, "trials", disease_id, **options)


@celery_app.task(bind=True, name="run_ml")
def task_run_ml(self: Any, top_n: int = 15, no_shap: bool = False, disease_id: str = "sle") -> Any:
    """Celery task: Run ML target prediction with progress updates."""
    return _dispatch_module(
        self,
        "ml",
        disease_id,
        top_n=top_n,
        no_shap=no_shap,
    )


@celery_app.task(bind=True, name="run_synergy")
def task_run_synergy(
    self: Any,
    top_n: int = 20,
    disease_id: str = "sle",
    save: bool | None = None,
) -> Any:
    """Celery task: Run drug combination synergy prediction with progress updates."""
    options: dict[str, Any] = {"top_n": top_n}
    if save is not None:
        options["save"] = save
    return _dispatch_module(self, "synergy", disease_id, **options)


@celery_app.task(bind=True, name="run_safety")
def task_run_safety(self: Any, drug_id: str | None = None, disease_id: str = "sle") -> Any:
    """Celery task: Run adverse event safety profiling with progress updates."""
    return _dispatch_module(
        self,
        "safety",
        disease_id,
        drug_id=drug_id,
    )


# ── Expanded registry module tasks ──────────────────────────────────────────


@celery_app.task(bind=True, name="run_knowledge_graph")
def task_run_knowledge_graph(self: Any, disease_id: str = "sle") -> Any:
    """Celery task: Build the disease knowledge graph."""
    return _dispatch_module(self, "knowledge_graph", disease_id)


@celery_app.task(bind=True, name="run_drug_repurposing")
def task_run_drug_repurposing(
    self: Any,
    top_n: int = 15,
    gene_id: str | None = None,
    disease_id: str = "sle",
) -> Any:
    """Celery task: Score drug repurposing candidates."""
    return _dispatch_module(
        self,
        "drug_repurposing",
        disease_id,
        top_n=top_n,
        gene_id=gene_id,
    )


@celery_app.task(bind=True, name="run_network_pharmacology")
def task_run_network_pharmacology(self: Any, disease_id: str = "sle") -> Any:
    """Celery task: Run network pharmacology analysis."""
    return _dispatch_module(self, "network_pharmacology", disease_id)


@celery_app.task(bind=True, name="run_gene_expression")
def task_run_gene_expression(self: Any, top_n: int = 26, disease_id: str = "sle") -> Any:
    """Celery task: Run gene expression correlation analysis."""
    return _dispatch_module(self, "gene_expression", disease_id, top_n=top_n)


@celery_app.task(bind=True, name="run_car_t_predictor")
def task_run_car_t_predictor(self: Any, top_n: int = 35, disease_id: str = "sle") -> Any:
    """Celery task: Run CAR-T response prediction."""
    return _dispatch_module(self, "car_t_predictor", disease_id, top_n=top_n)


@celery_app.task(bind=True, name="run_biomarker_discovery")
def task_run_biomarker_discovery(self: Any, top_n: int = 35, disease_id: str = "sle") -> Any:
    """Celery task: Run biomarker discovery."""
    return _dispatch_module(self, "biomarker_discovery", disease_id, top_n=top_n)


@celery_app.task(bind=True, name="run_cross_disease")
def task_run_cross_disease(self: Any, disease_id: str = "sle") -> Any:
    """Celery task: Run cross-disease analysis."""
    return _dispatch_module(self, "cross_disease", disease_id)


@celery_app.task(bind=True, name="run_semantic_search")
def task_run_semantic_search(
    self: Any,
    query: str = "",
    top_k: int = 20,
    disease_id: str = "sle",
) -> Any:
    """Celery task: Run semantic literature search."""
    return _dispatch_module(
        self,
        "semantic_search",
        disease_id,
        query=query,
        top_k=top_k,
    )


@celery_app.task(bind=True, name="run_evidence_gather")
def task_run_evidence_gather(
    self: Any,
    query: str = "",
    disease_id: str = "sle",
    max_per_source: int = 20,
    use_cache: bool = True,
) -> Any:
    """Celery task: Gather evidence from external sources."""
    return _dispatch_module(
        self,
        "evidence_gather",
        disease_id,
        query=query,
        max_per_source=max_per_source,
        use_cache=use_cache,
    )


@celery_app.task(bind=True, name="run_llm_extractor")
def task_run_llm_extractor(
    self: Any,
    query: str = "",
    disease_id: str = "sle",
    max_articles: int = 20,
    use_cache: bool = True,
) -> Any:
    """Celery task: Run LLM evidence extraction."""
    return _dispatch_module(
        self,
        "llm_extractor",
        disease_id,
        query=query,
        max_articles=max_articles,
        use_cache=use_cache,
    )


@celery_app.task(bind=True, name="run_evidence_monitor")
def task_run_evidence_monitor(
    self: Any,
    disease_id: str = "sle",
    max_per_query: int = 10,
) -> Any:
    """Celery task: Capture an evidence monitor snapshot."""
    return _dispatch_module(
        self,
        "evidence_monitor",
        disease_id,
        max_per_query=max_per_query,
    )


def _make_catalog_task(module_id: str, task_name: str) -> Any:
    """Register a generic Celery task for modules without a custom wrapper."""

    @celery_app.task(bind=True, name=task_name)
    def run_registered_module(self: Any, disease_id: str = "sle", **opts: Any) -> Any:
        return _dispatch_module(self, module_id, disease_id, **opts)

    return run_registered_module


# Custom tasks above retain their public signatures; newly registered modules
# receive a working generic task automatically from the same catalog.
for _module_metadata in module_catalog():
    _task_name = _module_metadata["celery_task"]
    if _task_name not in celery_app.tasks:
        _make_catalog_task(_module_metadata["module_id"], _task_name)
