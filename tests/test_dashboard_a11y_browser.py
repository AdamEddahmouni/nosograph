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


CORPUS_FIXTURE_ROWS = [
    {
        "disease_id": "sle",
        "name": "Systemic lupus erythematosus",
        "tier": "L3",
        "mondo_curie": "MONDO:0007915",
        "efo_id": "MONDO_0007915",
        "gene_count": 42,
        "drug_count": 7,
        "pathway_count": 3,
        "symptom_count": 12,
        "config_gaps": [],
    },
    {
        "disease_id": "ra",
        "name": "Rheumatoid arthritis",
        "tier": "L2",
        "mondo_curie": "MONDO:0008383",
        "gene_count": 30,
        "drug_count": 5,
        "pathway_count": 2,
        # Missing, not zero: the row must not claim an asserted count of 0.
        "config_gaps": ["biomarkers"],
    },
]


def _render_corpus_rows(page: Page) -> None:
    """Exercise the real corpus render path with a deterministic fixture."""
    page.evaluate(
        "rows => renderCorpusTable(rows)",
        CORPUS_FIXTURE_ROWS,
    )


def test_navigation_aria_current_moves_to_exactly_one_item(page: Page, static_server: str) -> None:
    """Exactly one nav item is current, before and after navigation."""
    page.goto(f"{static_server}/index.html", wait_until="domcontentloaded")

    expect(page.locator(".nav-link[aria-current]")).to_have_count(1)
    expect(page.locator('.nav-link[data-nav="evidence-workspace"]')).to_have_attribute(
        "aria-current", "true"
    )

    page.locator('.nav-link[data-nav="modules"]').click()
    page.wait_for_function("() => window.location.hash === '#modules'")

    expect(page.locator(".nav-link[aria-current]")).to_have_count(1)
    expect(page.locator('.nav-link[data-nav="modules"]')).to_have_attribute("aria-current", "true")
    expect(page.locator('.nav-link[data-nav="evidence-workspace"]')).not_to_have_attribute(
        "aria-current", "true"
    )
    # The styling class and the announced state stay in step.
    active_class = page.evaluate("() => document.querySelectorAll('.nav-link.active').length")
    assert active_class == 1


def test_navigation_state_survives_reduced_motion(page: Page, static_server: str) -> None:
    page.emulate_media(reduced_motion="reduce")
    page.goto(f"{static_server}/index.html", wait_until="domcontentloaded")
    page.locator('.nav-link[data-nav="corpus-status"]').click()
    page.wait_for_function("() => window.location.hash === '#corpus-status'")
    expect(page.locator(".nav-link[aria-current]")).to_have_count(1)
    expect(page.locator('.nav-link[data-nav="corpus-status"]')).to_have_attribute(
        "aria-current", "true"
    )


def test_compact_corpus_table_keeps_table_semantics_and_column_labels(
    page: Page, static_server: str
) -> None:
    """The phone presentation keeps <table>/<th scope> and labels each cell."""
    page.set_viewport_size({"width": 390, "height": 844})
    page.goto(f"{static_server}/index.html", wait_until="domcontentloaded")
    _render_corpus_rows(page)

    table = page.get_by_role(
        "table",
        name="Disease modules with readiness tier",
    )
    expect(table).to_be_visible()
    # Semantics are unchanged: real header cells, still scoped to their column.
    expect(table.locator("th[scope='col']")).to_have_count(7)
    expect(table.locator("tbody tr")).to_have_count(2)
    expect(table.locator("tbody tr").first.locator("th, td")).to_have_count(7)

    derived = page.evaluate(
        """() => {
            const table = document.querySelector('.corpus-table');
            const headers = Array.from(table.tHead.rows[0].cells)
                .map(cell => cell.textContent.trim());
            const labels = Array.from(table.tBodies[0].rows[0].cells)
                .map(cell => cell.dataset.label || '');
            return { headers, labels };
        }"""
    )
    assert derived["labels"] == derived["headers"]
    assert "Tier" in derived["labels"]

    # The compact presentation is active only at phone widths.
    phone_size = page.locator(".corpus-table th").first.evaluate(
        "el => getComputedStyle(el).fontSize"
    )
    assert phone_size == "0px"

    page.set_viewport_size({"width": 1440, "height": 900})
    desktop_size = page.locator(".corpus-table th").first.evaluate(
        "el => getComputedStyle(el).fontSize"
    )
    assert desktop_size != "0px"


def test_missing_counts_are_not_rendered_as_zero(page: Page, static_server: str) -> None:
    page.goto(f"{static_server}/index.html", wait_until="domcontentloaded")
    _render_corpus_rows(page)
    second_row = page.locator(".corpus-table tbody tr").nth(1)
    # symptom_count is absent from the fixture, so the row must say so.
    expect(second_row).to_contain_text("NOT_RECORDED")
    expect(second_row).not_to_contain_text("0 recorded")
    first_row = page.locator(".corpus-table tbody tr").first
    expect(first_row).to_contain_text("12 recorded")


