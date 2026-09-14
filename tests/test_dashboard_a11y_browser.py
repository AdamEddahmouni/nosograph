"""Browser a11y regression tests for the dashboard and satellite pages.

These tests serve committed static HTML/CSS (no Redis, Celery, or live APIs).
They do not re-assert :focus-visible CSS, which is covered statically.
"""

from __future__ import annotations

import threading
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlsplit

import pytest

playwright = pytest.importorskip("playwright.sync_api")

Browser = playwright.Browser
Page = playwright.Page
expect = playwright.expect
sync_playwright = playwright.sync_playwright

PROJECT_ROOT = Path(__file__).parents[1]
STATIC_DIR = PROJECT_ROOT / "src" / "med_research" / "web" / "static"

pytestmark = [pytest.mark.slow, pytest.mark.browser]

SATELLITES = (
    "agent.html",
    "lead_opt.html",
    "patient_matching.html",
    "pgx.html",
    "spatial.html",
)


class _StaticHandler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(STATIC_DIR), **kwargs)

    def translate_path(self, path):
        parsed_path = urlsplit(path).path
        if parsed_path.startswith("/lib/"):
            return str(PROJECT_ROOT / parsed_path.lstrip("/"))
        return super().translate_path(path)

    def log_message(self, _format, *_args):
        return


@pytest.fixture(scope="session")
def static_server() -> str:
    server = ThreadingHTTPServer(("127.0.0.1", 0), _StaticHandler)
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


def test_dashboard_skip_link_keyboard_and_landmarks(page: Page, static_server: str) -> None:
    page.goto(f"{static_server}/index.html", wait_until="domcontentloaded")
    expect(page.locator(".skip-link")).to_have_attribute("href", "#main-content")
    page.keyboard.press("Tab")
    focused = page.evaluate("() => document.activeElement && document.activeElement.className")
    assert focused == "skip-link"
    page.keyboard.press("Enter")
    page.wait_for_function(
        "() => document.activeElement && document.activeElement.id === 'main-content'"
    )
    expect(page.locator("header")).to_be_visible()
    expect(page.locator("nav.top-nav")).to_be_visible()
    expect(page.locator("main#main-content")).to_be_visible()
    expect(page.locator("footer")).to_be_attached()


def test_named_logos_and_icon_only_accessible_names(page: Page, static_server: str) -> None:
    page.goto(f"{static_server}/index.html", wait_until="domcontentloaded")
    expect(page.locator("img.nav-logo")).to_have_attribute("alt", "NosoGraph")
    api_name = page.locator("#api-status").get_attribute("aria-label") or ""
    assert api_name.startswith("API status")
    expect(page.locator("#nav-toggle")).to_have_attribute("aria-label", "Toggle navigation")
    for name in SATELLITES:
        page.goto(f"{static_server}/{name}", wait_until="domcontentloaded")
        expect(page.locator('img[alt="NosoGraph"]')).to_have_count(1)


def test_satellite_landmarks_and_responsive_layout(page: Page, static_server: str) -> None:
    page.set_viewport_size({"width": 375, "height": 900})
    for name in SATELLITES:
        page.goto(f"{static_server}/{name}", wait_until="domcontentloaded")
        expect(page.locator("header")).to_be_visible()
        expect(page.locator("nav")).to_be_visible()
        expect(page.locator("main#main-content")).to_be_visible()
        skip = page.locator(".skip-link")
        expect(skip).to_have_attribute("href", "#main-content")
        layout = page.locator(".satellite-layout")
        if layout.count():
            columns = layout.evaluate("el => getComputedStyle(el).gridTemplateColumns")
            assert " " not in columns.strip() or columns.count("px") == 1


def test_prefers_reduced_motion_shortens_transitions(page: Page, static_server: str) -> None:
    page.emulate_media(reduced_motion="reduce")
    page.goto(f"{static_server}/index.html", wait_until="domcontentloaded")
    duration = page.locator(".nav-link").first.evaluate(
        "el => getComputedStyle(el).transitionDuration"
    )
    raw = duration.strip().lower()
    seconds = float(raw[:-2]) / 1000.0 if raw.endswith("ms") else float(raw.rstrip("s"))
    assert seconds < 0.05


def _max_seconds(raw: str) -> float:
    """Parse a (possibly comma-separated) computed CSS time list to seconds."""
    values = []
    for part in raw.split(","):
        part = part.strip().lower()
        if not part:
            continue
        values.append(float(part[:-2]) / 1000.0 if part.endswith("ms") else float(part.rstrip("s")))
    return max(values, default=0.0)


def test_motion_preferences_toggle_smooth_scroll_and_durations(
    page: Page, static_server: str
) -> None:
    """Motion allowed: smooth scroll + token durations. Reduced: both off."""
    page.goto(f"{static_server}/index.html", wait_until="domcontentloaded")
    assert (
        page.evaluate("() => getComputedStyle(document.documentElement).scrollBehavior")
        == "smooth"
    )
    assert page.evaluate("() => ngScrollBehavior()") == "smooth"
    duration = page.locator(".nav-link").first.evaluate(
        "el => getComputedStyle(el).transitionDuration"
    )
    assert abs(_max_seconds(duration) - 0.16) < 0.001  # --ng-fast

    page.emulate_media(reduced_motion="reduce")
    assert (
        page.evaluate("() => getComputedStyle(document.documentElement).scrollBehavior")
        == "auto"
    )
    assert page.evaluate("() => ngScrollBehavior()") == "auto"
    killed = page.evaluate("() => getComputedStyle(document.body).animationDuration")
    assert _max_seconds(killed) < 0.05


