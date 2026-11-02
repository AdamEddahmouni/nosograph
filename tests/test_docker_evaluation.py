"""Guards for the documented Docker evaluation stack."""

from __future__ import annotations

import re
from pathlib import Path

import pytest

pytestmark = pytest.mark.unit

ROOT = Path(__file__).resolve().parents[1]


def test_dockerfile_installs_editable_package_after_source_copy() -> None:
    text = (ROOT / "Dockerfile").read_text(encoding="utf-8")
    deps, _, runtime = text.partition("FROM deps AS runtime")
    assert "pip install -e ." not in deps
    copy_idx = runtime.find("COPY . .")
    install_idx = runtime.find("pip install --no-deps -e .")
    assert copy_idx != -1
    assert install_idx != -1
    assert copy_idx < install_idx


def test_compose_worker_and_beat_invoke_celery_directly() -> None:
    text = (ROOT / "docker-compose.yml").read_text(encoding="utf-8")
    assert 'entrypoint: ["celery"]' in text
    assert "command: celery -A med_research.web.tasks.analysis_tasks worker" not in text
    assert "command: celery -A med_research.web.tasks.analysis_tasks beat" not in text
    assert '"-A", "med_research.web.tasks.analysis_tasks", "worker"' in text
    assert '"-A", "med_research.web.tasks.analysis_tasks", "beat"' in text


def test_dockerignore_excludes_runtime_data_directory() -> None:
    lines = [
        line.strip()
        for line in (ROOT / ".dockerignore").read_text(encoding="utf-8").splitlines()
        if line.strip() and not line.strip().startswith("#")
    ]
    assert "data/" in lines
    # The repository-local pytest temp dir uses an underscore; a hyphen-only
    # ignore rule would still copy a potentially unreadable artifact.
    assert ".pytest_tmp/" in lines


def test_compose_keeps_internal_image_tag_and_public_project_name() -> None:
    text = (ROOT / "docker-compose.yml").read_text(encoding="utf-8")
    assert re.search(r"(?m)^name:\s*nosograph\s*$", text)
    assert "image: med-research:latest" in text
    assert "compatibility" in text.lower() or "internal" in text.lower()


def test_dockerfile_healthcheck_uses_runtime_port() -> None:
    """A platform-injected PORT must not leave the healthcheck on 8000."""
    text = (ROOT / "Dockerfile").read_text(encoding="utf-8")
    assert "os.environ.get('PORT', '8000')" in text
    assert "127.0.0.1:8000" not in text
