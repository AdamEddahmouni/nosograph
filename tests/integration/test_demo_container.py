"""Contract tests for the single-container public demo profile.

The static checks always run and pin the demo boundary (no Redis/Celery,
snapshot baked in, non-root user, read-only policy env). The runtime smoke
test builds and boots the image with Docker; it is skipped when the Docker
CLI or daemon is unavailable.
"""

from __future__ import annotations

import json
import shutil
import subprocess
import time
import urllib.request
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]


def _demo_compose() -> str:
    return (ROOT / "docker-compose.demo.yml").read_text(encoding="utf-8")


def test_demo_image_bakes_snapshot_and_stays_non_root() -> None:
    dockerfile = (ROOT / "Dockerfile.demo").read_text(encoding="utf-8")
    assert "build_demo_snapshot.py" in dockerfile
    assert "DEMO_SNAPSHOT_PATH=" in dockerfile
    assert "DEMO_SNAPSHOT_MANIFEST=" in dockerfile
    assert "USER appuser" in dockerfile
    assert "pip install --no-deps -e ." in dockerfile


def test_demo_compose_runs_one_container_without_redis_celery() -> None:
    text = _demo_compose()
    # One service named web; no broker/worker/beat services or data mount.
    assert "redis" not in text.lower() or "redis://" not in text
    assert "celery" not in text.lower()
    assert "- ./data:/app/data" not in text
    assert "DEMO_MODE=true" in text
    assert "DEBUG=false" in text
    assert "DASHBOARD_CSP_MODE=enforce" in text
    assert "/api/health" in text


def test_demo_snapshot_builder_is_offline_and_reproducible(tmp_path) -> None:
    """The snapshot used by the image builds from checked-in fixtures only."""
    from scripts.build_demo_snapshot import build_demo_snapshot, manifest_path_for

    output = tmp_path / "biomedical.sqlite3"
    build_demo_snapshot(output, fixture_root=ROOT / "tests" / "fixtures" / "biomed")
    manifest = json.loads(manifest_path_for(output).read_text(encoding="utf-8"))
    assert manifest["schema_version"]
    assert manifest["snapshot_version"].startswith("demo-")
    assert {"mondo", "hp", "hpoa"} <= {item["resource_name"] for item in manifest["resources"]}
    assert output.is_file()
    assert output.stat().st_size > 0


@pytest.mark.integration
@pytest.mark.slow
def test_demo_container_boots_read_only_without_redis() -> None:
    """End-to-end Docker smoke: build, boot, health/ready, blocked job POST."""
    if shutil.which("docker") is None:
        pytest.skip("docker CLI not available")
    probe = subprocess.run(
        ["docker", "info"],
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )
    if probe.returncode != 0:
        pytest.skip("docker daemon not available")

    compose_file = ROOT / "docker-compose.demo.yml"
    subprocess.run(
        ["docker", "compose", "-f", str(compose_file), "up", "--build", "-d"],
        check=True,
        timeout=900,
        capture_output=True,
    )
    try:
        base = "http://127.0.0.1:8000"
        deadline = time.monotonic() + 180
        last_error: Exception | None = None
        while time.monotonic() < deadline:
            try:
                with urllib.request.urlopen(f"{base}/api/health", timeout=5) as response:
                    assert response.status == 200
                break
            except Exception as exc:  # noqa: BLE001 - container still starting
                last_error = exc
                time.sleep(5)
        else:
            pytest.fail(f"Demo container did not become healthy: {last_error}")

        with urllib.request.urlopen(f"{base}/api/ready", timeout=10) as response:
            ready = json.loads(response.read().decode("utf-8"))
        assert ready["status"] == "ok"
        assert ready["demo"]["demo_mode"] is True
        assert ready["demo"]["snapshot_version"].startswith("demo-")

        request = urllib.request.Request(
            f"{base}/api/jobs",
            data=b'{"module": "docking", "disease_id": "sle"}',
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            urllib.request.urlopen(request, timeout=10)
        except urllib.error.HTTPError as exc:
            assert exc.code == 403
            assert json.loads(exc.read().decode("utf-8"))["code"] == "demo_read_only"
        else:
            pytest.fail("Demo container accepted a job submission")
    finally:
        subprocess.run(
            ["docker", "compose", "-f", str(compose_file), "down"],
            check=False,
            timeout=120,
            capture_output=True,
        )
