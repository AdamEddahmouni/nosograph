"""Job management API router — submit and track Celery tasks."""

import asyncio
import inspect
import json
import logging
from typing import Annotated, Any
from uuid import UUID

from celery.result import AsyncResult
from fastapi import APIRouter, Depends, HTTPException, Request, WebSocket, WebSocketDisconnect
from pydantic import Field, ValidationError

from med_research.pipeline.evidence_workspace.schemas import ResearchRequest
from med_research.pipeline.registry import module_catalog
from med_research.web.dependencies import safe_serialize
from med_research.web.identity import DEFAULT_RESEARCHER_ID, get_researcher_id
from med_research.web.models import JobStatus, JobSubmitResponse
from med_research.web.models.jobs import (
    GenericModuleJobRequest,
    RunAllJobRequest,
    module_body_request_model,
    module_job_request_model,
)
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
WorkspaceJobRequest = module_body_request_model("evidence_workspace")


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


def _make_catalog_request_dependency(request_model: type[Any]) -> Any:
    """Create a validating query dependency while preserving model OpenAPI docs."""

    parameters = []
    for name, parameter in inspect.signature(request_model).parameters.items():
        field = request_model.model_fields.get(name)
        annotation = parameter.annotation
        if field is not None and field.json_schema_extra:
            annotation = Annotated[
                annotation,
                Field(json_schema_extra=field.json_schema_extra),
            ]
        parameters.append(parameter.replace(annotation=annotation))
    parameters.insert(
        0,
        inspect.Parameter(
            "request",
            inspect.Parameter.KEYWORD_ONLY,
            annotation=Request,
        ),
    )

    def parse_catalog_request(request: Request, **values: Any) -> Any:
        unknown = sorted(set(request.query_params) - set(request_model.model_fields))
        if unknown:
            raise HTTPException(
                status_code=422,
                detail=f"Unknown request options: {', '.join(unknown)}",
            )
        try:
            return request_model.model_validate(values)
        except ValidationError as exc:
            raise HTTPException(
                status_code=422,
                detail=json.loads(exc.json()),
            ) from exc

    parse_catalog_request.__signature__ = inspect.Signature(parameters)  # type: ignore[attr-defined]
    return parse_catalog_request


def _catalog_job_dependency(module_id: str) -> Any:
    """Return the registry-generated query dependency for a legacy job route."""
    return _make_catalog_request_dependency(module_job_request_model(module_id))


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


async def submit_workspace(
    payload: Any,
    request: Request = None,  # type: ignore[assignment]
) -> dict[str, Any]:
    """Submit a catalog-backed Workspace run with server-derived ownership."""
    payload_data = payload.model_dump(mode="json")
    model = payload_data.get("model")
    normalized = ResearchRequest.model_validate(payload_data)
    task_payload = normalized.model_dump(mode="json")
    if model is None:
        # Preserve the legacy task payload when no model was supplied.
        task_payload.pop("model", None)
    task_payload["researcher_id"] = (
        get_researcher_id(request) if request is not None else DEFAULT_RESEARCHER_ID
    )
    task = task_run_workspace.delay(**task_payload)
    return {"job_id": task.id, "status": "PENDING", "module": "workspace"}


# Register after replacing the runtime annotation so FastAPI uses the
# registry-generated body model while mypy can treat the dynamic payload as Any.
submit_workspace.__annotations__["payload"] = WorkspaceJobRequest
router.add_api_route(
    "/workspace",
    submit_workspace,
    methods=["POST"],
    response_model=JobSubmitResponse,
    name="submit_workspace",
)


@router.post("/gwas", response_model=JobSubmitResponse)
async def submit_gwas(
    job: Annotated[Any, Depends(_catalog_job_dependency("gwas"))],
) -> dict[str, Any]:
    """Submit a disease-specific GWAS analysis job."""
    options: dict[str, Any] = {
        "max_studies": job.max_studies if job.max_studies is not None else 30,
        "no_cache": job.no_cache if job.no_cache is not None else False,
        "disease_id": job.disease_id,
    }
    for name in ("use_cache", "resolve_snps"):
        value = getattr(job, name, None)
        if value is not None:
            options[name] = value
    task = task_run_gwas.delay(**options)
    return {"job_id": task.id, "status": "PENDING", "module": "gwas"}


@router.post("/enrichment", response_model=JobSubmitResponse)
async def submit_enrichment(
    job: Annotated[Any, Depends(_catalog_job_dependency("enrichment"))],
) -> dict[str, Any]:
    """Submit a disease-specific pathway enrichment job."""
    options: dict[str, Any] = {
        "untargeted_only": job.untargeted_only if job.untargeted_only is not None else False,
        "no_cache": job.no_cache if job.no_cache is not None else False,
        "disease_id": job.disease_id,
    }
    if job.use_cache is not None:
        options["use_cache"] = job.use_cache
    task = task_run_enrichment.delay(**options)
    return {"job_id": task.id, "status": "PENDING", "module": "enrichment"}


