"""Job management API router — submit and track Celery tasks."""

import asyncio

from celery.result import AsyncResult
from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from web_api.dependencies import safe_serialize
from web_api.models import JobStatus, JobSubmitResponse
from web_api.tasks.analysis_tasks import (
    celery_app,
    task_run_enrichment,
    task_run_gwas,
    task_run_literature,
    task_run_ml,
    task_run_ppi,
    task_run_safety,
    task_run_screening,
    task_run_synergy,
    task_run_trials,
)

router = APIRouter(prefix="/api/jobs", tags=["Jobs"])


# ── Job submission endpoints ────────────────────────────────────────────────

@router.post("/gwas", response_model=JobSubmitResponse)
async def submit_gwas(max_studies: int = 30, no_cache: bool = False):
    """Submit a GWAS analysis job."""
    task = task_run_gwas.delay(max_studies=max_studies, no_cache=no_cache)
    return {"job_id": task.id, "status": "PENDING", "module": "gwas"}


@router.post("/enrichment", response_model=JobSubmitResponse)
async def submit_enrichment(untargeted_only: bool = False, no_cache: bool = False):
    """Submit a pathway enrichment job."""
    task = task_run_enrichment.delay(untargeted_only=untargeted_only, no_cache=no_cache)
    return {"job_id": task.id, "status": "PENDING", "module": "enrichment"}


@router.post("/ppi", response_model=JobSubmitResponse)
async def submit_ppi(confidence: float = 0.4, no_cache: bool = False):
    """Submit a PPI network analysis job."""
    task = task_run_ppi.delay(confidence=confidence, no_cache=no_cache)
    return {"job_id": task.id, "status": "PENDING", "module": "ppi"}


@router.post("/literature", response_model=JobSubmitResponse)
async def submit_literature(max_articles: int = 30, targeted: bool = False, no_cache: bool = False):
    """Submit a literature mining job."""
    task = task_run_literature.delay(max_articles=max_articles, targeted=targeted, no_cache=no_cache)
    return {"job_id": task.id, "status": "PENDING", "module": "literature"}


@router.post("/screening", response_model=JobSubmitResponse)
async def submit_screening(gene_id: str | None = None, top_n: int = 15, use_vina: bool = False):
    """Submit a virtual screening job."""
    task = task_run_screening.delay(gene_id=gene_id, top_n=top_n, use_vina=use_vina)
    return {"job_id": task.id, "status": "PENDING", "module": "screening"}


@router.post("/trials", response_model=JobSubmitResponse)
async def submit_trials(max_trials: int = 100, query: str = "lupus OR SLE",
                       no_cache: bool = False):
    """Submit a clinical trials tracking job."""
    task = task_run_trials.delay(max_trials=max_trials, query=query, no_cache=no_cache)
    return {"job_id": task.id, "status": "PENDING", "module": "trials"}


@router.post("/ml", response_model=JobSubmitResponse)
async def submit_ml(top_n: int = 15, no_shap: bool = False):
    """Submit an ML prediction job."""
    task = task_run_ml.delay(top_n=top_n, no_shap=no_shap)
    return {"job_id": task.id, "status": "PENDING", "module": "ml"}


@router.post("/synergy", response_model=JobSubmitResponse)
async def submit_synergy(top_n: int = 20):
    """Submit a drug combination synergy prediction job."""
    task = task_run_synergy.delay(top_n=top_n)
    return {"job_id": task.id, "status": "PENDING", "module": "synergy"}


@router.post("/safety", response_model=JobSubmitResponse)
async def submit_safety(drug_id: str | None = None):
    """Submit an adverse event safety profiling job."""
    task = task_run_safety.delay(drug_id=drug_id)
    return {"job_id": task.id, "status": "PENDING", "module": "safety"}


# ── Job status endpoint ─────────────────────────────────────────────────────

@router.get("/{job_id}", response_model=JobStatus)
async def get_job_status(job_id: str):
    """Get the status and result of a submitted job."""
    result = AsyncResult(job_id, app=celery_app)

    response = {
        "job_id": job_id,
        "status": result.state,
    }

    if result.state == "SUCCESS":
        response["result"] = result.result
    elif result.state == "FAILURE":
        response["error"] = str(result.info) if result.info else "Unknown error"
    elif result.state == "PROGRESS":
        response["progress"] = result.info if result.info else {}

    return response


# ── WebSocket job streaming ────────────────────────────────────────────────

@router.websocket("/{job_id}/ws")
async def job_websocket(websocket: WebSocket, job_id: str):
    """WebSocket endpoint that streams real-time job progress.

    Connects to Celery's AsyncResult and pushes state changes
    every 500ms until the job reaches a terminal state.
    """
    await websocket.accept()

    result = AsyncResult(job_id, app=celery_app)
    last_state = None
    poll_interval = 0.5  # 500ms
    max_polls = 1200  # 10 minutes total
    polls = 0

    try:
        while polls < max_polls:
            state = result.state

            # Detect orphaned job IDs early (3 polls / 1.5s without any backend data)
            if polls > 3 and state == "PENDING" and not result.info and not result.date_done:
                await websocket.send_json({
                    "job_id": job_id,
                    "status": "ERROR",
                    "error": "Job not found or expired",
                })
                break

            # Only send when state changes or on first poll
            if state != last_state:
                last_state = state
                message = {"job_id": job_id, "status": state}

                if state == "SUCCESS":
                    message["result"] = safe_serialize(result.result)
                    await websocket.send_json(message)
                    break
                elif state == "FAILURE":
                    message["error"] = str(result.info) if result.info else "Unknown error"
                    await websocket.send_json(message)
                    break
                elif state == "PROGRESS":
                    progress = result.info if result.info else {}
                    message["progress"] = safe_serialize(progress)
                    await websocket.send_json(message)
                else:
                    # PENDING, STARTED, RETRY, etc.
                    await websocket.send_json(message)

            await asyncio.sleep(poll_interval)
            polls += 1

        # Timeout
        if polls >= max_polls:
            await websocket.send_json({
                "job_id": job_id,
                "status": "TIMEOUT",
                "error": "Job exceeded 10-minute timeout",
            })

    except WebSocketDisconnect:
        pass
    except Exception as e:
        from contextlib import suppress
        with suppress(Exception):
            await websocket.send_json({
                "job_id": job_id,
                "status": "ERROR",
                "error": str(e),
            })



