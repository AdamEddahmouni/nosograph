"""Server-Sent Events (SSE) router — stream real-time job progress to web clients."""

from __future__ import annotations

import asyncio
import json
import logging
from typing import AsyncGenerator
from uuid import UUID

from celery.result import AsyncResult
from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse

from med_research.web.routers.jobs import _safe_result_state
from med_research.web.tasks.analysis_tasks import celery_app

router = APIRouter(prefix="/api/stream", tags=["Streaming"])
logger = logging.getLogger(__name__)


async def _event_generator(job_id: str) -> AsyncGenerator[str, None]:
    """Poll Celery AsyncResult every 500ms and yield SSE format messages."""
    result = AsyncResult(job_id, app=celery_app)
    last_state: str | None = None
    last_progress: str | None = None

    while True:
        try:
            state = _safe_result_state(result) or "PENDING"
            progress_info = result.info if state == "PROGRESS" else None
            serialized_progress = json.dumps(progress_info, default=str) if progress_info else ""

            if state != last_state or serialized_progress != last_progress:
                payload: dict[str, str | dict[str, str]] = {
                    "job_id": job_id,
                    "status": state,
                }
                if state == "SUCCESS":
                    try:
                        payload["result"] = result.result
                    except Exception:
                        payload["result"] = None
                elif state == "FAILURE":
                    payload["error"] = str(result.info) if result.info else "Task failed"
                elif state == "PROGRESS" and progress_info:
                    payload["progress"] = progress_info

                data_str = json.dumps(payload, default=str)
                yield f"event: job_status\ndata: {data_str}\n\n"

                last_state = state
                last_progress = serialized_progress

                if state in {"SUCCESS", "FAILURE", "REVOKED"}:
                    break

            await asyncio.sleep(0.5)

        except asyncio.CancelledError:
            logger.info("SSE client disconnected for job %s", job_id)
            break
        except Exception as exc:
            logger.error("Error in SSE event stream for job %s: %s", job_id, exc)
            err_payload = json.dumps({"job_id": job_id, "status": "ERROR", "error": str(exc)})
            yield f"event: error\ndata: {err_payload}\n\n"
            break


@router.get("/jobs/{job_id}", response_class=StreamingResponse)
async def stream_job_progress(job_id: str) -> StreamingResponse:
    """Stream real-time job updates as Server-Sent Events (text/event-stream)."""
    try:
        UUID(job_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="Invalid job_id format") from exc

    return StreamingResponse(
        _event_generator(job_id),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
