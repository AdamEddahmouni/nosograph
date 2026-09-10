"""Public demo deny-by-default route policy."""

from __future__ import annotations

import asyncio
import importlib
from unittest.mock import patch

import pytest
from starlette.websockets import WebSocketDisconnect

DEMO_READ_ONLY = {
    "code": "demo_read_only",
    "detail": "This operation is disabled in the public read-only demo.",
}


def _assert_demo_blocked(response) -> None:
    assert response.status_code == 403
    assert response.json() == DEMO_READ_ONLY


def test_config_defaults_demo_mode_off(monkeypatch):
    monkeypatch.delenv("DEMO_MODE", raising=False)
    monkeypatch.delenv("DEMO_SNAPSHOT_VERSION", raising=False)
    from med_research.web import config

    importlib.reload(config)
    try:
        assert config.DEMO_MODE is False
        assert config.DEMO_SNAPSHOT_VERSION == ""
    finally:
        importlib.reload(config)


def test_is_demo_mode_reads_environment(monkeypatch, demo_env):
    from med_research.web.demo_mode import is_demo_mode

    assert is_demo_mode() is True
    monkeypatch.setenv("DEMO_MODE", "false")
    assert is_demo_mode() is False


def test_demo_mode_helper_uses_shared_parser(monkeypatch):
    from med_research.web import config
    from med_research.web.demo_mode import is_demo_mode

    calls: list[object] = []
    original = config.parse_demo_mode

    def wrapped(value: str | None = None) -> bool:
        calls.append(value)
        return original(value)

    monkeypatch.setattr(config, "parse_demo_mode", wrapped)
    monkeypatch.setenv("DEMO_MODE", "true")
    assert is_demo_mode() is True
    monkeypatch.setenv("DEMO_MODE", "TRUE")
    assert is_demo_mode() is True
    monkeypatch.setenv("DEMO_MODE", "false")
    assert is_demo_mode() is False
    assert calls
    assert original("true") is True
    assert original("no") is False


def test_preview_post_is_allowed_path():
    from med_research.web.demo_mode import is_demo_allowed_path

    assert is_demo_allowed_path("/api/v1/nosograph/comparisons/preview", "POST") is True
    assert is_demo_allowed_path("/api/v1/nosograph/comparisons/preview/", "POST") is True
    assert is_demo_allowed_path("/api/v1/nosograph/comparisons/preview/export", "POST") is True
    assert is_demo_allowed_path("/api/v1/nosograph/comparisons", "POST") is False
    assert is_demo_allowed_path("/api/jobs/run-all", "POST") is False


def test_demo_blocks_job_submission_without_celery(client, demo_env):
    with patch("med_research.web.routers.jobs.task_run_all") as mock_task:
        response = client.post("/api/jobs/run-all", params={"disease_id": "sle"})
    _assert_demo_blocked(response)
    mock_task.delay.assert_not_called()
    mock_task.assert_not_called()


def test_demo_blocks_job_status_and_streaming(client, demo_env):
    job_id = "00000000-0000-0000-0000-000000000099"
    _assert_demo_blocked(client.get(f"/api/jobs/{job_id}"))
    _assert_demo_blocked(client.get(f"/api/stream/jobs/{job_id}"))


def test_demo_blocks_jobs_websocket_without_celery(client, demo_env):
    from med_research.web.demo_mode import DEMO_WS_CLOSE_CODE, DEMO_WS_CLOSE_REASON

    with (
        patch("med_research.web.routers.jobs.AsyncResult") as mock_result,
        pytest.raises(WebSocketDisconnect) as exc_info,
        client.websocket_connect("/api/jobs/00000000-0000-0000-0000-000000000099/ws"),
    ):
        pass
    mock_result.assert_not_called()
    assert exc_info.value.code == DEMO_WS_CLOSE_CODE
    reason = getattr(exc_info.value, "reason", "") or ""
    assert DEMO_WS_CLOSE_REASON in reason or reason == ""


def test_demo_websocket_middleware_does_not_call_app(demo_env):
    from med_research.web.demo_mode import DEMO_WS_CLOSE_CODE, DEMO_WS_CLOSE_REASON
    from med_research.web.middleware import DemoModeMiddleware

    entered = False

    async def inner(scope, receive, send):
        nonlocal entered
        entered = True

    async def receive():
        return {"type": "websocket.connect"}

    sent: list[dict] = []

    async def send(message):
        sent.append(message)

    async def run():
        middleware = DemoModeMiddleware(inner)
        await middleware(
            {
                "type": "websocket",
                "asgi": {"version": "3.0"},
                "path": "/api/jobs/00000000-0000-0000-0000-000000000099/ws",
                "query_string": b"",
                "headers": [],
                "client": ("testclient", 50000),
                "server": ("testserver", 80),
            },
            receive,
            send,
        )

    asyncio.run(run())
    assert entered is False
    assert sent
    assert sent[0]["type"] == "websocket.close"
    assert sent[0]["code"] == DEMO_WS_CLOSE_CODE
    assert sent[0]["reason"] == DEMO_WS_CLOSE_REASON


