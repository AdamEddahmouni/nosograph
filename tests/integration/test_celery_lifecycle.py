"""Celery job lifecycle integration tests (submit → PROGRESS → SUCCESS/FAILURE).

Uses Redis as the Celery result backend and ``task_always_eager`` so tasks run
inline without a separate worker process. Skips gracefully when Redis is down.
"""

from __future__ import annotations

from unittest.mock import patch

import pytest
from starlette.websockets import WebSocketDisconnect

from med_research.pipeline.base import PipelineRunResult
from tests.integration.conftest import skip_without_redis

pytestmark = [pytest.mark.integration, skip_without_redis]


def _collect_ws_until_terminal(client, job_id: str, *, max_messages: int = 20) -> list[dict]:
    """Read WebSocket messages until a terminal status or the cap is reached."""
    terminal = frozenset({"SUCCESS", "FAILURE", "ERROR", "TIMEOUT"})
    messages: list[dict] = []
    with client.websocket_connect(f"/api/jobs/{job_id}/ws") as ws:
        for _ in range(max_messages):
            try:
                message = ws.receive_json()
            except (RuntimeError, WebSocketDisconnect):
                break
            messages.append(message)
            if message.get("status") in terminal:
                break
    return messages


class TestCeleryJobLifecycle:
    """End-to-end Celery state transitions via HTTP and WebSocket."""

    def test_submit_gwas_reaches_success(
        self,
        integration_client,
        offline_pipeline_http_mocks,
    ):
        client = integration_client
        submit = client.post(
            "/api/jobs/gwas",
            params={"max_studies": 3, "disease_id": "ra", "no_cache": True},
        )
        assert submit.status_code == 200
        job_id = submit.json()["job_id"]

        status = client.get(f"/api/jobs/{job_id}").json()
        assert status["job_id"] == job_id
        assert status["status"] == "SUCCESS"
        assert "result" in status

    def test_submit_failure_surfaces_in_http_status(self, integration_client):
        client = integration_client
        failed = PipelineRunResult(
            success=False,
            data=None,
            errors=["simulated pipeline failure"],
        )

        with patch(
            "med_research.web.services.registry_service.execute_module",
            return_value=failed,
        ):
            submit = client.post(
                "/api/jobs/gwas",
                params={"max_studies": 1, "disease_id": "ra"},
            )
            assert submit.status_code == 200
            job_id = submit.json()["job_id"]

            status = client.get(f"/api/jobs/{job_id}").json()
            assert status["status"] == "FAILURE"
            assert "error" in status
            assert "simulated pipeline failure" in status["error"]

    def test_progress_callback_emits_progress_state(self, integration_client):
        client = integration_client
        progress_meta: list[dict] = []

        def _run_with_progress(
            module_id: str,
            disease_id: str = "sle",
            progress_callback=None,
            **opts,
        ):
            if progress_callback is not None:
                progress_callback(40, "mock progress step")
                progress_meta.append({"percent": 40, "message": "mock progress step"})
            return {"status": "ready", "module": module_id, "disease_id": disease_id}

        with patch(
            "med_research.web.services.registry_service.run_module_job",
            side_effect=_run_with_progress,
        ):
            submit = client.post(
                "/api/jobs/gwas",
                params={"max_studies": 1, "disease_id": "ra"},
            )
            job_id = submit.json()["job_id"]

        assert progress_meta, "progress callback should have been invoked"
        status = client.get(f"/api/jobs/{job_id}").json()
        assert status["status"] == "SUCCESS"

    def test_websocket_reaches_terminal_success(
        self,
        integration_client,
        offline_pipeline_http_mocks,
    ):
        client = integration_client
        submit = client.post(
            "/api/jobs/gwas",
            params={"max_studies": 2, "disease_id": "ra", "no_cache": True},
        )
        job_id = submit.json()["job_id"]

        messages = _collect_ws_until_terminal(client, job_id)
        assert messages, "WebSocket should deliver at least one message"
        assert all(msg["job_id"] == job_id for msg in messages)

        terminal = messages[-1]
        assert terminal["status"] == "SUCCESS"
        assert "result" in terminal

    def test_websocket_reaches_terminal_failure(self, integration_client):
        client = integration_client
        failed = PipelineRunResult(
            success=False,
            data=None,
            errors=["websocket failure contract"],
        )

        with patch(
            "med_research.web.services.registry_service.execute_module",
            return_value=failed,
        ):
            submit = client.post(
                "/api/jobs/gwas",
                params={"max_studies": 1, "disease_id": "ra"},
            )
            job_id = submit.json()["job_id"]

        messages = _collect_ws_until_terminal(client, job_id)
        failure_msgs = [msg for msg in messages if msg.get("status") == "FAILURE"]
        assert failure_msgs, f"Expected FAILURE over WebSocket, got: {messages}"
        assert "websocket failure contract" in failure_msgs[-1].get("error", "")
