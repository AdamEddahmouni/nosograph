"""Saved Evidence-to-Hypothesis Workspace run history and review API."""

import os
import re
from typing import Any

from fastapi import APIRouter, HTTPException, Query, Request
from fastapi.responses import RedirectResponse, StreamingResponse

from med_research.web.config import WORKSPACE_DB_PATH
from med_research.web.identity import get_researcher_id
from med_research.web.models import (
    WorkspaceAlertListResponse,
    WorkspaceCandidateHistoryResponse,
    WorkspaceCandidateReview,
    WorkspaceCandidateReviewRequest,
    WorkspaceCompareResponse,
    WorkspaceEvidenceGraphResponse,
    WorkspaceNotificationSettings,
    WorkspaceNotificationSettingsRequest,
    WorkspaceReviewListResponse,
    WorkspaceRunListResponse,
    WorkspaceRunResponse,
    WorkspaceTrendsResponse,
    WorkspaceWeeklyDigestResponse,
)
from med_research.web.services.auth import resolve_principal
from med_research.web.services.notifications import (
    _slack_webhook_is_safe,
    dispatch_pending_alerts,
    dispatch_weekly_digest,
    render_weekly_digest,
)
from med_research.web.services.review_export import build_review_bundle
from med_research.web.services.review_links import create_review_link, verify_review_token
from med_research.web.services.workspace_graph import build_workspace_graph
from med_research.web.services.workspace_store import WorkspaceRunStore

_TRENDS_LIMIT = Query(default=20, ge=1, le=100)
router = APIRouter(prefix="/api/workspace", tags=["Evidence Workspace"])


def _store() -> WorkspaceRunStore:
    return WorkspaceRunStore(WORKSPACE_DB_PATH)


