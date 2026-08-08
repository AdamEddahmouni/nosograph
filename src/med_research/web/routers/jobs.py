"""Job management API router — submit and track Celery tasks."""

import asyncio
import json
import logging
from typing import Annotated, Any
from uuid import UUID

from celery.result import AsyncResult
from fastapi import APIRouter, Depends, HTTPException, Request, WebSocket, WebSocketDisconnect
from pydantic import ValidationError

from med_research.pipeline.evidence_workspace.schemas import ResearchRequest
from med_research.web.dependencies import safe_serialize
from med_research.web.identity import DEFAULT_RESEARCHER_ID, get_researcher_id
from med_research.web.models import JobStatus, JobSubmitResponse
from med_research.web.models.jobs import GenericModuleJobRequest, RunAllJobRequest
from med_research.web.services.registry_service import resolve_module_id
from med_research.web.tasks.analysis_tasks import (
    celery_app,
    task_run_all,
    task_run_enrichment,
    task_run_gwas,
    task_run_literature,
    task_run_ml,
    task_run_module,
    task_run_ppi,
    task_run_safety,
    task_run_screening,
    task_run_synergy,
    task_run_trials,
    task_run_workspace,
)

router = APIRouter(prefix="/api/jobs", tags=["Jobs"])
logger = logging.getLogger(__name__)


def _celery_backend_errors() -> tuple[type[BaseException], ...]:
    """Exception types raised when the Celery result backend is unavailable."""
    errors: list[type[BaseException]] = [AttributeError, OSError, ConnectionError]
    try:
        from celery.exceptions import BackendError

        errors.append(BackendError)
    except ImportError:
        pass
    try:
        from kombu.exceptions import OperationalError

        errors.append(OperationalError)
    except ImportError:
        pass
    try:
        from redis.exceptions import ConnectionError as RedisConnectionError

        errors.append(RedisConnectionError)
    except ImportError:
        pass
    return tuple(errors)


def _parse_run_all_request(request: Request) -> RunAllJobRequest:
    """Parse and validate run-all job query parameters."""
    try:
        return RunAllJobRequest.model_validate(dict(request.query_params))
    except ValidationError as exc:
        raise HTTPException(status_code=422, detail=json.loads(exc.json())) from exc


def _parse_generic_job_request(request: Request) -> GenericModuleJobRequest:
    """Parse and validate generic job query parameters."""
    try:
        return GenericModuleJobRequest.model_validate(dict(request.query_params))
    except ValidationError as exc:
        raise HTTPException(status_code=422, detail=json.loads(exc.json())) from exc


def _validate_job_id(job_id: str) -> str:
    """Ensure job IDs match the Celery UUID format."""
    try:
        UUID(job_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="Invalid job_id format") from exc
    return job_id


def _safe_result_state(result: AsyncResult) -> str | None:
    """Return Celery task state, or None when the result backend is unavailable."""
    try:
        state = result.state
        return str(state) if state is not None else None
    except _celery_backend_errors() as exc:
        logger.warning("Celery result backend unavailable: %s", exc)
        return None


# ── Job submission endpoints ────────────────────────────────────────────────


@router.post("/workspace", response_model=JobSubmitResponse)
async def submit_workspace(
    payload: ResearchRequest, request: Request = None  # type: ignore[assignment]
) -> dict[str, Any]:
    """Submit a Workspace run with the server-derived researcher principal."""
    try:
        task_payload = payload.model_dump(mode="json")
    except TypeError:
        task_payload = payload.model_dump()
    task_payload["researcher_id"] = (
        get_researcher_id(request) if request is not None else DEFAULT_RESEARCHER_ID
    )
    task = task_run_workspace.delay(**task_payload)
    return {"job_id": task.id, "status": "PENDING", "module": "workspace"}


@router.post("/gwas", response_model=JobSubmitResponse)
async def submit_gwas(
    max_studies: int = 30, no_cache: bool = False, disease_id: str = "sle"
) -> dict[str, Any]:
    """Submit a disease-specific GWAS analysis job."""
    task = task_run_gwas.delay(
        max_studies=max_studies, no_cache=no_cache, disease_id=disease_id
    )
    return {"job_id": task.id, "status": "PENDING", "module": "gwas"}


@router.post("/enrichment", response_model=JobSubmitResponse)
async def submit_enrichment(
    untargeted_only: bool = False,
    no_cache: bool = False,
    disease_id: str = "sle",
) -> dict[str, Any]:
    """Submit a disease-specific pathway enrichment job."""
    task = task_run_enrichment.delay(
        untargeted_only=untargeted_only,
        no_cache=no_cache,
        disease_id=disease_id,
    )
    return {"job_id": task.id, "status": "PENDING", "module": "enrichment"}


@router.post("/ppi", response_model=JobSubmitResponse)
async def submit_ppi(
    confidence: float = 0.4,
    no_cache: bool = False,
    disease_id: str = "sle",
) -> dict[str, Any]:
    """Submit a disease-specific PPI network analysis job."""
    task = task_run_ppi.delay(
        confidence=confidence, no_cache=no_cache, disease_id=disease_id
    )
    return {"job_id": task.id, "status": "PENDING", "module": "ppi"}


@router.post("/literature", response_model=JobSubmitResponse)
async def submit_literature(
    max_articles: int = 30,
    targeted: bool = False,
    no_cache: bool = False,
    disease_id: str = "sle",
) -> dict[str, Any]:
    """Submit a disease-specific literature mining job."""
    task = task_run_literature.delay(
        max_articles=max_articles,
        targeted=targeted,
        no_cache=no_cache,
        disease_id=disease_id,
    )
    return {"job_id": task.id, "status": "PENDING", "module": "literature"}


