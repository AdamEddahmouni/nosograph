"""Celery application and analysis tasks — with real-time progress reporting."""

from uuid import uuid4

from celery import Celery

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
)


def _make_progress(self):
    """Return a legacy progress callback that emits Celery task state updates."""

    def report(percent: int, message: str):
        self.update_state(
            state="PROGRESS",
            meta={"percent": percent, "message": message},
        )

    return report


# ── Generic module dispatch ─────────────────────────────────────────────────


@celery_app.task(bind=True, name="run_module")
def task_run_module(self, module_id: str, disease_id: str = "sle", **opts):
    """Celery task: run any registry-backed module via the web service bridge."""
    from med_research.web.services.registry_service import run_module_job

    return run_module_job(
        module_id,
        disease_id,
        progress_callback=_make_progress(self),
        **opts,
    )


# ── Evidence-to-Hypothesis Workspace ───────────────────────────────────────


@celery_app.task(bind=True, name="run_workspace")
def task_run_workspace(
    self,
    question: str,
    disease_id: str = "sle",
    sources: list[str] | tuple[str, ...] | str = ("pubmed", "clinical_trials"),
    date_from: str | None = None,
    date_to: str | None = None,
    candidate_type: str = "both",
    max_evidence: int = 50,
    enable_llm: bool = True,
):
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
        }
    )
    validate_disease_contract(request.disease_id)

    store = WorkspaceRunStore(WORKSPACE_DB_PATH)
    task_id = getattr(self.request, "id", None) or uuid4().hex
    run_id = f"ew-{task_id}"
    store.create_run(run_id, request)

    self.update_state(state="PROGRESS", meta={"percent": 1, "message": "Workspace job accepted"})
    try:
        dossier = run_workspace(
            request,
            progress_callback=_make_progress(self),
        )
        dossier.run_id = run_id
        html = render_html(dossier)
        store.save_success(dossier, html)
    except Exception as exc:
        store.mark_failed(run_id, f"{type(exc).__name__}: {exc}")
        raise
    return {"dossier": dossier.model_dump(mode="json"), "html": html}


# ── Bioinformatics tasks ────────────────────────────────────────────────────


@celery_app.task(bind=True, name="run_gwas")
def task_run_gwas(
    self, max_studies: int = 30, no_cache: bool = False, disease_id: str = "sle"
):
    """Celery task: Run GWAS catalog annotation with progress updates."""
    return task_run_module(
        self,
        "gwas",
        disease_id,
        max_studies=max_studies,
        no_cache=no_cache,
    )


@celery_app.task(bind=True, name="run_enrichment")
def task_run_enrichment(
    self,
    untargeted_only: bool = False,
    no_cache: bool = False,
    disease_id: str = "sle",
):
    """Celery task: Run pathway enrichment analysis with progress updates."""
    return task_run_module(
        self,
        "enrichment",
        disease_id,
        untargeted_only=untargeted_only,
        no_cache=no_cache,
    )


@celery_app.task(bind=True, name="run_ppi")
def task_run_ppi(
    self, confidence: float = 0.4, no_cache: bool = False, disease_id: str = "sle"
):
    """Celery task: Build PPI network and compute hub scores with progress updates."""
    return task_run_module(
        self,
        "ppi",
        disease_id,
        confidence=confidence,
        no_cache=no_cache,
    )


# ── Shared analysis tasks ─────────────────────────────────────────────────────


@celery_app.task(bind=True, name="run_literature")
def task_run_literature(
    self,
    max_articles: int = 30,
    targeted: bool = False,
    no_cache: bool = False,
    disease_id: str = "sle",
):
    """Celery task: Mine PubMed for disease articles with progress updates."""
    return task_run_module(
        self,
        "literature",
        disease_id,
        max_articles=max_articles,
        targeted=targeted,
        no_cache=no_cache,
    )


@celery_app.task(bind=True, name="run_screening")
def task_run_screening(
    self,
    gene_id: str | None = None,
    top_n: int = 15,
    use_vina: bool = False,
    disease_id: str = "sle",
):
    """Celery task: Run virtual drug screening with progress updates."""
    return task_run_module(
        self,
        "screening",
        disease_id,
        gene_id=gene_id,
        top_n=top_n,
        use_vina=use_vina,
    )


@celery_app.task(bind=True, name="run_trials")
def task_run_trials(
    self,
    max_trials: int = 100,
    query: str = "",
    no_cache: bool = False,
    disease_id: str = "sle",
):
    """Celery task: Track disease-specific clinical trials with progress updates."""
    return task_run_module(
        self,
        "trials",
        disease_id,
        max_trials=max_trials,
        query=query,
        no_cache=no_cache,
    )


