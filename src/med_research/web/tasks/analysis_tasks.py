"""Celery application and analysis tasks — with real-time progress reporting."""

import sys
from pathlib import Path
from uuid import uuid4

# Ensure project root is importable
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from celery import Celery

from med_research.web.config import CELERY_BROKER_URL, CELERY_RESULT_BACKEND

celery_app = Celery(
    "lupus_platform",
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
    task_time_limit=600,  # 10 min max per task
    task_soft_time_limit=540,
)


def _make_progress(self):
    """Return a progress callback that emits Celery task state updates."""

    def report(percent: int, message: str):
        self.update_state(
            state="PROGRESS",
            meta={"percent": percent, "message": message},
        )

    return report


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
    # Return only JSON-compatible values because Celery is configured with the
    # JSON result serializer and the browser consumes the same representation.
    return {"dossier": dossier.model_dump(mode="json"), "html": html}


# ── Bioinformatics tasks ────────────────────────────────────────────────────


@celery_app.task(bind=True, name="run_gwas")
def task_run_gwas(
    self, max_studies: int = 30, no_cache: bool = False, disease_id: str = "sle"
):
    """Celery task: Run GWAS catalog annotation with progress updates."""
    from med_research.web.services.bioinformatics_service import run_gwas

    return run_gwas(
        max_studies=max_studies,
        no_cache=no_cache,
        disease_id=disease_id,
        progress_callback=_make_progress(self),
    )


@celery_app.task(bind=True, name="run_enrichment")
def task_run_enrichment(
    self,
    untargeted_only: bool = False,
    no_cache: bool = False,
    disease_id: str = "sle",
):
    """Celery task: Run pathway enrichment analysis with progress updates."""
    from med_research.web.services.bioinformatics_service import run_enrichment

    return run_enrichment(
        untargeted_only=untargeted_only,
        no_cache=no_cache,
        disease_id=disease_id,
        progress_callback=_make_progress(self),
    )


@celery_app.task(bind=True, name="run_ppi")
def task_run_ppi(
    self, confidence: float = 0.4, no_cache: bool = False, disease_id: str = "sle"
):
    """Celery task: Build PPI network and compute hub scores with progress updates."""
    from med_research.web.services.bioinformatics_service import run_ppi

    return run_ppi(
        confidence=confidence,
        no_cache=no_cache,
        disease_id=disease_id,
        progress_callback=_make_progress(self),
    )


# ── Shared analysis tasks ───────────────────────────────────────────────────


@celery_app.task(bind=True, name="run_literature")
def task_run_literature(
    self,
    max_articles: int = 30,
    targeted: bool = False,
    no_cache: bool = False,
    disease_id: str = "sle",
):
    """Celery task: Mine PubMed for disease articles with progress updates."""
    from med_research.web.services.shared_services import run_literature

    return run_literature(
        max_articles=max_articles,
        targeted=targeted,
        no_cache=no_cache,
        disease_id=disease_id,
        progress_callback=_make_progress(self),
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
    from med_research.web.services.shared_services import run_screening

    return run_screening(
        gene_id=gene_id,
        top_n=top_n,
        use_vina=use_vina,
        disease_id=disease_id,
        progress_callback=_make_progress(self),
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
    from med_research.web.services.shared_services import run_trials

    return run_trials(
        max_trials=max_trials,
        query=query,
        no_cache=no_cache,
        disease_id=disease_id,
        progress_callback=_make_progress(self),
    )


@celery_app.task(bind=True, name="run_ml")
def task_run_ml(self, top_n: int = 15, no_shap: bool = False, disease_id: str = "sle"):
    """Celery task: Run ML target prediction with progress updates."""
    from med_research.web.services.shared_services import run_ml_prediction

    return run_ml_prediction(
        top_n=top_n,
        no_shap=no_shap,
        disease_id=disease_id,
        progress_callback=_make_progress(self),
    )


@celery_app.task(bind=True, name="run_synergy")
def task_run_synergy(self, top_n: int = 20, disease_id: str = "sle"):
    """Celery task: Run drug combination synergy prediction with progress updates."""
    from med_research.web.services.synergy_service import run_synergy

    return run_synergy(
        top_n=top_n,
        disease_id=disease_id,
        progress_callback=_make_progress(self),
    )


@celery_app.task(bind=True, name="run_safety")
def task_run_safety(self, drug_id: str | None = None, disease_id: str = "sle"):
    """Celery task: Run adverse event safety profiling with progress updates."""
    from med_research.web.services.adverse_events_service import run_safety_profiling

    return run_safety_profiling(
        drug_id=drug_id,
        disease_id=disease_id,
        progress_callback=_make_progress(self),
    )
