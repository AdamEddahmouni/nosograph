"""Capture visual-baseline screenshots of the two NosoGraph surfaces.

Surfaces
--------
- ``docs``: the MkDocs documentation site. Built once with ``mkdocs build``
  and served statically (deterministic; no livereload).
- ``app``: the local FastAPI dashboard (``med_research.cli serve``). ``.env``
  is loaded into the server process environment first — the app refuses to
  start with ``DEBUG=false`` and no ``API_KEY``.

Screenshots are PNG plus a ``manifest.json`` recording URL, viewport, byte
size, and SHA-1 per capture, plus any skipped captures and why. Nothing is
written into the repository when ``--out-dir`` points outside it; the default
out-dir lives under the git-ignored ``test-artifacts/browser/`` tree.

Usage:
    python scripts/capture_visual_baseline.py --surface all --out-dir <dir>
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import sys
import tempfile
import threading
import time
import urllib.request
from dataclasses import dataclass, field
from datetime import UTC, datetime
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUT_DIR = REPO_ROOT / "test-artifacts" / "browser" / "visual-baseline"
ENV_PATH = REPO_ROOT / ".env"

HEALTH_PATH = "/api/health"
CONDITION_SEARCH_PATH = "/api/v1/conditions/search"


@dataclass(frozen=True)
class Shot:
    """One screenshot target."""

    name: str
    path: str
    width: int
    height: int = 900
    full_page: bool = True
    wait_selector: str | None = None
    settle_ms: int = 600
    click_selector: str | None = None  # optional interaction before capturing
    result_selector: str | None = None  # waited on after the click


DOCS_SHOTS: tuple[Shot, ...] = (
    Shot("docs-landing-1440", "/", 1440),
    Shot("docs-landing-375", "/", 375, height=812),
    Shot("docs-long-registry-1440", "/concepts/registry/", 1440),
    Shot("docs-architecture-1440", "/architecture/overview/", 1440),
    Shot("docs-research-sle-1440", "/research/sle/", 1440),
)

APP_SHOTS: tuple[Shot, ...] = (
    Shot("app-dashboard-1440", "/", 1440),
    Shot("app-dashboard-375", "/", 375, height=812),
    # Mobile nav disclosure open state (Stage 4: Esc/focus-return behavior).
    Shot(
        "app-dashboard-375-nav-open",
        "/",
        375,
        height=812,
        full_page=False,
        click_selector="#nav-toggle",
        result_selector="#nav-menu.is-open",
    ),
    Shot("app-satellite-pgx-1440", "/pgx.html", 1440),
)


@dataclass
class CaptureRecord:
    name: str
    url: str
    viewport: str
    file: str
    bytes: int
    sha1: str


@dataclass
class Manifest:
    surface: str
    captures: list[CaptureRecord] = field(default_factory=list)
    skipped: list[dict[str, str]] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)
    created_at: str = field(default_factory=lambda: datetime.now(UTC).isoformat(timespec="seconds"))

    def to_dict(self) -> dict[str, Any]:
        return {
            "surface": self.surface,
            "created_at": self.created_at,
            "captures": [vars(c) for c in self.captures],
            "skipped": self.skipped,
            "notes": self.notes,
        }


def load_env_file(path: Path) -> dict[str, str]:
    """Parse a dotenv file (UTF-8 BOM tolerated) into a dict."""
    values: dict[str, str] = {}
    if not path.is_file():
        return values
    for raw in path.read_text(encoding="utf-8-sig").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        values[key.strip()] = value.strip().strip('"').strip("'")
    return values


def wait_for_url(url: str, *, timeout_s: float = 90.0) -> None:
    """Poll until ``url`` answers with HTTP 200 or raise TimeoutError."""
    deadline = time.monotonic() + timeout_s
    last_error: Exception | None = None
    while time.monotonic() < deadline:
        try:
            with urllib.request.urlopen(url, timeout=5) as response:  # noqa: S310
                if response.status == 200:
                    return
        except Exception as exc:  # noqa: BLE001 - report whatever refused us
            last_error = exc
        time.sleep(1.0)
    raise TimeoutError(f"{url} did not return HTTP 200 within {timeout_s:.0f}s: {last_error}")


def fetch_json(url: str, *, timeout_s: float = 15.0) -> dict[str, Any] | None:
    try:
        with urllib.request.urlopen(url, timeout=timeout_s) as response:  # noqa: S310
            return json.loads(response.read().decode("utf-8"))
    except Exception:  # noqa: BLE001 - discovery is best-effort
        return None


class _QuietHandler(SimpleHTTPRequestHandler):
    def log_message(self, _format: str, *_args: object) -> None:
        return


def build_docs_site(work_dir: Path) -> Path:
    """Build the MkDocs site into ``work_dir/site`` and return that path."""
    site_dir = work_dir / "site"
    subprocess.run(
        [sys.executable, "-m", "mkdocs", "build", "--clean", "--site-dir", str(site_dir)],
        cwd=REPO_ROOT,
        check=True,
    )
    return site_dir


def serve_static(site_dir: Path, port: int) -> ThreadingHTTPServer:
    handler = lambda *args, **kwargs: _QuietHandler(  # noqa: E731
        *args, directory=str(site_dir), **kwargs
    )
    server = ThreadingHTTPServer(("127.0.0.1", port), handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    return server


def start_app_server(port: int, log_path: Path) -> subprocess.Popen[bytes]:
    env = os.environ.copy()
    env.update(load_env_file(ENV_PATH))
    # Baseline captures load several dashboard pages back-to-back from
    # 127.0.0.1; the default per-IP limiter (60/min) 429s later page loads.
    # Local one-shot server only — this never leaves the capture process.
    env["RATE_LIMIT_REQUESTS"] = "0"
    log_handle = log_path.open("wb")
    proc = subprocess.Popen(  # noqa: S603
        [
            sys.executable,
            "-m",
            "med_research.cli",
            "serve",
            "--host",
            "127.0.0.1",
            "--port",
            str(port),
        ],
        cwd=REPO_ROOT,
        env=env,
        stdout=log_handle,
        stderr=subprocess.STDOUT,
    )
    return proc


def stop_app_server(proc: subprocess.Popen[bytes]) -> None:
    proc.terminate()
    try:
        proc.wait(timeout=15)
    except subprocess.TimeoutExpired:
        proc.kill()
        proc.wait(timeout=10)


def discover_condition_curies(base_url: str, *, count: int = 2) -> list[str]:
    """Ask the running app for real condition CURIEs (no fabricated data)."""
    payload = fetch_json(f"{base_url}{CONDITION_SEARCH_PATH}?q=a&limit={count * 5}")
    if not payload:
        return []
    items = payload.get("items") or payload.get("results") or []
    curies: list[str] = []
    for item in items:
        if isinstance(item, dict):
            curie = str(item.get("curie") or "")
            if curie and curie not in curies:
                curies.append(curie)
        if len(curies) >= count:
            break
    return curies


def _trigger_scroll_reveals(page: Any) -> None:
    """Scroll through the page so IntersectionObserver-gated reveals fire before
    a full-page screenshot (which would otherwise race the observer callbacks)."""
    page.evaluate(
        """async () => {
            const step = Math.max(200, Math.floor(window.innerHeight * 0.6));
            for (let y = 0; y <= document.body.scrollHeight; y += step) {
                window.scrollTo(0, y);
                await new Promise((resolve) => setTimeout(resolve, 60));
            }
            window.scrollTo(0, 0);
        }"""
    )


def _shoot(page: Any, shot: Shot, url: str, out_dir: Path) -> CaptureRecord:
    page.set_viewport_size({"width": shot.width, "height": shot.height})
    page.goto(url, wait_until="networkidle", timeout=60_000)
    if shot.wait_selector:
        page.wait_for_selector(shot.wait_selector, timeout=30_000)
    if shot.click_selector:
        page.click(shot.click_selector, timeout=15_000)
        if shot.result_selector:
            page.wait_for_selector(shot.result_selector, timeout=60_000)
    if shot.full_page:
        _trigger_scroll_reveals(page)
    page.wait_for_timeout(shot.settle_ms)
    target = out_dir / f"{shot.name}.png"
    page.screenshot(path=str(target), full_page=shot.full_page, animations="disabled")
    data = target.read_bytes()
    return CaptureRecord(
        name=shot.name,
        url=url,
        viewport=f"{shot.width}x{shot.height}",
        file=str(target),
        bytes=len(data),
        sha1=hashlib.sha1(data).hexdigest(),
    )


def capture_docs(base_url: str, out_dir: Path, manifest: Manifest) -> None:
    from playwright.sync_api import sync_playwright

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        try:
            page = browser.new_page()
            for shot in DOCS_SHOTS:
                record = _shoot(page, shot, f"{base_url}{shot.path}", out_dir)
                _record(manifest, record)
        finally:
            browser.close()


def capture_app(base_url: str, out_dir: Path, manifest: Manifest) -> None:
    from playwright.sync_api import sync_playwright

    shots = list(APP_SHOTS)
    curies = discover_condition_curies(base_url)
    if curies:
        shots.append(
            Shot(
                "app-condition-explorer-1440",
                f"/?curie={curies[0]}",
                1440,
                wait_selector=".condition-explorer-body",
                settle_ms=1500,
            )
        )
    else:
        _skip(
            manifest,
            "app-condition-explorer-1440",
            "no condition CURIEs returned by /api/v1/conditions/search",
        )
    if len(curies) >= 2:
        shots.append(
            Shot(
                "app-compare-1440",
                f"/?left={curies[0]}&right={curies[1]}",
                1440,
                wait_selector="#condition-comparison-panel",
                settle_ms=1500,
                click_selector="#comparison-run-btn",
                result_selector=".condition-comparison-report-header",
            )
        )
    else:
        _skip(
            manifest,
            "app-compare-1440",
            "fewer than two condition CURIEs available for comparison deep link",
        )

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        try:
            page = browser.new_page()
            for shot in shots:
                record = _shoot(page, shot, f"{base_url}{shot.path}", out_dir)
                _record(manifest, record)
        finally:
            browser.close()


def run_docs(port: int, out_dir: Path, manifest: Manifest) -> None:
    with tempfile.TemporaryDirectory(prefix="ng-docs-site-") as work:
        print("building MkDocs site …")
        site_dir = build_docs_site(Path(work))
        server = serve_static(site_dir, port)
        base_url = f"http://127.0.0.1:{port}"
        try:
            wait_for_url(f"{base_url}/")
            print(f"serving docs at {base_url}")
            capture_docs(base_url, out_dir, manifest)
        finally:
            server.shutdown()
            server.server_close()


def run_app(port: int, out_dir: Path, manifest: Manifest) -> None:
    log_path = out_dir / "app-server.log"
    proc = start_app_server(port, log_path)
    base_url = f"http://127.0.0.1:{port}"
    try:
        wait_for_url(f"{base_url}{HEALTH_PATH}")
        print(f"app healthy at {base_url} (log: {log_path})")
        capture_app(base_url, out_dir, manifest)
    finally:
        stop_app_server(proc)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--surface",
        choices=("docs", "app", "all"),
        default="all",
        help="Which surface to capture (default: all)",
    )
    parser.add_argument(
        "--out-dir",
        type=Path,
        default=DEFAULT_OUT_DIR,
        help="Directory for PNGs + manifest.json (default: %(default)s)",
    )
    parser.add_argument("--docs-port", type=int, default=8001)
    parser.add_argument("--app-port", type=int, default=8000)
    return parser.parse_args(argv)


def _load_manifest(path: Path, *, surface: str) -> Manifest:
    """Merge with an existing manifest so separate docs/app runs accumulate."""
    manifest = Manifest(surface=surface)
    if not path.is_file():
        return manifest
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return manifest
    for raw in data.get("captures", []):
        try:
            manifest.captures.append(CaptureRecord(**raw))
        except TypeError:
            continue
    manifest.skipped.extend(data.get("skipped", []))
    manifest.notes.extend(data.get("notes", []))
    return manifest


def _record(manifest: Manifest, record: CaptureRecord) -> None:
    manifest.captures = [c for c in manifest.captures if c.name != record.name]
    manifest.skipped = [s for s in manifest.skipped if s.get("name") != record.name]
    manifest.captures.append(record)
    print(f"  captured {record.name} ({record.bytes} bytes)")


def _skip(manifest: Manifest, name: str, reason: str) -> None:
    if any(c.name == name for c in manifest.captures):
        return  # keep the earlier successful capture
    manifest.skipped = [s for s in manifest.skipped if s.get("name") != name]
    manifest.skipped.append({"name": name, "reason": reason})
    print(f"  skipped {name}: {reason}")


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    out_dir: Path = args.out_dir
    out_dir.mkdir(parents=True, exist_ok=True)
    manifest_path = out_dir / "manifest.json"
    manifest = _load_manifest(manifest_path, surface=args.surface)
    if args.surface in ("docs", "all"):
        run_docs(args.docs_port, out_dir, manifest)
    if args.surface in ("app", "all"):
        run_app(args.app_port, out_dir, manifest)
    manifest_path.write_text(json.dumps(manifest.to_dict(), indent=2) + "\n", encoding="utf-8")
    print(f"\n{len(manifest.captures)} captures, {len(manifest.skipped)} skipped")
    print(f"manifest: {manifest_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