@router.post("/ppi", response_model=JobSubmitResponse)
async def submit_ppi(
    job: Annotated[Any, Depends(_catalog_job_dependency("ppi"))],
) -> dict[str, Any]:
    """Submit a disease-specific PPI network analysis job."""
    options: dict[str, Any] = {
        "confidence": job.confidence if job.confidence is not None else 0.4,
        "no_cache": job.no_cache if job.no_cache is not None else False,
        "disease_id": job.disease_id,
    }
    for name in ("expand_neighbors", "use_cache"):
        value = getattr(job, name, None)
        if value is not None:
            options[name] = value
    task = task_run_ppi.delay(**options)
    return {"job_id": task.id, "status": "PENDING", "module": "ppi"}


@router.post("/literature", response_model=JobSubmitResponse)
async def submit_literature(
    job: Annotated[Any, Depends(_catalog_job_dependency("literature_mining"))],
) -> dict[str, Any]:
    """Submit a disease-specific literature mining job."""
    options: dict[str, Any] = {
        "max_articles": job.max_articles if job.max_articles is not None else 30,
        "targeted": job.targeted if job.targeted is not None else False,
        "no_cache": job.no_cache if job.no_cache is not None else False,
        "disease_id": job.disease_id,
    }
    for name in ("query", "sources", "queries", "extract_content", "use_cache", "email"):
        value = getattr(job, name, None)
        if value is not None:
            options[name] = value
    task = task_run_literature.delay(**options)
    return {"job_id": task.id, "status": "PENDING", "module": "literature"}


@router.post("/screening", response_model=JobSubmitResponse)
async def submit_screening(
    job: Annotated[Any, Depends(_catalog_job_dependency("virtual_screening"))],
) -> dict[str, Any]:
    """Submit a virtual screening job."""
    options: dict[str, Any] = {
        "gene_id": job.gene_id,
        "top_n": job.top_n if job.top_n is not None else 15,
        "use_vina": job.use_vina if job.use_vina is not None else False,
        "disease_id": job.disease_id,
    }
    if job.operation is not None:
        options["operation"] = job.operation
    task = task_run_screening.delay(**options)
    return {"job_id": task.id, "status": "PENDING", "module": "screening"}


@router.post("/trials", response_model=JobSubmitResponse)
async def submit_trials(
    job: Annotated[Any, Depends(_catalog_job_dependency("clinical_trials"))],
) -> dict[str, Any]:
    """Submit a disease-specific clinical trials tracking job."""
    options: dict[str, Any] = {
        "max_trials": job.max_trials if job.max_trials is not None else 100,
        "query": job.query if job.query is not None else "",
        "no_cache": job.no_cache if job.no_cache is not None else False,
        "disease_id": job.disease_id,
    }
    if job.use_cache is not None:
        options["use_cache"] = job.use_cache
    task = task_run_trials.delay(**options)
    return {"job_id": task.id, "status": "PENDING", "module": "trials"}


@router.post("/ml", response_model=JobSubmitResponse)
async def submit_ml(
    job: Annotated[Any, Depends(_catalog_job_dependency("ml_predictor"))],
) -> dict[str, Any]:
    """Submit an ML prediction job."""
    task = task_run_ml.delay(
        top_n=job.top_n if job.top_n is not None else 15,
        no_shap=job.no_shap if job.no_shap is not None else False,
        disease_id=job.disease_id,
    )
    return {"job_id": task.id, "status": "PENDING", "module": "ml"}


@router.post("/synergy", response_model=JobSubmitResponse)
async def submit_synergy(
    job: Annotated[Any, Depends(_catalog_job_dependency("drug_synergy"))],
) -> dict[str, Any]:
    """Submit a drug combination synergy prediction job."""
    options: dict[str, Any] = {
        "top_n": job.top_n if job.top_n is not None else 20,
        "disease_id": job.disease_id,
    }
    if job.save is not None:
        options["save"] = job.save
    task = task_run_synergy.delay(**options)
    return {"job_id": task.id, "status": "PENDING", "module": "synergy"}


@router.post("/safety", response_model=JobSubmitResponse)
async def submit_safety(
    job: Annotated[Any, Depends(_catalog_job_dependency("adverse_events"))],
) -> dict[str, Any]:
    """Submit an adverse event safety profiling job."""
    task = task_run_safety.delay(
        drug_id=job.drug_id,
        disease_id=job.disease_id,
    )
    return {"job_id": task.id, "status": "PENDING", "module": "safety"}


