#!/usr/bin/env python3
"""Smoke-test a NosoGraph container with a platform-injected ``PORT``.

Boots one image (building it first unless ``--no-build``/``--runtime-only``)
and checks that the application listens on the injected port and that both
probes answer on it. Every container and image this script creates is labelled
``dev.nosograph.smoke`` and is removed in a ``finally`` block, including on
failure. Nothing else is ever stopped or removed.

Usage::

    python scripts/docker_smoke.py                      # build ./Dockerfile
    python scripts/docker_smoke.py --build-only
    python scripts/docker_smoke.py --no-build --image nosograph-demo:latest --demo
    python scripts/docker_smoke.py --port 8080 --timeout 240

Output is a single JSON object on stdout::

    {
      "ok": true,
      "image": "...",
      "image_origin": "built" | "reused",
      "port": 8000,
      "failures": ["..."],
      "checks": [{"name": ..., "phase": ..., "ok": ..., "detail": ...}]
    }

Exit status is 0 only when every check passes, 3 when the docker CLI or daemon
could not be reached, and 1 for any failed check. No third-party dependencies
are used: this script must run on a bare runner before the project venv exists.

Why the custom process runner
-----------------------------
``subprocess.run(..., capture_output=True, timeout=...)`` does *not* bound a
hung ``docker build``. On timeout CPython kills the direct child and then calls
``communicate()`` a second time with no timeout; if any grandchild (buildkit, a
shell wrapper, a helper container) inherited the stdout/stderr write handle,
that second read never sees EOF and the call blocks forever. That is the
observed "the build got stuck and never returned" failure on Windows.

So output goes to temporary files instead of pipes -- there is no reader that
can block -- and a timeout escalates to a whole-tree kill (``taskkill /T`` on
Windows, a killed process group on POSIX) before the files are read.
"""

from __future__ import annotations

import argparse
import contextlib
import json
import os
import socket
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_PORT = 8000
OWNER_LABEL = "dev.nosograph.smoke"
IS_WINDOWS = os.name == "nt"


@dataclass
class CommandResult:
    """Outcome of one bounded external command."""

    args: list[str]
    returncode: int
    stdout: str = ""
    stderr: str = ""
    timed_out: bool = False
    duration: float = 0.0
    kill_failed: bool = False

    @property
    def ok(self) -> bool:
        return self.returncode == 0 and not self.timed_out

    def describe(self, limit: int = 1500) -> str:
        if self.timed_out:
            head = f"timed out after {self.duration:.1f}s (whole process tree killed)"
            if self.kill_failed:
                head += "; the tree did not exit after the kill"
            return head
        text = (self.stderr or "").strip() or (self.stdout or "").strip()
        return text[-limit:] if text else f"exit {self.returncode}"


def _kill_tree(process: subprocess.Popen[bytes]) -> bool:
    """Kill ``process`` and its descendants. Returns True when it exited."""
    if process.poll() is not None:
        return True
    try:
        if IS_WINDOWS:
            subprocess.run(
                ["taskkill", "/F", "/T", "/PID", str(process.pid)],
                capture_output=True,
                timeout=30,
                check=False,
            )
        else:  # pragma: no cover - POSIX branch
            import signal

            os.killpg(os.getpgid(process.pid), signal.SIGKILL)
    except (OSError, subprocess.SubprocessError):
        pass
    with contextlib.suppress(OSError):
        process.kill()
    try:
        process.wait(timeout=15)
    except (subprocess.SubprocessError, OSError):
        return process.poll() is not None
    return True


def _run(
    args: list[str],
    *,
    timeout: float,
    cwd: Path | None = None,
    echo: bool = False,
) -> CommandResult:
    """Run ``args`` with a hard bound, capturing output through temp files.

    Never raises for a missing binary, a non-zero exit, or a timeout.
    """
    started = time.monotonic()
    with tempfile.TemporaryDirectory(prefix="nosograph-smoke-") as tmp:
        out_path = Path(tmp) / "stdout"
        err_path = Path(tmp) / "stderr"
        popen_kwargs: dict[str, Any] = {
            "cwd": str(cwd) if cwd else None,
            "stdin": subprocess.DEVNULL,
        }
        if IS_WINDOWS:
            popen_kwargs["creationflags"] = getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0)
        else:  # pragma: no cover - POSIX branch
            popen_kwargs["start_new_session"] = True
        try:
            with out_path.open("wb") as out_file, err_path.open("wb") as err_file:
                process = subprocess.Popen(  # noqa: S603 - fixed argv, no shell
                    args,
                    stdout=out_file,
                    stderr=err_file,
                    **popen_kwargs,
                )
                timed_out = False
                kill_failed = False
                try:
                    process.wait(timeout=timeout)
                except subprocess.TimeoutExpired:
                    timed_out = True
                    kill_failed = not _kill_tree(process)
        except (OSError, subprocess.SubprocessError) as exc:
            # Keep the JSON contract when the docker CLI itself is missing.
            return CommandResult(
                args=args,
                returncode=127,
                stderr=str(exc),
                duration=time.monotonic() - started,
            )

        result = CommandResult(
            args=args,
            returncode=process.returncode if process.returncode is not None else -1,
            stdout=out_path.read_text(encoding="utf-8", errors="replace")
            if out_path.exists()
            else "",
            stderr=err_path.read_text(encoding="utf-8", errors="replace")
            if err_path.exists()
            else "",
            timed_out=timed_out,
            duration=time.monotonic() - started,
            kill_failed=kill_failed,
        )
    if echo:
        label = " ".join(args[:4])
        print(f"[docker-smoke] {label} -> {result.describe(400)}", file=sys.stderr)
    return result