def test_demo_blocks_workspace_writes(client, demo_env):
    _assert_demo_blocked(
        client.put(
            "/api/workspace/notifications",
            json={"email_enabled": False, "slack_enabled": False},
        )
    )
    _assert_demo_blocked(client.post("/api/workspace/digest/send"))
    _assert_demo_blocked(client.delete("/api/workspace/runs/00000000-0000-0000-0000-000000000001"))
    _assert_demo_blocked(client.post("/api/workspace/alerts/1/read"))


def test_demo_blocks_admin_routes(client, demo_env):
    _assert_demo_blocked(client.get("/api/admin/diseases/sle/backups"))
    _assert_demo_blocked(client.post("/api/admin/diseases/sle/prune", json={}))


def test_demo_blocks_cache_mutation(client, demo_env):
    _assert_demo_blocked(client.delete("/api/system/cache"))
    _assert_demo_blocked(client.delete("/api/system/cache/jobs"))
    _assert_demo_blocked(client.get("/api/system/cache/stats"))


def test_demo_blocks_llm_evidence_and_live_source_routes(client, demo_env):
    _assert_demo_blocked(client.get("/api/llm/extract", params={"q": "lupus"}))
    _assert_demo_blocked(client.get("/api/evidence/gather", params={"q": "lupus"}))
    _assert_demo_blocked(client.post("/api/monitor/snapshot"))
    _assert_demo_blocked(client.get("/api/monitor/diff"))
    _assert_demo_blocked(client.post("/api/agent/chat", json={"message": "hello"}))


def test_demo_blocks_persisted_compare_post(client, demo_env):
    persisted = client.post(
        "/api/v1/nosograph/comparisons",
        json={"condition_curies": ["MONDO:0005290", "MONDO:0008383"]},
    )
    _assert_demo_blocked(persisted)
    _assert_demo_blocked(
        client.post(
            "/api/v1/comparisons",
            json={"left_curie": "MONDO:0005290", "right_curie": "MONDO:0008383"},
        )
    )


def test_demo_allows_health_and_condition_reads(client, demo_env):
    assert client.get("/api/health").status_code == 200
    assert client.get("/api/v1/conditions/search", params={"q": "lupus"}).status_code == 200


def test_demo_allows_claim_evidence_provenance_and_snapshot_reads(client, demo_env):
    search = client.get("/api/v1/conditions/search", params={"q": "lupus", "limit": 5})
    assert search.status_code == 200
    snapshots = client.get("/api/v1/snapshots", params={"limit": 10})
    assert snapshots.status_code == 200
    diseases = client.get("/api/system/diseases")
    assert diseases.status_code == 200
    corpus = client.get("/api/system/corpus-status")
    assert corpus.status_code == 200


def test_demo_blocks_persisted_compare_but_allows_preview(client, demo_env):
    persisted = client.post(
        "/api/v1/nosograph/comparisons",
        json={"condition_curies": ["MONDO:0005290", "MONDO:0008383"]},
    )
    preview = client.post(
        "/api/v1/nosograph/comparisons/preview",
        json={"condition_curies": ["MONDO:0005290", "MONDO:0008383"]},
    )
    assert persisted.status_code == 403
    assert persisted.json()["code"] == "demo_read_only"
    assert preview.status_code != 403


def test_demo_mode_false_preserves_existing_behavior(client, monkeypatch):
    monkeypatch.setenv("DEMO_MODE", "false")
    health = client.get("/api/health")
    assert health.status_code == 200
    with patch("med_research.web.routers.jobs.task_run_all") as mock_task:
        mock_task.delay.return_value.id = "00000000-0000-0000-0000-000000000021"
        jobs = client.post("/api/jobs/run-all", params={"disease_id": "sle"})
    assert jobs.status_code != 403
    assert jobs.json().get("code") != "demo_read_only"
    llm = client.get("/api/llm/extract", params={"q": "lupus"})
    assert llm.status_code != 403
    assert llm.json().get("code") != "demo_read_only"