def test_mobile_nav_disclosure_escape_and_focus_return(page: Page, static_server: str) -> None:
    page.set_viewport_size({"width": 375, "height": 812})
    page.goto(f"{static_server}/index.html", wait_until="domcontentloaded")
    toggle = page.locator("#nav-toggle")
    menu = page.locator("#nav-menu")
    expect(toggle).to_be_visible()
    expect(toggle).to_have_attribute("aria-expanded", "false")
    expect(toggle).to_have_attribute("aria-controls", "nav-menu")
    expect(menu).to_be_hidden()

    # Keyboard open: Enter on the focused toggle.
    toggle.focus()
    page.keyboard.press("Enter")
    expect(toggle).to_have_attribute("aria-expanded", "true")
    expect(menu).to_be_visible()

    # Keyboard order from the toggle runs through the primary bar into the
    # open menu (DOM order): disease selector, API status, first section link.
    # (The selector is a Tom-Select combobox when JS upgrades it, hence the
    # "-ts-control" suffix on the focusable input.)
    labels = []
    for _ in range(3):
        page.keyboard.press("Tab")
        labels.append(
            page.evaluate(
                "() => document.activeElement "
                "&& (document.activeElement.id || document.activeElement.textContent.trim())"
            )
        )
    assert labels[0].startswith("disease-selector")
    assert labels[1:] == ["api-status", "Workspace"]

    # Escape closes the menu and returns focus to the toggle.
    page.keyboard.press("Escape")
    expect(toggle).to_have_attribute("aria-expanded", "false")
    expect(menu).to_be_hidden()
    page.wait_for_function(
        "() => document.activeElement && document.activeElement.id === 'nav-toggle'"
    )


def test_mobile_nav_closes_after_link_activation(page: Page, static_server: str) -> None:
    page.set_viewport_size({"width": 375, "height": 812})
    page.goto(f"{static_server}/index.html", wait_until="domcontentloaded")
    toggle = page.locator("#nav-toggle")
    menu = page.locator("#nav-menu")
    toggle.click()
    expect(menu).to_be_visible()
    page.locator(".nav-links--sections .nav-link").first.click()
    expect(menu).to_be_hidden()
    expect(toggle).to_have_attribute("aria-expanded", "false")
    # Hiding the focused link would strand focus on <body>; the disclosure
    # returns it to the toggle instead.
    page.wait_for_function(
        "() => document.activeElement && document.activeElement.id === 'nav-toggle'"
    )


def test_dashboard_keyboard_order_desktop(page: Page, static_server: str) -> None:
    """At desktop widths the hidden toggle drops out of the tab order."""
    page.set_viewport_size({"width": 1440, "height": 900})
    page.goto(f"{static_server}/index.html", wait_until="domcontentloaded")
    expect(page.locator("#nav-toggle")).to_be_hidden()
    order = []
    for _ in range(4):
        page.keyboard.press("Tab")
        order.append(
            page.evaluate(
                "() => document.activeElement "
                "&& (document.activeElement.id || document.activeElement.textContent.trim())"
            )
        )
    assert order[0] == "Skip to content"
    assert order[1].startswith("disease-selector")
    assert order[2:] == ["api-status", "Workspace"]


def test_pgx_form_keyboard_flow(page: Page, static_server: str) -> None:
    """End-to-end keyboard pass on a satellite: skip link → form → submit."""
    page.goto(f"{static_server}/pgx.html", wait_until="domcontentloaded")
    expect(page.locator("#result")).to_have_attribute("aria-live", "polite")
    order = []
    for _ in range(9):
        page.keyboard.press("Tab")
        order.append(
            page.evaluate(
                "() => document.activeElement "
                "&& (document.activeElement.id || document.activeElement.textContent.trim())"
            )
        )
    assert order == [
        "Skip to content",
        "NosoGraph",
        "Patient Matching",
        "Lead Opt & ADMET",
        "Spatial Omics",
        "Target Agent",
        "PGx",
        "genotype-input",
        "submit-btn",
    ]
    # Shift+Tab back to the textarea; invalid JSON is handled fully
    # client-side (deterministic, offline), then Tab → Enter submits.
    page.keyboard.press("Shift+Tab")
    page.wait_for_function(
        "() => document.activeElement && document.activeElement.id === 'genotype-input'"
    )
    page.keyboard.type("{not json")
    page.keyboard.press("Tab")
    page.wait_for_function(
        "() => document.activeElement && document.activeElement.id === 'submit-btn'"
    )
    page.keyboard.press("Enter")
    expect(page.locator("#result")).to_contain_text("Invalid JSON")