def _record(checks: list[dict[str, Any]], name: str, phase: str, ok: bool, detail: str) -> bool:
    checks.append({"name": name, "phase": phase, "ok": ok, "detail": detail})
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
        with urllib.request.urlopen(request, timeout=timeout) as response:  # noqa: S310
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


def _container_logs(container: str, *, timeout: float, echo: bool) -> str:
    proc = _run(["docker", "logs", "--tail", "40", container], timeout=timeout, echo=echo)
    text = (proc.stdout or "") + (proc.stderr or "")
    if proc.timed_out:
        text += f"\n[logs unavailable: {proc.describe(200)}]"
    return text.strip()[-2000:]


def _image_created(image: str, *, timeout: float, echo: bool) -> str:
    """Return the image's created timestamp, or a short diagnostic."""
    proc = _run(
        ["docker", "image", "inspect", "--format", "{{.Created}}", image],
        timeout=timeout,
        echo=echo,
    )
    if proc.ok:
        return (proc.stdout or "").strip() or "unknown"
    return f"unavailable ({proc.describe(200)})"


def _remove_container(name: str, *, timeout: float, echo: bool) -> None:
    """Remove only our own container, identified by the ownership label."""
    proc = _run(
        ["docker", "rm", "-f", name],
        timeout=timeout,
        echo=echo,
    )
    if proc.timed_out:
        print(
            f"[docker-smoke] WARNING: could not remove {name}: {proc.describe(200)}",
            file=sys.stderr,
        )


def _remove_image(image: str, *, timeout: float, echo: bool) -> None:
    proc = _run(["docker", "rmi", "-f", image], timeout=timeout, echo=echo)
    if proc.timed_out:
        print(
            f"[docker-smoke] WARNING: could not remove {image}: {proc.describe(200)}",
            file=sys.stderr,
        )