@router.post("/run-all", response_model=JobSubmitResponse)
async def submit_run_all(
    job: Annotated[RunAllJobRequest, Depends(_parse_run_all_request)],
) -> dict[str, Any]:
    """Submit a full pipeline orchestration job (mirrors CLI ``run-all``)."""
    task = task_run_all.delay(job.disease_id, **job.to_task_opts())
    return {"job_id": task.id, "status": "PENDING", "module": "run-all"}


def _make_catalog_job_submitter(module_id: str, request_model: type[Any]) -> Any:
    """Create a static, schema-backed job endpoint for one registry module."""

    request_dependency = _make_catalog_request_dependency(request_model)

    async def submit_catalog_job(
        job: Any = Depends(request_dependency),  # noqa: B008 - dynamic dependency
    ) -> dict[str, Any]:
        task = task_run_module.delay(module_id, job.disease_id, **job.to_task_opts())
        return {"job_id": task.id, "status": "PENDING", "module": module_id}

    submit_catalog_job.__name__ = f"submit_{module_id}_catalog_job"
    submit_catalog_job.__doc__ = (
        f"Submit the {module_id} module using its registry-generated request schema."
    )
    return submit_catalog_job


# Generate static module paths before the fallback ``/{module_id}`` route so
# FastAPI publishes each module's exact query contract in OpenAPI. Dedicated
# legacy aliases above remain unchanged for backwards compatibility.
_DEDICATED_JOB_PATHS = {
    "gwas",
    "enrichment",
    "ppi",
    "literature",
    "screening",
    "trials",
    "ml",
    "synergy",
    "safety",
    "workspace",
    "run-all",
}
for _catalog_entry in module_catalog():
    _catalog_module_id = _catalog_entry["module_id"]
    if _catalog_module_id in _DEDICATED_JOB_PATHS:
        continue
    router.add_api_route(
        f"/{_catalog_module_id}",
        _make_catalog_job_submitter(
            _catalog_module_id,
            module_job_request_model(_catalog_module_id),
        ),
        methods=["POST"],
        response_model=JobSubmitResponse,
        name=f"submit_{_catalog_module_id}_catalog_job",
    )


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

    try:
        job.validate_for_module(resolved)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

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
            # Celery/Redis reads block (connection timeouts can take seconds);
            # run them off the event loop so one slow poll cannot stall the
            # whole server.
            state = await asyncio.to_thread(_safe_result_state, result)
            if state is None:
                await websocket.send_json(
                    {
                        "job_id": job_id,
                        "status": "ERROR",
                        "error": "Job backend unavailable",
                    }
                )
                await websocket.close()
                break

            # Detect orphaned job IDs early (3 polls / 1.5s without any backend data)
            if polls > 3 and state == "PENDING":
                try:
                    info, date_done = await asyncio.to_thread(
                        lambda: (result.info, result.date_done)
                    )
                    job_missing = not info and not date_done
                except _celery_backend_errors() as exc:
                    logger.warning("WebSocket job meta poll failed: %s", exc)
                    await websocket.send_json(
                        {
                            "job_id": job_id,
                            "status": "ERROR",
                            "error": "Job backend unavailable",
                        }
                    )
                    await websocket.close()
                    break
                if job_missing:
                    await websocket.send_json(
                        {
                            "job_id": job_id,
                            "status": "ERROR",
                            "error": "Job not found or expired",
                        }
                    )
                    await websocket.close()
                    break

            # Only send when state changes or on first poll
            if state != last_state:
                last_state = state
                message = {"job_id": job_id, "status": state}

                if state == "SUCCESS":
                    message["result"] = safe_serialize(
                        await asyncio.to_thread(lambda: result.result)
                    )
                    await websocket.send_json(message)
                    await websocket.close()
                    break
                elif state == "FAILURE":
                    failure_info = await asyncio.to_thread(lambda: result.info)
                    message["error"] = str(failure_info) if failure_info else "Unknown error"
                    await websocket.send_json(message)
                    await websocket.close()
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
            await websocket.close()

    except WebSocketDisconnect:
        pass
    except _celery_backend_errors() as exc:
        logger.warning("WebSocket job poll failed: %s", exc)
        try:
            await websocket.send_json(
                {
                    "job_id": job_id,
                    "status": "ERROR",
                    "error": "Job backend unavailable",
                }
            )
            await websocket.close()
        except (WebSocketDisconnect, RuntimeError):
            pass
    except asyncio.CancelledError:
        raise
