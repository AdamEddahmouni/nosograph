"""Health/readiness version must track canonical package metadata."""

from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from med_research import __version__
from med_research.pipeline.provenance import package_version
from med_research.web.config import API_VERSION
from med_research.web.main import app

pytestmark = pytest.mark.unit

ROOT = Path(__file__).resolve().parents[1]


def test_health_version_matches_dunder_version() -> None:
    with TestClient(app) as client:
        payload = client.get("/api/health").json()
    assert payload["status"] == "ok"
    assert payload["version"] == __version__
    assert __version__ == API_VERSION
    assert package_version() == __version__


def test_pyproject_version_matches_dunder_version() -> None:
    text = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
    assert f'version = "{__version__}"' in text


def test_config_has_no_stale_version_fallback() -> None:
    text = (ROOT / "src" / "med_research" / "web" / "config.py").read_text(encoding="utf-8")
    assert 'API_VERSION = "2.2.0"' not in text
    assert "API_VERSION = __version__" in text