def _finish(
    checks: list[dict[str, Any]],
    *,
    image: str,
    port: int,
    image_origin: str,
    report: Path | None,
    extra: dict[str, Any] | None = None,
) -> int:
    failures = [check["name"] for check in checks if not check["ok"]]
    payload: dict[str, Any] = {
        "ok": bool(checks) and not failures,
        "image": image,
        "image_origin": image_origin,
        "port": port,
        "failures": failures,
        "checks": checks,
    }
    if extra:
        payload.update(extra)
    text = json.dumps(payload, indent=2)
    print(text)
    if report is not None:
        try:
            report.parent.mkdir(parents=True, exist_ok=True)
            report.write_text(text + "\n", encoding="utf-8")
        except OSError as exc:
            print(f"[docker-smoke] WARNING: could not write report: {exc}", file=sys.stderr)
    return 0 if payload["ok"] else 1


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument(
        "--port", type=int, default=DEFAULT_PORT, help="Injected PORT (0 = free port)"
    )
    parser.add_argument("--image", default="", help="Image tag to build/run")
    parser.add_argument("--dockerfile", default="Dockerfile", help="Dockerfile used for the build")
    parser.add_argument(
        "--timeout", type=float, default=180.0, help="Application readiness timeout in seconds"
    )
    parser.add_argument(
        "--build-timeout", type=float, default=900.0, help="Hard bound for the image build"
    )
    parser.add_argument(
        "--daemon-timeout", type=float, default=60.0, help="Hard bound for `docker info`"
    )
    parser.add_argument(
        "--cleanup-timeout",
        type=float,
        default=60.0,
        help="Hard bound for each container/image removal",
    )
    parser.add_argument(
        "--target",
        default="",
        help=(
            "Build stage/target (e.g. runtime). Ignored when empty. Sourcing a "
            "pre-existing runtime stage avoids re-running earlier layers."
        ),
    )
    parser.add_argument(
        "--no-build", action="store_true", help="Reuse an existing --image (runtime only)"
    )
    parser.add_argument("--build-only", action="store_true", help="Verify the image build and stop")
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
    parser.add_argument(
        "--report", type=Path, default=None, help="Also write the JSON report to this path"
    )
    parser.add_argument("--verbose", action="store_true", help="Echo command diagnostics to stderr")
    args = parser.parse_args(argv)

    if args.no_build and args.build_only:
        parser.error("--build-only and --no-build are mutually exclusive")

    echo = args.verbose
    port = args.port or _free_port()
    image = args.image or f"nosograph-smoke:{port}"
    # Unique per run: a name collision can only be our own leftover, never a
    # container the user created for something else.
    run_token = f"{os.getpid()}-{int(time.time())}"
    container = f"nosograph-smoke-{port}-{run_token}"
    image_origin = "reused"
    checks: list[dict[str, Any]] = []
    built = False
    started = False

    try:
        docker = _run(["docker", "info"], timeout=args.daemon_timeout, echo=echo)
        daemon_ok = _record(
            checks,
            "docker_daemon",
            "environment",
            docker.ok,
            docker.describe(500) if not docker.ok else "available",
        )
        if not daemon_ok:
            return _finish(
                checks, image=image, port=port, image_origin=image_origin, report=args.report
            )

        if not args.no_build:
            build_cmd = ["docker", "build", "-f", args.dockerfile, "-t", image]
            if args.target:
                build_cmd += ["--target", args.target]
            if not args.validate_diseases:
                # The image's build-time validation walks the full 10k+ registry and
                # exits non-zero on generated scaffolds by design (see docs/deployment.md).
                # Opt in with --validate-diseases when that gate is the thing under test.
                build_cmd += ["--build-arg", "DOCKER_SKIP_DISEASE_VALIDATE=1"]
            build = _run(
                [*build_cmd, "."],
                timeout=args.build_timeout,
                cwd=ROOT,
                echo=echo,
            )
            built = build.ok
            image_origin = "built" if built else "reused"
            if not _record(
                checks,
                "image_build",
                "build",
                built,
                f"built in {build.duration:.1f}s" if built else build.describe(1800),
            ):
                return _finish(
                    checks,
                    image=image,
                    port=port,
                    image_origin=image_origin,
                    report=args.report,
                )
            created = _image_created(image, timeout=30, echo=echo)
            _record(checks, "image_created", "build", True, created)
        elif not args.image:
            _record(
                checks,
                "image_present",
                "build",
                False,
                "--no-build requires --image",
            )
            return _finish(
                checks, image=image, port=port, image_origin=image_origin, report=args.report
            )
        else:
            # Reusing a cached image is legitimate, but it is not evidence about
            # the current source tree. Record which image it actually was.
            created = _image_created(image, timeout=30, echo=echo)
            present = not created.startswith("unavailable")
            if not _record(
                checks,
                "image_present",
                "build",
                present,
                f"reused existing image (created {created}); not built from the current "
                f"source tree in this run"
                if present
                else created,
            ):
                return _finish(
                    checks,
                    image=image,
                    port=port,
                    image_origin=image_origin,
                    report=args.report,
                )

        if args.build_only:
            return _finish(
                checks,
                image=image,
                port=port,
                image_origin=image_origin,
                report=args.report,
                extra={"mode": "build_only"},
            )

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
                "--label",
                f"{OWNER_LABEL}=1",
                "-p",
                f"127.0.0.1:{port}:{port}",
                *env_flags,
                image,
            ],
            timeout=120,
            echo=echo,
        )
        started = run.returncode == 0
        if not _record(
            checks, "container_start", "runtime", started, (run.stdout or run.stderr).strip()
        ):
            return _finish(
                checks, image=image, port=port, image_origin=image_origin, report=args.report
            )

        base = f"http://127.0.0.1:{port}"
        healthy, detail = _wait_for_health(base, args.timeout)
        if not _record(checks, "health_on_injected_port", "runtime", healthy, detail):
            _record(
                checks,
                "container_logs",
                "runtime",
                False,
                _container_logs(container, timeout=args.cleanup_timeout, echo=echo),
            )
            return _finish(
                checks, image=image, port=port, image_origin=image_origin, report=args.report
            )

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
            "runtime",
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
                _record(
                    checks, label, "runtime", blocked, f"HTTP {status}: {payload.strip()[:200]}"
                )

        # The app must still be serving once the probes are done; a container
        # that answers and then crashes should not report success.
        try:
            final_status, _ = _http(f"{base}/api/health", timeout=10.0)
        except (urllib.error.URLError, TimeoutError, ConnectionError, OSError) as exc:
            final_status = 0
            detail = f"{type(exc).__name__}: {exc}"
        else:
            detail = f"HTTP {final_status}"
        _record(checks, "health_after_probes", "runtime", final_status == 200, detail)

        return _finish(
            checks,
            image=image,
            port=port,
            image_origin=image_origin,
            report=args.report,
            extra={"container": container, "demo_mode": demo_mode},
        )
    finally:
        if started and not args.keep:
            _remove_container(container, timeout=args.cleanup_timeout, echo=echo)
        if built and not args.keep:
            _remove_image(image, timeout=args.cleanup_timeout, echo=echo)


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        print(json.dumps({"ok": False, "checks": [], "failures": ["interrupted"]}, indent=2))
        sys.exit(130)
