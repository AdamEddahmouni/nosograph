import datetime
import re

import pytest
from fastapi.testclient import TestClient

from med_research.web.main import app

client = TestClient(app)


@pytest.mark.unit
def test_dossier_generate_endpoint():
    response = client.get("/api/dossier/generate")
    # Should either succeed with URLs or 404 if pipeline empty in isolation
    assert response.status_code in (200, 404)
    if response.status_code == 200:
        data = response.json()
        assert "pdf_url" in data
        assert "markdown_url" in data
        assert "timestamp" in data


@pytest.mark.unit
def test_dossier_generate_filename_timestamp_shape(monkeypatch):
    from med_research.web.routers import dossier as dossier_router

    monkeypatch.setattr(
        dossier_router, "collect_module_data", lambda: {"demo_module": {"status": "ok"}}
    )
    response = client.get("/api/dossier/generate")
    assert response.status_code == 200
    data = response.json()
    # Filename-safe token must retain the exact YYYYMMDDTHHMMSSZ shape.
    assert re.fullmatch(r"\d{8}T\d{6}Z", data["timestamp"])


@pytest.mark.unit
def test_dossier_markdown_timestamp_carries_utc_offset():
    from med_research.web.services.dossier_service import data_to_markdown

    markdown = data_to_markdown({"demo_module": {"status": "ok"}})
    match = re.search(r"Generated at: (.+)", markdown)
    assert match is not None
    parsed = datetime.datetime.fromisoformat(match.group(1).strip())
    assert parsed.tzinfo is not None
    assert parsed.utcoffset() == datetime.timedelta(0)


@pytest.mark.unit
def test_dossier_html_timestamp_carries_utc_offset():
    from med_research.web.services.dossier_service import render_dossier_html

    html = render_dossier_html({"demo_module": {"status": "ok"}})
    heading = re.search(r"Regulatory Dossier[^<]*</h1>", html)
    assert heading is not None
    timestamp_text = re.search(r"\d{4}-\d{2}-\d{2}T[0-9:.+]+", heading.group(0))
    assert timestamp_text is not None
    parsed = datetime.datetime.fromisoformat(timestamp_text.group(0))
    assert parsed.tzinfo is not None
    assert parsed.utcoffset() == datetime.timedelta(0)