@celery_app.task(bind=True, name="run_ml")
def task_run_ml(self, top_n: int = 15, no_shap: bool = False, disease_id: str = "sle"):
    """Celery task: Run ML target prediction with progress updates."""
    return task_run_module(
        self,
        "ml",
        disease_id,
        top_n=top_n,
        no_shap=no_shap,
    )


@celery_app.task(bind=True, name="run_synergy")
def task_run_synergy(self, top_n: int = 20, disease_id: str = "sle"):
    """Celery task: Run drug combination synergy prediction with progress updates."""
    return task_run_module(
        self,
        "synergy",
        disease_id,
        top_n=top_n,
    )


@celery_app.task(bind=True, name="run_safety")
def task_run_safety(self, drug_id: str | None = None, disease_id: str = "sle"):
    """Celery task: Run adverse event safety profiling with progress updates."""
    return task_run_module(
        self,
        "safety",
        disease_id,
        drug_id=drug_id,
    )


# ── Expanded registry module tasks ──────────────────────────────────────────


@celery_app.task(bind=True, name="run_knowledge_graph")
def task_run_knowledge_graph(self, disease_id: str = "sle"):
    """Celery task: Build the disease knowledge graph."""
    return task_run_module(self, "knowledge_graph", disease_id)


@celery_app.task(bind=True, name="run_drug_repurposing")
def task_run_drug_repurposing(
    self,
    top_n: int = 15,
    gene_id: str | None = None,
    disease_id: str = "sle",
):
    """Celery task: Score drug repurposing candidates."""
    return task_run_module(
        self,
        "drug_repurposing",
        disease_id,
        top_n=top_n,
        gene_id=gene_id,
    )


@celery_app.task(bind=True, name="run_network_pharmacology")
def task_run_network_pharmacology(self, disease_id: str = "sle"):
    """Celery task: Run network pharmacology analysis."""
    return task_run_module(self, "network_pharmacology", disease_id)


@celery_app.task(bind=True, name="run_gene_expression")
def task_run_gene_expression(self, top_n: int = 26, disease_id: str = "sle"):
    """Celery task: Run gene expression correlation analysis."""
    return task_run_module(self, "gene_expression", disease_id, top_n=top_n)


@celery_app.task(bind=True, name="run_car_t_predictor")
def task_run_car_t_predictor(self, top_n: int = 35, disease_id: str = "sle"):
    """Celery task: Run CAR-T response prediction."""
    return task_run_module(self, "car_t_predictor", disease_id, top_n=top_n)


@celery_app.task(bind=True, name="run_biomarker_discovery")
def task_run_biomarker_discovery(self, top_n: int = 35, disease_id: str = "sle"):
    """Celery task: Run biomarker discovery."""
    return task_run_module(self, "biomarker_discovery", disease_id, top_n=top_n)


@celery_app.task(bind=True, name="run_cross_disease")
def task_run_cross_disease(self, disease_id: str = "sle"):
    """Celery task: Run cross-disease analysis."""
    return task_run_module(self, "cross_disease", disease_id)


@celery_app.task(bind=True, name="run_semantic_search")
def task_run_semantic_search(
    self,
    query: str = "",
    top_k: int = 20,
    disease_id: str = "sle",
):
    """Celery task: Run semantic literature search."""
    return task_run_module(
        self,
        "semantic_search",
        disease_id,
        query=query,
        top_k=top_k,
    )


@celery_app.task(bind=True, name="run_evidence_gather")
def task_run_evidence_gather(
    self,
    query: str = "",
    disease_id: str = "sle",
    max_per_source: int = 20,
    use_cache: bool = True,
):
    """Celery task: Gather evidence from external sources."""
    return task_run_module(
        self,
        "evidence_gather",
        disease_id,
        query=query,
        max_per_source=max_per_source,
        use_cache=use_cache,
    )


@celery_app.task(bind=True, name="run_llm_extractor")
def task_run_llm_extractor(
    self,
    query: str = "",
    disease_id: str = "sle",
    max_articles: int = 20,
    use_cache: bool = True,
):
    """Celery task: Run LLM evidence extraction."""
    return task_run_module(
        self,
        "llm_extractor",
        disease_id,
        query=query,
        max_articles=max_articles,
        use_cache=use_cache,
    )


@celery_app.task(bind=True, name="run_evidence_monitor")
def task_run_evidence_monitor(
    self,
    disease_id: str = "sle",
    max_per_query: int = 10,
):
    """Celery task: Capture an evidence monitor snapshot."""
    return task_run_module(
        self,
        "evidence_monitor",
        disease_id,
        max_per_query=max_per_query,
    )
