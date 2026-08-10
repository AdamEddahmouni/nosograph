"""Disease Admin API router — module lifecycle without the CLI.

Endpoints:
    GET  /api/admin/diseases/{id}/backups   — list pruned backups
    POST /api/admin/diseases/{id}/prune     — refresh + drop stale entities
                                              (preview by default; apply: true writes)
    POST /api/admin/diseases/{id}/restore   — re-merge a pruned backup
                                              (preview by default; apply: true writes)
    GET  /api/admin/diseases/{id}/audit     — recent prune/restore activity

The prune/restore endpoints are declared as sync ``def`` so FastAPI runs them
in its threadpool — a live refresh hits external APIs and must not block the
event loop. Both mutation endpoints are auto-protected by AuthMiddleware when
an API key is configured.
"""

from typing import Any

from fastapi import APIRouter, HTTPException

from med_research.web.models.disease_admin import (
    AuditResponse,
    BackupsResponse,
    PruneRequest,
    PruneResponse,
    RestoreRequest,
    RestoreResponse,
)
from med_research.web.services import disease_admin_service

router = APIRouter(prefix="/api/admin/diseases", tags=["Disease Admin"])


@router.get("/{disease_id}/backups", response_model=BackupsResponse)
def list_backups(disease_id: str) -> dict[str, Any]:
    """List the pruned backups for a disease (newest first)."""
    try:
        return disease_admin_service.list_disease_backups(disease_id)
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e


@router.post("/{disease_id}/prune", response_model=PruneResponse)
def prune_disease(disease_id: str, req: PruneRequest) -> dict[str, Any]:
    """Refresh sources and drop entities no longer reported.

    Default (``apply: false``) is a preview: merge + prune candidates are
    returned and nothing is written. With ``apply: true`` the module's data
    files are updated and pruned entities are backed up.
    """
    try:
        if req.apply:
            return disease_admin_service.apply_prune(disease_id, req)
        return disease_admin_service.preview_prune(disease_id, req)
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e


@router.post("/{disease_id}/restore", response_model=RestoreResponse)
def restore_disease(disease_id: str, req: RestoreRequest) -> dict[str, Any]:
    """Re-merge a pruned backup back into the module.

    ``backup`` accepts a full path or a bare filename from the module's
    data/backups/ dir; omitted → the newest backup. ``apply: true`` writes.
    """
    try:
        if req.apply:
            return disease_admin_service.apply_restore(disease_id, req.backup)
        return disease_admin_service.preview_restore(disease_id, req.backup)
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e


@router.get("/{disease_id}/audit", response_model=AuditResponse)
def list_audit(disease_id: str, limit: int = 20) -> dict[str, Any]:
    """Return a module's recent prune/restore activity (newest first).

    ``limit`` clamps to the last N actions (1–500). The log is written by the
    scaffold engine, so CLI-driven mutations appear here too.
    """
    try:
        return disease_admin_service.list_disease_audit(disease_id, limit=limit)
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
