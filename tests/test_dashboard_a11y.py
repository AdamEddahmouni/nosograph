"""Static accessibility contracts for the dashboard and satellite pages.

Browser/Playwright coverage is still required for keyboard and screen-reader
behavior; these checks catch missing skip links, names, landmarks, and
research disclaimers in the committed HTML.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

pytestmark = pytest.mark.unit

ROOT = Path(__file__).resolve().parents[1] / "src" / "med_research" / "web" / "static"
SATELLITES = (
    "agent.html",
    "lead_opt.html",
    "patient_matching.html",
    "pgx.html",
    "spatial.html",
)


def test_dashboard_has_skip_link_named_logo_and_landmarks() -> None:
    html = (ROOT / "index.html").read_text(encoding="utf-8")
    assert 'class="skip-link"' in html
    assert 'href="#main-content"' in html
    assert 'alt="NosoGraph"' in html
    assert 'id="main-content"' in html
    assert 'tabindex="-1"' in html
    assert "<header>" in html
    assert '<nav class="top-nav"' in html
    assert "<footer>" in html
    assert 'aria-label="API status"' in html
    assert 'aria-label="Toggle navigation"' in html
    assert ":focus-visible" not in html  # focus styles stay in CSS


def test_dashboard_css_keeps_focus_visible_and_skip_link() -> None:
    css = (ROOT / "css" / "dashboard.css").read_text(encoding="utf-8")
    assert "a:focus-visible" in css
    assert ".skip-link" in css
    assert "prefers-reduced-motion" in css
    assert ".satellite-layout" in css


def test_satellites_have_skip_link_disclaimer_and_named_logo() -> None:
    for name in SATELLITES:
        html = (ROOT / name).read_text(encoding="utf-8")
        assert 'class="skip-link"' in html, name
        assert 'alt="NosoGraph"' in html, name
        assert 'id="main-content"' in html, name
        assert 'tabindex="-1"' in html, name
        assert "<header" in html, name
        lowered = html.lower()
        assert "research" in lowered, name
        assert "phi" in lowered or "protected health" in lowered, name
        assert "<nav" in html, name


def test_pgx_heading_and_input_label() -> None:
    html = (ROOT / "pgx.html").read_text(encoding="utf-8")
    assert "<h1>" in html
    assert 'for="genotype-input"' in html


def test_nav_toggle_is_a_wired_disclosure_button() -> None:
    """The mobile nav toggle must reference its menu and default to collapsed."""
    html = (ROOT / "index.html").read_text(encoding="utf-8")
    assert 'id="nav-toggle"' in html
    assert 'aria-expanded="false"' in html
    assert 'aria-controls="nav-menu"' in html
    assert 'id="nav-menu"' in html


def test_nav_js_supports_escape_close_and_focus_return() -> None:
    """Contract for the disclosure keyboard behavior verified in the browser tier."""
    js = (ROOT / "js" / "dashboard.js").read_text(encoding="utf-8")
    assert '"Escape"' in js or "'Escape'" in js
    assert "aria-expanded" in js
    assert "toggle.focus()" in js


def test_satellite_navs_are_named_and_mark_current_page() -> None:
    for name in SATELLITES:
        html = (ROOT / name).read_text(encoding="utf-8")
        assert 'aria-label="Research tools"' in html, name
        assert 'aria-current="page"' in html, name


_LAYOUT_TRANSITION_PROPS = frozenset(
    {
        "all",
        "width",
        "height",
        "top",
        "right",
        "bottom",
        "left",
        "margin",
        "padding",
        "flex",
        "grid",
    }
)


def test_dashboard_css_transitions_stay_off_layout_properties() -> None:
    """Motion safety (WCAG 2.3.3): animate compositor properties only.

    Layout-animating transitions (width/height/...) cause reflow churn and
    vestibular-unfriendly movement on dense research screens; use transform
    or opacity instead.
    """
    css = (ROOT / "css" / "dashboard.css").read_text(encoding="utf-8")
    offenders: list[str] = []
    for match in re.finditer(r"transition\s*:\s*([^;]+);", css):
        for part in match.group(1).split(","):
            tokens = part.strip().split()
            if tokens and tokens[0] in _LAYOUT_TRANSITION_PROPS:
                offenders.append(tokens[0])
    assert not offenders, f"layout-property transitions found: {offenders}"
