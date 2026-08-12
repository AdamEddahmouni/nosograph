"""Unit tests for Server-Sent Events (SSE) job streaming router."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from med_research.web.main import app


@pytest.mark.unit
def test_stream_job_progress_invalid_uuid() -> None:
    client = TestClient(app)
    response = client.get("/api/stream/jobs/invalid-uuid-format")
    assert response.status_code == 400
    assert "Invalid job_id format" in response.json()["detail"]


@pytest.mark.unit
def test_stream_job_progress_valid_uuid(monkeypatch: pytest.MonkeyPatch) -> None:
    fake_job_id = "00000000-0000-0000-0000-000000000001"

    # Mock _safe_result_state to return SUCCESS immediately
    monkeypatch.setattr("med_research.web.routers.stream._safe_result_state", lambda res: "SUCCESS")

    client = TestClient(app)
    response = client.get(f"/api/stream/jobs/{fake_job_id}")
    assert response.status_code == 200
    assert "text/event-stream" in response.headers.get("content-type", "")
    assert "event: job_status" in response.text
    assert fake_job_id in response.text
