"""Celery application and analysis tasks — with real-time progress reporting."""

import sys
from pathlib import Path

# Ensure project root is importable
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from celery import Celery

from web_api.config import CELERY_BROKER_URL, CELERY_RESULT_BACKEND

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


# ── Bioinformatics tasks ────────────────────────────────────────────────────

@celery_app.task(bind=True, name="run_gwas")
def task_run_gwas(self, max_studies: int = 30, no_cache: bool = False):
    """Celery task: Run GWAS catalog annotation with progress updates."""
    from web_api.services.bioinformatics_service import run_gwas

    return run_gwas(
        max_studies=max_studies,
        no_cache=no_cache,
        progress_callback=_make_progress(self),
    )


@celery_app.task(bind=True, name="run_enrichment")
def task_run_enrichment(self, untargeted_only: bool = False, no_cache: bool = False):
    """Celery task: Run pathway enrichment analysis with progress updates."""
    from web_api.services.bioinformatics_service import run_enrichment

    return run_enrichment(
        untargeted_only=untargeted_only,
        no_cache=no_cache,
        progress_callback=_make_progress(self),
    )


@celery_app.task(bind=True, name="run_ppi")
def task_run_ppi(self, confidence: float = 0.4, no_cache: bool = False):
    """Celery task: Build PPI network and compute hub scores with progress updates."""
    from web_api.services.bioinformatics_service import run_ppi

    return run_ppi(
        confidence=confidence,
        no_cache=no_cache,
        progress_callback=_make_progress(self),
    )


# ── Shared analysis tasks ───────────────────────────────────────────────────

@celery_app.task(bind=True, name="run_literature")
def task_run_literature(self, max_articles: int = 30, targeted: bool = False,
                        no_cache: bool = False):
    """Celery task: Mine PubMed for SLE articles with progress updates."""
    from web_api.services.shared_services import run_literature

    return run_literature(
        max_articles=max_articles,
        targeted=targeted,
        no_cache=no_cache,
        progress_callback=_make_progress(self),
    )


@celery_app.task(bind=True, name="run_screening")
def task_run_screening(self, gene_id: str | None = None, top_n: int = 15,
                       use_vina: bool = False):
    """Celery task: Run virtual drug screening with progress updates."""
    from web_api.services.shared_services import run_screening

    return run_screening(
        gene_id=gene_id,
        top_n=top_n,
        use_vina=use_vina,
        progress_callback=_make_progress(self),
    )


@celery_app.task(bind=True, name="run_trials")
def task_run_trials(self, max_trials: int = 100, query: str = "lupus OR SLE", no_cache: bool = False):
    """Celery task: Track clinical trials with progress updates."""
    from web_api.services.shared_services import run_trials

    return run_trials(
        max_trials=max_trials,
        query=query,
        no_cache=no_cache,
        progress_callback=_make_progress(self),
    )


@celery_app.task(bind=True, name="run_ml")
def task_run_ml(self, top_n: int = 15, no_shap: bool = False):
    """Celery task: Run ML target prediction with progress updates."""
    from web_api.services.shared_services import run_ml_prediction

    return run_ml_prediction(
        top_n=top_n,
        no_shap=no_shap,
        progress_callback=_make_progress(self),
    )


@celery_app.task(bind=True, name="run_synergy")
def task_run_synergy(self, top_n: int = 20):
    """Celery task: Run drug combination synergy prediction with progress updates."""
    from web_api.services.synergy_service import run_synergy

    return run_synergy(
        top_n=top_n,
        progress_callback=_make_progress(self),
    )


@celery_app.task(bind=True, name="run_safety")
def task_run_safety(self, drug_id: str | None = None):
    """Celery task: Run adverse event safety profiling with progress updates."""
    from web_api.services.adverse_events_service import run_safety_profiling

    return run_safety_profiling(
        drug_id=drug_id,
        progress_callback=_make_progress(self),
    )
