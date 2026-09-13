"""DEMO_MODE is opt-in and does not activate unintentionally."""

from __future__ import annotations

import asyncio
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from med_research.web.demo_mode import (
    DEMO_WS_CLOSE_CODE,
    DEMO_WS_CLOSE_REASON,
    is_demo_allowed_path,
    is_demo_mode,
)
from med_research.web.main import app

pytestmark = pytest.mark.unit

DEMO_READ_ONLY = {
    "code": "demo_read_only",
    "detail": "This operation is disabled in the public read-only demo.",
}


def test_demo_mode_defaults_off(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("DEMO_MODE", raising=False)
    assert is_demo_mode() is False
    for value in ("", "false", "0", "no", "off", "TRUEISH"):
        monkeypatch.setenv("DEMO_MODE", value)
        assert is_demo_mode() is False


def test_demo_mode_opt_in_values(monkeypatch: pytest.MonkeyPatch) -> None:
    for value in ("true", "TRUE", "1", "yes", "on"):
        monkeypatch.setenv("DEMO_MODE", value)
        assert is_demo_mode() is True


def test_parse_demo_mode_helper() -> None:
    from med_research.web.config import parse_demo_mode

    assert parse_demo_mode("") is False
    assert parse_demo_mode("true") is True
    assert parse_demo_mode("false") is False
    assert parse_demo_mode("no") is False


def test_demo_allows_reads_and_blocks_jobs() -> None:
    assert is_demo_allowed_path("/api/health", "GET") is True
    assert is_demo_allowed_path("/api/system/diseases", "GET") is True
    assert is_demo_allowed_path("/api/jobs/run-all", "POST") is False
    assert is_demo_allowed_path("/api/jobs/abc", "GET") is False
    assert is_demo_allowed_path("/api/v1/nosograph/comparisons", "POST") is False
    assert is_demo_allowed_path("/api/v1/nosograph/comparisons/preview", "POST") is True


def test_demo_does_not_activate_on_default_client() -> None:
    with TestClient(app) as client:
        health = client.get("/api/health")
        assert health.status_code == 200
        with patch("med_research.web.routers.jobs.task_run_all") as mock_task:
            mock_task.delay.return_value.id = "00000000-0000-0000-0000-000000000021"
            jobs = client.post("/api/jobs/run-all", params={"disease_id": "sle"})
        assert jobs.status_code != 403
        assert jobs.json().get("code") != "demo_read_only"


def test_demo_blocks_job_submission_when_enabled(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DEMO_MODE", "true")
    with TestClient(app) as client:
        with patch("med_research.web.routers.jobs.task_run_all") as mock_task:
            response = client.post("/api/jobs/run-all", params={"disease_id": "sle"})
        assert response.status_code == 403
        assert response.json() == DEMO_READ_ONLY
        mock_task.delay.assert_not_called()
        assert client.get("/api/health").status_code == 200


def test_demo_websocket_middleware_does_not_call_app(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DEMO_MODE", "true")
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
    assert sent[0]["type"] == "websocket.close"
    assert sent[0]["code"] == DEMO_WS_CLOSE_CODE
    assert sent[0]["reason"] == DEMO_WS_CLOSE_REASON
