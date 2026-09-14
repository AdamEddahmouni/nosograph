"""Browser tests for the MkDocs docs homepage motion gating.

The committed docs site is built once per session (``mkdocs build``) and
served statically — no livereload, no network. These tests pin the
reduced-motion contract of the landing page:

- ``html.ng-motion`` (which gates the scroll-reveal hiding rules) is added
  ONLY when the user has not requested reduced motion;
- reveal-gated sections render fully visible immediately under reduced
  motion — information never depends on animation;
- CSS animation/transition durations collapse to ~0 under reduced motion
  (base.css kill switch), including the hero's ambient drift and entrance
  stagger;
- with motion allowed, the entrance duration consumes the ``--ng-slow``
  design token (320 ms).
"""

from __future__ import annotations

import subprocess
import sys
import tempfile
import threading
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import pytest

playwright = pytest.importorskip("playwright.sync_api")
pytest.importorskip("mkdocs")

Browser = playwright.Browser
Page = playwright.Page
sync_playwright = playwright.sync_playwright

PROJECT_ROOT = Path(__file__).parents[1]

pytestmark = [pytest.mark.slow, pytest.mark.browser]


@pytest.fixture(scope="session")
def docs_server() -> str:
    """Build the MkDocs site once and serve it statically for the session."""
    with tempfile.TemporaryDirectory(prefix="ng-docs-a11y-") as work:
        site_dir = Path(work) / "site"
        subprocess.run(
            [
                sys.executable,
                "-m",
                "mkdocs",
                "build",
                "--clean",
                "--site-dir",
                str(site_dir),
            ],
            cwd=PROJECT_ROOT,
            check=True,
            capture_output=True,
            text=True,
        )

        def _handler(*args, **kwargs):
            return SimpleHTTPRequestHandler(*args, directory=str(site_dir), **kwargs)

        server = ThreadingHTTPServer(("127.0.0.1", 0), _handler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            yield f"http://127.0.0.1:{server.server_address[1]}"
        finally:
            server.shutdown()
            thread.join(timeout=5)
            server.server_close()


@pytest.fixture(scope="session")
def browser() -> Browser:
    # Repo convention: one session browser per browser-test module. Note this
    # makes browser modules mutually exclusive within a single pytest process
    # (a second sync_playwright() raises "Sync API inside the asyncio loop"
    # while another module's session browser is alive) — run browser modules
    # in separate invocations, as the verification gates do. The skip here
    # degrades that situation gracefully instead of erroring.
    try:
        with sync_playwright() as playwright_context:
            browser = playwright_context.chromium.launch(headless=True)
            yield browser
            browser.close()
    except Exception as exc:
        pytest.skip(f"Playwright Chromium is not available: {exc}")


@pytest.fixture
def page(browser: Browser) -> Page:
    context = browser.new_context()
    page = context.new_page()
    try:
        yield page
    finally:
        context.close()


@pytest.fixture
def reduced_page(browser: Browser) -> Page:
    context = browser.new_context(reduced_motion="reduce")
    page = context.new_page()
    try:
        yield page
    finally:
        context.close()


def _max_seconds(raw: str) -> float:
    """Parse a (possibly comma-separated) computed CSS time list to seconds."""
    values = []
    for part in raw.split(","):
        part = part.strip().lower()
        if not part:
            continue
        values.append(float(part[:-2]) / 1000.0 if part.endswith("ms") else float(part.rstrip("s")))
    return max(values, default=0.0)


def test_docs_home_reveal_gating_follows_motion_preference(page: Page, docs_server: str) -> None:
    page.goto(f"{docs_server}/", wait_until="domcontentloaded")
    # Motion allowed: home.js adds html.ng-motion, hiding unrevealed sections…
    page.wait_for_function("() => document.documentElement.classList.contains('ng-motion')")
    # Adding the gate transitions not-yet-revealed shells 1→0; wait for that
    # fade-out to settle before asserting the hidden state.
    page.wait_for_function(
        """() => [...document.querySelectorAll('.ng-homepage section:not(.ng-hero) > .ng-shell')]
            .some(e => getComputedStyle(e).opacity === '0')"""
    )
    hidden = page.locator(".ng-homepage section:not(.ng-hero) > .ng-shell").evaluate_all(
        "els => els.filter(e => getComputedStyle(e).opacity === '0').length"
    )
    assert hidden > 0
    # …and scrolling reveals every section (IntersectionObserver).
    page.evaluate(
        """async () => {
            const step = Math.max(200, Math.floor(window.innerHeight * 0.6));
            for (let y = 0; y <= document.body.scrollHeight; y += step) {
                window.scrollTo(0, y);
                await new Promise((resolve) => setTimeout(resolve, 50));
            }
        }"""
    )
    page.wait_for_function(
        """() => [...document.querySelectorAll('.ng-homepage section:not(.ng-hero)')]
            .every(s => s.classList.contains('is-visible'))"""
    )


def test_docs_home_reduced_motion_never_hides_content(reduced_page: Page, docs_server: str) -> None:
    reduced_page.goto(f"{docs_server}/", wait_until="domcontentloaded")
    # home.js must not add the gating class under reduced motion. The class is
    # added synchronously at parse time when allowed, so its absence after
    # domcontentloaded + a settle window is deterministic.
    reduced_page.wait_for_timeout(500)
    assert (
        reduced_page.evaluate("() => document.documentElement.classList.contains('ng-motion')")
        is False
    )
    opacities = reduced_page.locator(".ng-homepage section > .ng-shell").evaluate_all(
        "els => els.map(e => getComputedStyle(e).opacity)"
    )
    assert opacities, "expected homepage sections"
    assert all(o == "1" for o in opacities)


def test_docs_home_reduced_motion_kills_animation_durations(
    reduced_page: Page, docs_server: str
) -> None:
    reduced_page.goto(f"{docs_server}/", wait_until="domcontentloaded")
    # Hero entrance stagger (applies regardless of the ng-motion gate)…
    rise = reduced_page.evaluate(
        "() => getComputedStyle(document.querySelector('.ng-hero-copy > *')).animationDuration"
    )
    assert _max_seconds(rise) < 0.05
    # …and the ambient hero drift (pseudo-element) both collapse to ~0.
    ambient = reduced_page.evaluate(
        "() => getComputedStyle(document.querySelector('.ng-hero'), '::after').animationDuration"
    )
    assert _max_seconds(ambient) < 0.05


def test_docs_home_entrance_consumes_slow_motion_token(page: Page, docs_server: str) -> None:
    page.goto(f"{docs_server}/", wait_until="domcontentloaded")
    rise = page.evaluate(
        "() => getComputedStyle(document.querySelector('.ng-hero-copy > *')).animationDuration"
    )
    assert abs(_max_seconds(rise) - 0.32) < 0.001  # --ng-slow