def test_scroll_region_responds_to_end_and_home_keys(page: Page, static_server: str) -> None:
    page.set_viewport_size({"width": 390, "height": 844})
    page.goto(f"{static_server}/index.html", wait_until="domcontentloaded")
    _render_corpus_rows(page)
    region = page.locator("#corpus-table-wrap")
    expect(region).to_have_attribute("aria-describedby", "corpus-table-hint")
    region.focus()
    metrics = page.evaluate(
        """() => {
            const wrap = document.getElementById('corpus-table-wrap');
            return wrap.scrollWidth - wrap.clientWidth;
        }"""
    )
    assert metrics > 0, "fixture table must overflow at phone width"

    page.keyboard.press("End")
    end_left = page.evaluate("() => document.getElementById('corpus-table-wrap').scrollLeft")
    assert end_left > 0

    page.keyboard.press("Home")
    home_position = page.evaluate(
        """() => {
            const wrap = document.getElementById('corpus-table-wrap');
            return { left: wrap.scrollLeft, top: wrap.scrollTop };
        }"""
    )
    assert home_position == {"left": 0, "top": 0}


def test_table_states_are_announced_and_distinguishable(page: Page, static_server: str) -> None:
    page.goto(f"{static_server}/index.html", wait_until="domcontentloaded")

    page.evaluate("() => announceCorpusTableState('loading', 'Loading disease corpus data…')")
    expect(page.locator("#corpus-table-status")).to_have_text("Loading disease corpus data…")
    expect(page.locator("#corpus-table-alert")).to_be_empty()
    expect(page.locator("#corpus-table-wrap")).to_have_attribute("aria-busy", "true")
    expect(page.locator(".corpus-table .table-state--loading")).to_have_count(1)

    page.evaluate("() => announceCorpusTableState('error', 'Failed to load corpus status: boom')")
    # Errors go to the assertive region only, so the state is never ambiguous.
    expect(page.locator("#corpus-table-alert")).to_have_text("Failed to load corpus status: boom")
    expect(page.locator("#corpus-table-status")).to_be_empty()
    expect(page.locator("#corpus-table-wrap")).to_have_attribute("aria-busy", "false")
    expect(page.locator(".corpus-table .table-state--error")).to_have_count(1)
    expect(page.locator(".corpus-table .table-state--loading")).to_have_count(0)


def test_empty_corpus_filter_is_a_distinct_empty_state(page: Page, static_server: str) -> None:
    page.goto(f"{static_server}/index.html", wait_until="domcontentloaded")
    page.evaluate("() => renderCorpusTable([])")
    expect(page.locator(".corpus-table .table-state--empty")).to_have_count(1)
    expect(page.locator(".corpus-table .table-state--error")).to_have_count(0)


def test_focus_returns_to_submit_after_workspace_state_change(
    page: Page, static_server: str
) -> None:
    """Disabling the focused submit button must not strand focus on <body>."""
    page.goto(f"{static_server}/index.html", wait_until="domcontentloaded")
    page.evaluate("() => document.getElementById('workspace-submit').focus()")
    assert page.evaluate("() => document.activeElement.id") == "workspace-submit"

    page.evaluate("() => setWorkspaceSubmissionState('running')")
    assert page.evaluate("() => document.activeElement.id") != "workspace-submit"
    expect(page.locator("#workspace-submit")).to_have_attribute("aria-busy", "true")

    page.evaluate("() => setWorkspaceSubmissionState('success')")
    page.wait_for_function(
        "() => document.activeElement && document.activeElement.id === 'workspace-submit'"
    )
    expect(page.locator("#workspace-submit-status")).to_contain_text("dossier ready")


def test_errors_are_announced_and_not_only_colour_coded(page: Page, static_server: str) -> None:
    page.goto(f"{static_server}/index.html", wait_until="domcontentloaded")

    page.evaluate("() => showToast('Corpus reload failed', 'error')")
    error_toast = page.locator("#toast-container .toast.error")
    expect(error_toast).to_have_count(1)
    expect(error_toast).to_have_attribute("role", "alert")

    page.evaluate("() => showToast('Disease switched', 'success')")
    success_toast = page.locator("#toast-container .toast.success")
    expect(success_toast).to_have_count(1)
    expect(success_toast).to_have_attribute("role", "status")
    expect(error_toast).to_have_attribute("role", "alert")


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
        page.evaluate("() => getComputedStyle(document.documentElement).scrollBehavior") == "smooth"
    )
    assert page.evaluate("() => ngScrollBehavior()") == "smooth"
    duration = page.locator(".nav-link").first.evaluate(
        "el => getComputedStyle(el).transitionDuration"
    )
    assert abs(_max_seconds(duration) - 0.16) < 0.001  # --ng-fast

    page.emulate_media(reduced_motion="reduce")
    assert (
        page.evaluate("() => getComputedStyle(document.documentElement).scrollBehavior") == "auto"
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
