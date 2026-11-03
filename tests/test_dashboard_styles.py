"""Static guarantees for the dashboard stylesheet (no browser required).

The Playwright suites in ``tests/test_dashboard_a11y_browser.py`` cover focus
order, disclosure behaviour, and computed motion values. This module pins the
cheaper structural contracts so a CSS edit cannot silently drop reduced-motion
support, print styling, responsive breakpoints, focus rings, or a token
definition. Everything here reads committed files only.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

pytestmark = pytest.mark.unit

ROOT = Path(__file__).resolve().parents[1]
STATIC = ROOT / "src" / "med_research" / "web" / "static"
TOKENS_CSS = STATIC / "css" / "tokens.css"
DASHBOARD_CSS = STATIC / "css" / "dashboard.css"
INDEX_HTML = STATIC / "index.html"
DASHBOARD_JS = STATIC / "js" / "dashboard.js"

_COMMENT_RE = re.compile(r"/\*.*?\*/", re.DOTALL)
_DECL_RE = re.compile(r"(--[\w-]+)\s*:")
_VAR_RE = re.compile(r"var\(\s*(--[\w-]+)")

# Namespaces owned by third-party bundles (Tom Select, vis-network,
# cytoscape) may be referenced without being declared in our stylesheets.
_THIRD_PARTY_PREFIXES = ("--ts-", "--vis-", "--cytoscape-", "--rc-")


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _without_comments(css: str) -> str:
    return _COMMENT_RE.sub("", css)


def _declared(text: str) -> set[str]:
    return set(_DECL_RE.findall(_without_comments(text)))


def _references(text: str) -> set[str]:
    return set(_VAR_RE.findall(text))


def _is_third_party(name: str) -> bool:
    return any(name.startswith(prefix) for prefix in _THIRD_PARTY_PREFIXES)


def _block_after(css: str, marker: str) -> str:
    """Return the body of the first block whose prelude contains ``marker``."""
    start = css.index(marker)
    open_brace = css.index("{", start)
    depth = 0
    for index in range(open_brace, len(css)):
        if css[index] == "{":
            depth += 1
        elif css[index] == "}":
            depth -= 1
            if depth == 0:
                return css[open_brace + 1 : index]
    raise AssertionError(f"unbalanced CSS block after {marker!r}")


@pytest.fixture(scope="module")
def dashboard_css() -> str:
    return _read(DASHBOARD_CSS)


@pytest.fixture(scope="module")
def declared_tokens() -> set[str]:
    return _declared(_read(TOKENS_CSS)) | _declared(_read(DASHBOARD_CSS))


def test_focus_ring_covers_non_native_controls(dashboard_css: str) -> None:
    assert ":focus-visible" in dashboard_css
    rule = _block_after(dashboard_css, "a:focus-visible")
    assert "var(--ng-focus-ring)" in rule
    selectors = [
        '[role="button"]:focus-visible',
        '[role="option"]:focus-visible',
        '[contenteditable="true"]:focus-visible',
        ".nav-link:focus-visible",
        ".corpus-table-wrap:focus-visible",
    ]
    for selector in selectors:
        assert selector in dashboard_css, selector


def test_form_controls_keep_the_keyboard_focus_ring(dashboard_css: str) -> None:
    # Both the reset and the ring appear more than once (the ring is also part of
    # the grouped :focus-visible rule near the top of the file). Only the *last*
    # occurrence of each decides the cascade, so compare those.
    reset = dashboard_css.rindex("input:focus, select:focus, textarea:focus")
    ring = dashboard_css.rindex("input:focus-visible,")
    assert ring > reset, "the focus-visible ring must follow the outline:none reset"


def test_reduced_motion_block_disables_nonessential_motion(dashboard_css: str) -> None:
    block = _block_after(dashboard_css, "prefers-reduced-motion: reduce")
    for declaration in ("transition-duration", "animation-duration"):
        assert declaration in block
    assert "animation-iteration-count" in block
    assert "scroll-behavior: auto" in block
    assert "stat-card.is-loading" in block, "decorative shimmer must stop"


def test_print_block_hides_chrome_and_keeps_tables_legible(dashboard_css: str) -> None:
    block = _block_after(dashboard_css, "@media print")
    assert ".top-nav" in block
    assert ".demo-banner" in block
    assert "@page" in block
    assert "border-collapse: collapse" in block
    assert "thead { display: table-header-group; }" in block


def test_responsive_breakpoints_cover_all_target_widths(dashboard_css: str) -> None:
    for media in (
        "@media (max-width: 420px)",
        "@media (max-width: 768px)",
        "@media (max-width: 560px)",
        "@media (min-width: 1600px)",
    ):
        assert media in dashboard_css, media
    tokens = _read(TOKENS_CSS)
    assert "--ng-bp-md: 768px;" in tokens
    assert "--ng-bp-sm: 375px;" in tokens


def test_every_css_custom_property_is_defined(declared_tokens: set[str]) -> None:
    used = _references(_read(DASHBOARD_CSS)) | _references(_read(INDEX_HTML))
    candidates = [name for name in used if not _is_third_party(name)]
    undefined = sorted(name for name in candidates if name not in declared_tokens)
    assert not undefined, f"undefined custom properties: {undefined}"


def test_inline_style_aliases_are_declared(declared_tokens: set[str]) -> None:
    # dashboard.js injects inline styles that depend on the legacy alias layer
    # in dashboard.css; dropping an alias breaks the dashboard silently.
    combined = _read(DASHBOARD_JS) + _read(INDEX_HTML)
    missing = sorted(_references(combined) - declared_tokens)
    assert not missing, f"inline styles reference undeclared tokens: {missing}"


def test_local_primitives_are_declared_and_consumed(dashboard_css: str) -> None:
    primitives = [name for name in _declared(dashboard_css) if "--ng-dash-" in name]
    assert primitives, "expected dashboard-local primitives"
    unused = [name for name in primitives if f"var({name})" not in dashboard_css]
    assert not unused, f"declared but unused primitives: {unused}"


def test_touch_target_floor_is_tokenised(dashboard_css: str) -> None:
    assert "--ng-dash-tap: 44px;" in dashboard_css
    assert dashboard_css.count("var(--ng-dash-tap)") >= 2
    mobile = _block_after(dashboard_css, "@media (max-width: 768px)")
    assert "min-height: var(--ng-dash-tap)" in mobile


def test_state_channels_are_not_colour_only(dashboard_css: str) -> None:
    selectors = [
        ".coverage-badge.coverage-unsupported::before",
        ".condition-state-cell.state-not-recorded > strong::before",
        ".condition-state-cell.state-known-absent > strong::before",
        ".sat-empty::before",
        ".sat-error-box::before",
        ".workspace-result.loading::before",
    ]
    for selector in selectors:
        assert selector in dashboard_css, selector
    assert "repeating-linear-gradient" in dashboard_css


def test_aria_current_navigation_state_is_styled(dashboard_css: str) -> None:
    for state in ("page", "true", "location"):
        assert f'.nav-link[aria-current="{state}"]' in dashboard_css
    rule = _block_after(dashboard_css, '.nav-link[aria-current="page"]')
    assert "text-decoration: underline" in rule


def test_corpus_table_is_a_labelled_keyboard_scroll_region() -> None:
    html = _read(INDEX_HTML)
    wrapper = re.search(r'<div class="corpus-table-wrap"([^>]*)>', html)
    assert wrapper is not None
    attributes = wrapper.group(1)
    assert 'role="region"' in attributes
    assert 'tabindex="0"' in attributes
    assert "aria-label=" in attributes
    assert 'aria-label="Primary"' in html
