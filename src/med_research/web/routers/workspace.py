"""Saved Evidence-to-Hypothesis Workspace run history API."""

from fastapi import APIRouter, HTTPException, Query

from med_research.web.config import WORKSPACE_DB_PATH
from med_research.web.models import (
    WorkspaceCompareResponse,
    WorkspaceRunListResponse,
    WorkspaceRunResponse,
    WorkspaceTrendsResponse,
)
from med_research.web.services.workspace_store import WorkspaceRunStore

_TRENDS_LIMIT = Query(default=20, ge=1, le=100)
router = APIRouter(prefix="/api/workspace", tags=["Evidence Workspace"])


def _store() -> WorkspaceRunStore:
    return WorkspaceRunStore(WORKSPACE_DB_PATH)


@router.get("/runs", response_model=WorkspaceRunListResponse)
def list_workspace_runs(
    limit: int = Query(default=25, ge=1, le=200), offset: int = Query(default=0, ge=0)
):
    return {
        "runs": _store().list_runs(limit=limit, offset=offset),
        "limit": limit,
        "offset": offset,
    }


@router.get("/runs/{run_id}", response_model=WorkspaceRunResponse)
def get_workspace_run(run_id: str):
    result = _store().get_run(run_id)
    if result is None:
        raise HTTPException(status_code=404, detail=f"Workspace run not found: {run_id}")
    return result


@router.delete("/runs/{run_id}")
def delete_workspace_run(run_id: str):
    if not _store().delete_run(run_id):
        raise HTTPException(status_code=404, detail=f"Workspace run not found: {run_id}")
    return {"deleted": True, "run_id": run_id}


@router.get("/trends", response_model=WorkspaceTrendsResponse)
def workspace_trends(
    run_ids: list[str] | None = None,
    limit: int = _TRENDS_LIMIT,
):
    return _store().trends(limit=limit, run_ids=run_ids)


@router.get("/compare", response_model=WorkspaceCompareResponse)
def compare_workspace_runs(left: str, right: str):
    try:
        return _store().compare_runs(left, right)
    except KeyError as exc:
        raise HTTPException(
            status_code=404, detail=f"Workspace run not found: {exc.args[0]}"
        ) from exc
