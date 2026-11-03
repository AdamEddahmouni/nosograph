"""Regression tests for the bounded process runner in ``scripts/docker_smoke.py``.

The original harness used ``subprocess.run(..., capture_output=True,
timeout=...)``, which does not actually bound a hung ``docker build``: on
timeout CPython kills the direct child and then re-reads the pipes with no
timeout, so any grandchild holding the inherited write handle blocks the read
forever. These tests pin the fix -- a timeout must return promptly even when a
grandchild inherits the handles.
"""

from __future__ import annotations

import importlib.util
import json
import sys
import time
from pathlib import Path

import pytest

SCRIPT = Path(__file__).parents[1] / "scripts" / "docker_smoke.py"


def _load_module():
    spec = importlib.util.spec_from_file_location("docker_smoke_under_test", SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


docker_smoke = _load_module()

BOUND = 4.0
# Allow generous headroom over the bound for process teardown on slow CI.
SLACK = 30.0


def test_runner_captures_both_streams() -> None:
    result = docker_smoke._run(
        [sys.executable, "-c", "import sys; print('out'); print('err', file=sys.stderr)"],
        timeout=30,
    )
    assert result.ok
    assert result.stdout.strip() == "out"
    assert result.stderr.strip() == "err"
    assert result.timed_out is False


def test_runner_reports_a_missing_binary_without_raising() -> None:
    result = docker_smoke._run(["nosograph-definitely-not-a-binary"], timeout=10)
    assert result.ok is False
    assert result.returncode == 127
    assert result.stderr


def test_runner_nonzero_exit_is_not_ok() -> None:
    result = docker_smoke._run([sys.executable, "-c", "raise SystemExit(3)"], timeout=30)
    assert result.ok is False
    assert result.returncode == 3


def test_runner_bounds_a_hung_child() -> None:
    started = time.monotonic()
    result = docker_smoke._run(
        [sys.executable, "-c", "import time; time.sleep(120)"], timeout=BOUND
    )
    elapsed = time.monotonic() - started
    assert result.timed_out is True
    assert result.ok is False
    assert elapsed < BOUND + SLACK, f"runner did not bound the child ({elapsed:.1f}s)"


def test_runner_bounds_a_child_whose_grandchild_inherits_the_handles() -> None:
    """The exact shape that wedged the Windows docker build."""
    inner = (
        "import subprocess, sys, time;"
        " subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(120)']);"
        " time.sleep(120)"
    )
    started = time.monotonic()
    result = docker_smoke._run([sys.executable, "-c", inner], timeout=BOUND)
    elapsed = time.monotonic() - started
    assert result.timed_out is True
    assert elapsed < BOUND + SLACK, (
        f"an inherited pipe handle blocked the runner for {elapsed:.1f}s"
    )


def test_no_build_without_an_image_fails_fast() -> None:
    """Runtime-only mode must refuse to guess an image rather than build one."""
    assert docker_smoke.main(["--no-build"]) != 0


def test_build_only_and_no_build_are_mutually_exclusive() -> None:
    with pytest.raises(SystemExit):
        docker_smoke.main(["--build-only", "--no-build", "--image", "x:y"])


def test_environment_failure_uses_its_own_exit_code(capsys) -> None:
    """A missing CLI or unreachable daemon is exit 3, not a failed check.

    The module docstring promises 0 for a clean run, 3 when the docker CLI or
    daemon cannot be reached, and 1 for a failed check. Without this guard the
    environment case collapsed into 1, so a caller could not tell "cannot run
    here" from "ran and failed" -- which is exactly what a hosted runner needs
    to distinguish before it reports a build failure.
    """
    assert docker_smoke.EXIT_ENVIRONMENT == 3

    checks = [
        {
            "name": "docker_daemon",
            "phase": "environment",
            "ok": False,
            "required": True,
            "detail": "cannot connect to the Docker daemon",
        }
    ]
    finish_kwargs = {"image": "none:latest", "port": 8000, "image_origin": "reused", "report": None}

    assert (
        docker_smoke._finish(checks, exit_code=docker_smoke.EXIT_ENVIRONMENT, **finish_kwargs) == 3
    )
    payload = json.loads(capsys.readouterr().out)
    assert payload["ok"] is False
    assert payload["failures"] == ["docker_daemon"]

    # An ordinary failed check is still 1, and a clean run is still 0.
    assert docker_smoke._finish(checks, **finish_kwargs) == 1
    passing = [{**checks[0], "ok": True, "detail": "available"}]
    assert docker_smoke._finish(passing, **finish_kwargs) == 0
