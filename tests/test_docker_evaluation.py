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


@pytest.mark.parametrize("dockerfile", ["Dockerfile", "Dockerfile.demo"])
def test_images_declare_the_default_port_explicitly(dockerfile: str) -> None:
    """ENV PORT makes the default visible to the runtime and the probe."""
    text = (ROOT / dockerfile).read_text(encoding="utf-8")
    assert "ENV PORT=8000" in text
    assert "os.environ.get('PORT', '8000')" in text
    assert "USER appuser" in text
    assert "--reload" not in text
    assert "EXPOSE 8000" in text


def test_compose_web_services_use_one_injected_port() -> None:
    text = (ROOT / "docker-compose.yml").read_text(encoding="utf-8")
    # Host publish, container listen port, and healthcheck must agree.
    assert text.count('"${PORT:-8000}:${PORT:-8000}"') == 2
    assert text.count("- PORT=${PORT:-8000}") == 2
    assert text.count('os.environ.get(\\"PORT\\", \\"8000\\")') == 2


def test_compose_demo_profile_points_at_the_built_snapshot() -> None:
    """`pipeline demo build` writes into ./data; the demo service must look there."""
    text = (ROOT / "docker-compose.yml").read_text(encoding="utf-8")
    demo_block = text.split("# ── Web API (read-only demo profile)", 1)[1]
    assert "DEMO_REQUIRE_MODE=true" in demo_block
    assert "DEMO_MODE=true" in demo_block
    assert "DEMO_SNAPSHOT_PATH=/app/data/demo/biomedical.sqlite3" in demo_block
    assert "DEMO_SNAPSHOT_MANIFEST=/app/data/demo/biomedical.manifest.json" in demo_block


def test_single_container_demo_honours_injected_port() -> None:
    text = (ROOT / "docker-compose.demo.yml").read_text(encoding="utf-8")
    assert '"${PORT:-8000}:${PORT:-8000}"' in text
    assert "- PORT=${PORT:-8000}" in text
    assert "DEMO_REQUIRE_MODE=true" in text
    assert "/api/health" in text


def test_docker_smoke_script_covers_injected_port_and_probes() -> None:
    """The smoke harness is the local stand-in for a hosted deploy check."""
    script = (ROOT / "scripts" / "docker_smoke.py").read_text(encoding="utf-8")
    assert "--require-ready" in script
    assert "--no-build" in script
    assert "/api/health" in script and "/api/ready" in script
    assert '"PORT="{port}"' in script or 'f"PORT={port}"' in script
    assert "finally:" in script
    assert '"rm", "-f"' in script
