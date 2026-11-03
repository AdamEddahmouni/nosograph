#!/usr/bin/env python3
"""Smoke-test a NosoGraph container with a platform-injected ``PORT``.

Builds (optionally) and boots one image, then checks that the application
listens on the injected port and that both probes answer on it. The container
is always removed in a ``finally`` block, including on failure.

Usage::

    python scripts/docker_smoke.py                      # build ./Dockerfile
    python scripts/docker_smoke.py --no-build --image nosograph-demo:latest --demo
    python scripts/docker_smoke.py --port 8080 --timeout 240

Output is a single JSON object on stdout::

    {"ok": true, "image": "...", "port": 8000, "checks": [{"name": ..., "ok": ..., "detail": ...}]}

Exit status is 0 only when every check passes. No third-party dependencies are
used: this script must run on a bare runner before the project venv exists.
"""

from __future__ import annotations

import argparse
import json
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_PORT = 8000


def _run(
    args: list[str], *, timeout: float, cwd: Path | None = None
) -> subprocess.CompletedProcess[str]:
    try:
        return subprocess.run(
            args,
            cwd=str(cwd) if cwd else None,
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        # Keep the JSON contract when the docker CLI itself is missing.
        return subprocess.CompletedProcess(args, 127, stdout="", stderr=str(exc))


def _record(checks: list[dict[str, Any]], name: str, ok: bool, detail: str) -> bool:
    checks.append({"name": name, "ok": ok, "detail": detail})
    return ok


def _free_port() -> int:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def _http(
    url: str,
    *,
    method: str = "GET",
    timeout: float = 5.0,
    body: bytes | None = None,
) -> tuple[int, str]:
    request = urllib.request.Request(url, data=body, method=method)
    if body is not None:
        request.add_header("Content-Type", "application/json")
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return response.status, response.read().decode("utf-8", "replace")
    except urllib.error.HTTPError as exc:
        return exc.code, exc.read().decode("utf-8", "replace")


def _wait_for_health(base: str, timeout: float) -> tuple[bool, str]:
    deadline = time.monotonic() + timeout
    last = "no response yet"
    while time.monotonic() < deadline:
        try:
            status, payload = _http(f"{base}/api/health", timeout=5.0)
        except (urllib.error.URLError, TimeoutError, ConnectionError, OSError) as exc:
            last = f"{type(exc).__name__}: {exc}"
        else:
            if status == 200:
                return True, payload.strip()
            last = f"HTTP {status}: {payload.strip()[:200]}"
        time.sleep(2.0)
    return False, last


def _container_logs(container: str) -> str:
    proc = _run(["docker", "logs", "--tail", "40", container], timeout=30)
    text = (proc.stdout or "") + (proc.stderr or "")
    return text.strip()[-2000:]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--port", type=int, default=DEFAULT_PORT, help="Injected PORT (0 = free port)"
    )
    parser.add_argument("--image", default="", help="Image tag to build/run")
    parser.add_argument("--dockerfile", default="Dockerfile", help="Dockerfile used for the build")
    parser.add_argument("--timeout", type=float, default=180.0, help="Readiness timeout in seconds")
    parser.add_argument("--no-build", action="store_true", help="Reuse an existing --image")
    parser.add_argument(
        "--validate-diseases",
        action="store_true",
        help=(
            "Run the full-registry strict validation during the build. Slow, and it "
            "exits non-zero on generated scaffolds by design; the default build skips it."
        ),
    )
    parser.add_argument("--demo", action="store_true", help="Assert the demo write guard")
    parser.add_argument(
        "--require-ready", action="store_true", help="Fail when /api/ready is not 200"
    )
    parser.add_argument(
        "--env",
        action="append",
        default=[],
        metavar="KEY=VALUE",
        help="Extra container environment (repeatable)",
    )
    parser.add_argument("--keep", action="store_true", help="Keep the container and image")
    args = parser.parse_args(argv)

    port = args.port or _free_port()
    image = args.image or f"nosograph-smoke:{port}"
    container = f"nosograph-smoke-{port}"
    checks: list[dict[str, Any]] = []
    built = False
    started = False

    try:
        docker = _run(["docker", "info"], timeout=60)
        daemon_detail = (docker.stderr or "").strip()[-500:] or "available"
        if not _record(checks, "docker_daemon", docker.returncode == 0, daemon_detail):
            return _finish(checks, image, port)

        if not args.no_build:
            build_cmd = ["docker", "build", "-f", args.dockerfile, "-t", image]
            if not args.validate_diseases:
                # The image's build-time validation walks the full 10k+ registry and
                # exits non-zero on generated scaffolds by design (see docs/deployment.md).
                # Opt in with --validate-diseases when that gate is the thing under test.
                build_cmd += ["--build-arg", "DOCKER_SKIP_DISEASE_VALIDATE=1"]
            build = _run(
                [*build_cmd, "."],
                timeout=max(args.timeout * 4, 900.0),
                cwd=ROOT,
            )
            built = build.returncode == 0
            if not _record(
                checks,
                "image_build",
                built,
                "built" if built else (build.stderr or "").strip()[-1500:],
            ):
                return _finish(checks, image, port)
        elif not args.image:
            _record(checks, "image_present", False, "--no-build requires --image")
            return _finish(checks, image, port)

        _run(["docker", "rm", "-f", container], timeout=60)
        env_flags = ["-e", f"PORT={port}"]
        demo_mode = args.demo
        for item in args.env:
            key, _, value = item.partition("=")
            if key:
                env_flags.extend(["-e", f"{key}={value}"])
                if key == "DEMO_MODE":
                    demo_mode = value.strip().lower() in {"1", "true", "yes", "on"}
        if not any(item.startswith("DEBUG=") for item in args.env):
            env_flags.extend(["-e", "DEBUG=false" if demo_mode else "DEBUG=true"])
        if not any(item.startswith("CORS_ORIGINS=") for item in args.env):
            # Same-origin dashboard; keeps DEBUG=false startup validation quiet
            # without weakening the explicit-origin requirement in production.
            env_flags.extend(["-e", f"CORS_ORIGINS=http://127.0.0.1:{port}"])

        run = _run(
            [
                "docker",
                "run",
                "-d",
                "--name",
                container,
                "-p",
                f"127.0.0.1:{port}:{port}",
                *env_flags,
                image,
            ],
            timeout=120,
        )
        started = run.returncode == 0
        if not _record(checks, "container_start", started, (run.stdout or run.stderr).strip()):
            return _finish(checks, image, port)

        base = f"http://127.0.0.1:{port}"
        healthy, detail = _wait_for_health(base, args.timeout)
        if not _record(checks, "health_on_injected_port", healthy, detail):
            _record(checks, "container_logs", False, _container_logs(container))
            return _finish(checks, image, port)

        try:
            ready_status, ready_body = _http(f"{base}/api/ready", timeout=10.0)
        except (urllib.error.URLError, TimeoutError, ConnectionError, OSError) as exc:
            ready_status, ready_body = 0, f"{type(exc).__name__}: {exc}"
        try:
            ready_payload = json.loads(ready_body)
        except json.JSONDecodeError:
            ready_payload = {}
        ready_ok = ready_status == 200 if args.require_ready else bool(ready_payload.get("status"))
        _record(
            checks,
            "ready_probe",
            ready_ok,
            f"HTTP {ready_status} status={ready_payload.get('status', 'unknown')}",
        )

        if demo_mode:
            for method, path, label in (
                ("POST", "/api/jobs", "demo_blocks_job_submission"),
                ("DELETE", "/api/system/cache", "demo_blocks_cache_admin"),
            ):
                body = b'{"module": "docking", "disease_id": "sle"}' if method == "POST" else None
                try:
                    status, payload = _http(f"{base}{path}", method=method, body=body)
                except (urllib.error.URLError, TimeoutError, ConnectionError, OSError) as exc:
                    status, payload = 0, f"{type(exc).__name__}: {exc}"
                blocked = status == 403 and "demo_read_only" in payload
                _record(checks, label, blocked, f"HTTP {status}: {payload.strip()[:200]}")

        return _finish(checks, image, port)
    finally:
        if started and not args.keep:
            _run(["docker", "rm", "-f", container], timeout=120)
        if built and not args.keep:
            _run(["docker", "rmi", "-f", image], timeout=120)


def _finish(checks: list[dict[str, Any]], image: str, port: int) -> int:
    ok = bool(checks) and all(check["ok"] for check in checks)
    print(json.dumps({"ok": ok, "image": image, "port": port, "checks": checks}, indent=2))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