@router.get("/alerts", response_model=WorkspaceAlertListResponse)
def list_workspace_alerts(
    request: Request,
    unread_only: bool = Query(default=False),
    limit: int = Query(default=25, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
) -> Any:
    store = _store()
    researcher_id = get_researcher_id(request)
    store.refresh_alerts(researcher_id)
    dispatch_pending_alerts(store, researcher_id)
    dispatch_weekly_digest(store, researcher_id)
    return store.list_alerts(
        researcher_id, unread_only=unread_only, limit=limit, offset=offset
    )


@router.get("/notifications", response_model=WorkspaceNotificationSettings)
def get_workspace_notification_settings(request: Request) -> Any:
    return _store().get_notification_settings(get_researcher_id(request))


@router.put("/notifications", response_model=WorkspaceNotificationSettings)
def save_workspace_notification_settings(
    request: Request, payload: WorkspaceNotificationSettingsRequest
) -> Any:
    if payload.slack_webhook_url and not _slack_webhook_is_safe(payload.slack_webhook_url):
        raise HTTPException(
            status_code=422,
            detail="slack_webhook_url must be an HTTPS Slack webhook URL",
        )
    store = _store()
    researcher_id = get_researcher_id(request)
    existing = store._notification_settings_raw(researcher_id)
    webhook_url = payload.slack_webhook_url or existing.get("slack_webhook_url", "")
    store.save_notification_settings(
        researcher_id,
        payload.email,
        payload.email_enabled,
        webhook_url,
        payload.slack_enabled,
        payload.score_drop_threshold,
        payload.rank_change_threshold,
        payload.evidence_quality_change_threshold,
        payload.weekly_digest_enabled,
        payload.weekly_digest_weekday,
        payload.weekly_digest_hour,
        payload.weekly_digest_minute,
        payload.weekly_digest_timezone,
    )
    store.refresh_alerts(researcher_id)
    dispatch_pending_alerts(store, researcher_id)
    dispatch_weekly_digest(store, researcher_id)
    return store.get_notification_settings(researcher_id)


@router.get("/digest", response_model=WorkspaceWeeklyDigestResponse)
def preview_workspace_digest(request: Request) -> Any:
    store = _store()
    researcher_id = get_researcher_id(request)
    store.refresh_alerts(researcher_id)
    digest = store.build_weekly_digest(researcher_id)
    digest["review_url"] = create_review_link(researcher_id, digest["digest_key"])
    digest["markdown"] = render_weekly_digest(digest)
    return digest


@router.post("/digest/send", response_model=WorkspaceWeeklyDigestResponse)
def send_workspace_digest(request: Request, force: bool = Query(default=False)) -> Any:
    store = _store()
    researcher_id = get_researcher_id(request)
    store.refresh_alerts(researcher_id)
    digest = dispatch_weekly_digest(store, researcher_id, force=force)
    if digest.get("status") == "disabled":
        raise HTTPException(status_code=409, detail="Weekly researcher digest is disabled")
    return digest


@router.get("/digest/delivery-history")
def workspace_digest_delivery_history(
    request: Request, limit: int = Query(default=50, ge=1, le=200)
) -> dict[str, Any]:
    return {
        "deliveries": _store().list_digest_deliveries(get_researcher_id(request), limit)
    }


@router.get("/digest/review")
def open_workspace_digest_review(request: Request, token: str) -> RedirectResponse:
    claims = verify_review_token(token)
    if claims is None:
        raise HTTPException(status_code=401, detail="Invalid or expired workspace review link")
    principal = resolve_principal(request)
    if principal and principal != claims["researcher_id"]:
        raise HTTPException(status_code=403, detail="Workspace review link belongs to another researcher")
    if not principal and os.environ.get("DEBUG", "false").lower() != "true":
        raise HTTPException(status_code=401, detail="Authentication required to open workspace review link")
    from urllib.parse import quote

    destination = (
        "/?researcher_id="
        + quote(claims["researcher_id"])
        + "&digest_key="
        + quote(claims["digest_key"])
        + "#evidence-workspace"
    )
    return RedirectResponse(destination, status_code=303)


@router.post("/alerts/{alert_id}/read")
def mark_workspace_alert_read(request: Request, alert_id: str) -> dict[str, Any]:
    researcher_id = get_researcher_id(request)
    if not _store().mark_alert_read(alert_id, researcher_id):
        raise HTTPException(status_code=404, detail=f"Workspace alert not found: {alert_id}")
    return {"alert_id": alert_id, "read": True}


@router.get("/runs", response_model=WorkspaceRunListResponse)
def list_workspace_runs(
    limit: int = Query(default=25, ge=1, le=200), offset: int = Query(default=0, ge=0)
) -> dict[str, Any]:
    return {
        "runs": _store().list_runs(limit=limit, offset=offset),
        "limit": limit,
        "offset": offset,
    }


@router.get("/runs/{run_id}", response_model=WorkspaceRunResponse)
def get_workspace_run(run_id: str) -> Any:
    result = _store().get_run(run_id)
    if result is None:
        raise HTTPException(status_code=404, detail=f"Workspace run not found: {run_id}")
    return result


@router.delete("/runs/{run_id}")
def delete_workspace_run(run_id: str) -> dict[str, Any]:
    if not _store().delete_run(run_id):
        raise HTTPException(status_code=404, detail=f"Workspace run not found: {run_id}")
    return {"deleted": True, "run_id": run_id}


@router.get("/runs/{run_id}/reviews", response_model=WorkspaceReviewListResponse)
def list_candidate_reviews(request: Request, run_id: str) -> dict[str, Any]:
    store = _store()
    if store.get_run(run_id) is None:
        raise HTTPException(status_code=404, detail=f"Workspace run not found: {run_id}")
    researcher_id = get_researcher_id(request)
    return {"run_id": run_id, "reviews": store.list_reviews(run_id, researcher_id)}


@router.get("/runs/{run_id}/review-events")
def list_candidate_review_events(request: Request, run_id: str) -> dict[str, Any]:
    store = _store()
    if store.get_run(run_id) is None:
        raise HTTPException(status_code=404, detail=f"Workspace run not found: {run_id}")
    researcher_id = get_researcher_id(request)
    return {"run_id": run_id, "events": store.list_review_events(run_id, researcher_id)}


@router.get("/runs/{run_id}/graph", response_model=WorkspaceEvidenceGraphResponse)
def workspace_evidence_graph(request: Request, run_id: str) -> Any:
    store = _store()
    run = store.get_run(run_id)
    if run is None:
        raise HTTPException(status_code=404, detail=f"Workspace run not found: {run_id}")
    if not run.get("dossier"):
        raise HTTPException(status_code=409, detail="Workspace run has no completed dossier")
    researcher_id = get_researcher_id(request)
    return build_workspace_graph(run, store.list_reviews(run_id, researcher_id), researcher_id)


@router.put("/runs/{run_id}/reviews", response_model=WorkspaceCandidateReview)
def save_candidate_review(
    request: Request, run_id: str, review: WorkspaceCandidateReviewRequest
) -> Any:
    store = _store()
    run = store.get_run(run_id)
    if run is None:
        raise HTTPException(status_code=404, detail=f"Workspace run not found: {run_id}")
    dossier = run.get("dossier") or {}
    rankings = dossier.get(f"{review.candidate_type}_rankings", [])
    candidate = next(
        (item for item in rankings if item.get("candidate_id") == review.candidate_id), None
    )
    if candidate is None:
        raise HTTPException(
            status_code=404,
            detail=f"Candidate not found in workspace run: {review.candidate_id}",
        )
    provenance = (dossier.get("manifest") or {}).get("provenance") or {}
    return store.upsert_review(
        run_id=run_id,
        candidate_id=review.candidate_id,
        candidate_type=review.candidate_type,
        candidate_name=candidate.get("name", review.candidate_id),
        decision=review.decision,
        rationale=review.rationale,
        notes=review.notes,
        tags=review.tags,
        changed_my_mind=review.changed_my_mind,
        provenance_fingerprint=provenance.get("fingerprint", ""),
        researcher_id=get_researcher_id(request),
    )


@router.get("/candidate-history", response_model=WorkspaceCandidateHistoryResponse)
def candidate_history(
    request: Request,
    candidate_id: str = Query(..., min_length=1, max_length=200),
    candidate_type: str = Query(..., pattern="^(drug|target)$"),
    disease_id: str | None = Query(default=None, min_length=1, max_length=50),
) -> Any:
    return _store().candidate_history(
        candidate_id, candidate_type, disease_id, get_researcher_id(request)
    )


@router.get("/runs/{run_id}/review-bundle")
def download_review_bundle(request: Request, run_id: str) -> StreamingResponse:
    store = _store()
    run = store.get_run(run_id)
    if run is None:
        raise HTTPException(status_code=404, detail=f"Workspace run not found: {run_id}")
    if not run.get("dossier"):
        raise HTTPException(status_code=409, detail="Workspace run has no completed dossier")
    researcher_id = get_researcher_id(request)
    archive = build_review_bundle(
        run,
        store.list_reviews(run_id, researcher_id),
        store.list_review_events(run_id, researcher_id),
    )
    safe_run_id = re.sub(r"[^A-Za-z0-9._-]+", "-", run_id)
    return StreamingResponse(
        iter([archive.getvalue()]),
        media_type="application/zip",
        headers={
            "Content-Disposition": f'attachment; filename="workspace-{safe_run_id}-review.zip"'
        },
    )


@router.get("/trends", response_model=WorkspaceTrendsResponse)
def workspace_trends(
    run_ids: list[str] | None = None,
    limit: int = _TRENDS_LIMIT,
) -> Any:
    return _store().trends(limit=limit, run_ids=run_ids)


@router.get("/compare", response_model=WorkspaceCompareResponse)
def compare_workspace_runs(request: Request, left: str, right: str) -> Any:
    try:
        return _store().compare_runs(left, right, get_researcher_id(request))
    except KeyError as exc:
        raise HTTPException(
            status_code=404, detail=f"Workspace run not found: {exc.args[0]}"
        ) from exc