@router.post("/screening", response_model=JobSubmitResponse)
async def submit_screening(
    gene_id: str | None = None, top_n: int = 15, use_vina: bool = False, disease_id: str = "sle"
) -> dict[str, Any]:
    """Submit a virtual screening job."""
    task = task_run_screening.delay(
        gene_id=gene_id, top_n=top_n, use_vina=use_vina, disease_id=disease_id
    )
    return {"job_id": task.id, "status": "PENDING", "module": "screening"}


@router.post("/trials", response_model=JobSubmitResponse)
async def submit_trials(
    max_trials: int = 100,
    query: str = "",
    no_cache: bool = False,
    disease_id: str = "sle",
) -> dict[str, Any]:
    """Submit a disease-specific clinical trials tracking job."""
    task = task_run_trials.delay(
        max_trials=max_trials,
        query=query,
        no_cache=no_cache,
        disease_id=disease_id,
    )
    return {"job_id": task.id, "status": "PENDING", "module": "trials"}


@router.post("/ml", response_model=JobSubmitResponse)
async def submit_ml(top_n: int = 15, no_shap: bool = False, disease_id: str = "sle") -> dict[str, Any]:
    """Submit an ML prediction job."""
    task = task_run_ml.delay(top_n=top_n, no_shap=no_shap, disease_id=disease_id)
    return {"job_id": task.id, "status": "PENDING", "module": "ml"}


@router.post("/synergy", response_model=JobSubmitResponse)
async def submit_synergy(top_n: int = 20, disease_id: str = "sle") -> dict[str, Any]:
    """Submit a drug combination synergy prediction job."""
    task = task_run_synergy.delay(top_n=top_n, disease_id=disease_id)
    return {"job_id": task.id, "status": "PENDING", "module": "synergy"}


@router.post("/safety", response_model=JobSubmitResponse)
async def submit_safety(drug_id: str | None = None, disease_id: str = "sle") -> dict[str, Any]:
    """Submit an adverse event safety profiling job."""
    task = task_run_safety.delay(drug_id=drug_id, disease_id=disease_id)
    return {"job_id": task.id, "status": "PENDING", "module": "safety"}


@router.post("/run-all", response_model=JobSubmitResponse)
async def submit_run_all(
    job: Annotated[RunAllJobRequest, Depends(_parse_run_all_request)],
) -> dict[str, Any]:
    """Submit a full pipeline orchestration job (mirrors CLI ``run-all``)."""
    task = task_run_all.delay(job.disease_id, **job.to_task_opts())
    return {"job_id": task.id, "status": "PENDING", "module": "run-all"}


@router.post("/{module_id}", response_model=JobSubmitResponse)
async def submit_module_job(
    module_id: str,
    job: Annotated[GenericModuleJobRequest, Depends(_parse_generic_job_request)],
) -> dict[str, Any]:
    """Submit any registry-backed module as an asynchronous Celery job."""
    try:
        resolved = resolve_module_id(module_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    task = task_run_module.delay(resolved, job.disease_id, **job.to_task_opts())
    return {"job_id": task.id, "status": "PENDING", "module": module_id}


# ── Job status endpoint ─────────────────────────────────────────────────────


@router.get("/{job_id}", response_model=JobStatus)
async def get_job_status(job_id: str) -> dict[str, Any]:
    """Get the status and result of a submitted job."""
    _validate_job_id(job_id)
    result = AsyncResult(job_id, app=celery_app)

    response = {
        "job_id": job_id,
        "status": _safe_result_state(result) or "PENDING",
    }

    state = response["status"]
    if state == "SUCCESS":
        response["result"] = result.result
    elif state == "FAILURE":
        response["error"] = str(result.info) if result.info else "Unknown error"
    elif state == "PROGRESS":
        response["progress"] = result.info if result.info else {}

    return response


# ── WebSocket job streaming ────────────────────────────────────────────────


@router.websocket("/{job_id}/ws")
async def job_websocket(websocket: WebSocket, job_id: str) -> None:
    """WebSocket endpoint that streams real-time job progress.

    Connects to Celery's AsyncResult and pushes state changes
    every 500ms until the job reaches a terminal state.
    """
    try:
        UUID(job_id)
    except ValueError:
        await websocket.close(code=1008, reason="Invalid job_id format")
        return

    await websocket.accept()

    result = AsyncResult(job_id, app=celery_app)
    last_state = None
    poll_interval = 0.5  # 500ms
    max_polls = 1200  # 10 minutes total
    polls = 0

    try:
        while polls < max_polls:
            state = _safe_result_state(result)
            if state is None:
                await websocket.send_json(
                    {
                        "job_id": job_id,
                        "status": "ERROR",
                        "error": "Job backend unavailable",
                    }
                )
                break

            # Detect orphaned job IDs early (3 polls / 1.5s without any backend data)
            if polls > 3 and state == "PENDING" and not result.info and not result.date_done:
                await websocket.send_json(
                    {
                        "job_id": job_id,
                        "status": "ERROR",
                        "error": "Job not found or expired",
                    }
                )
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
            await websocket.send_json(
                {
                    "job_id": job_id,
                    "status": "TIMEOUT",
                    "error": "Job exceeded 10-minute timeout",
                }
            )

    except WebSocketDisconnect:
        pass
    except _celery_backend_errors() as exc:
        logger.warning("WebSocket job poll failed: %s", exc)
    except asyncio.CancelledError:
        raise
