"""Static safety invariants for the community experience prototype (no browser).

The prototype under ``src/med_research/web/static/community/`` is a deliberately
inert artefact: a fixed synthetic fixture list rendered by plain JavaScript, with
no network access, no persistence, no accounts, and no submission path. Its value
depends entirely on those absences, so they are pinned here as assertions rather
than left to review discipline.

Everything in this module reads committed files only. It does not start a server,
open a browser, or touch curated disease data. Behavioural coverage of the
accessible interactions would belong in the slow browser tier; this module covers
the structural contract that a later edit could otherwise break silently.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

pytestmark = pytest.mark.unit

ROOT = Path(__file__).resolve().parents[1]
STATIC = ROOT / "src" / "med_research" / "web" / "static"
COMMUNITY = STATIC / "community"
PROTOTYPE_HTML = COMMUNITY / "prototype.html"
PROTOTYPE_JS = COMMUNITY / "prototype.js"
COMMUNITY_README = COMMUNITY / "README.md"
DESIGN_DOC = ROOT / "docs" / "concepts" / "community-prototype.md"

MODERATION_STATES = (
    "published",
    "pending_review",
    "hidden_insufficient_context",
)

# Identifiers that would turn this static sketch into a data-collecting surface.
# Matched case-insensitively so a rename or a wrapper cannot slip past.
FORBIDDEN_IN_CLIENT_CODE = (
    "fetch(",
    "xmlhttprequest",
    "localstorage",
    "sessionstorage",
    "indexeddb",
    "opendatabase",
    "sendbeacon",
    "websocket",
    "eventsource",
    "document.cookie",
)

_WHITESPACE_RE = re.compile(r"\s+")


def _read(path: Path) -> str:
    assert path.is_file(), f"missing prototype asset: {path.relative_to(ROOT)}"
    return path.read_text(encoding="utf-8")


def _prose(text: str) -> str:
    """Collapse whitespace so wrapped markup prose can be asserted as sentences."""
    return _WHITESPACE_RE.sub(" ", text).strip().lower()


@pytest.fixture(scope="module")
def html() -> str:
    return _read(PROTOTYPE_HTML)


@pytest.fixture(scope="module")
def script() -> str:
    return _read(PROTOTYPE_JS)


@pytest.fixture(scope="module")
def design_doc() -> str:
    return _read(DESIGN_DOC)


# --------------------------------------------------------------------------- #
# Not a submission surface
# --------------------------------------------------------------------------- #


def test_prototype_has_no_submission_form(html: str) -> None:
    lowered = html.lower()
    assert "<form" not in lowered, "the prototype must not contain a form element"
    assert "action=" not in lowered, "no element may declare a submit action"
    assert "<textarea" not in lowered, "free-text submission is out of scope"
    assert "contenteditable" not in lowered


def test_prototype_collects_no_identity_fields(html: str) -> None:
    lowered = html.lower()
    for field_type in ('type="password"', 'type="email"', 'type="tel"', 'type="file"'):
        assert field_type not in lowered, field_type
    # A name attribute on any form control would make it submittable.
    named_control = re.search(r"<(?:input|select|textarea)[^>]*\bname\s*=", lowered)
    assert named_control is None, named_control
    assert "autocomplete=" not in lowered


def test_client_code_is_offline(html: str, script: str) -> None:
    combined = (html + "\n" + script).lower()
    offenders = [token for token in FORBIDDEN_IN_CLIENT_CODE if token in combined]
    assert not offenders, f"prototype must stay offline and stateless: {offenders}"


def test_report_control_is_announced_and_does_not_submit(script: str) -> None:
    assert "aria-pressed" in script, "the report control must expose its toggle state"
    assert "setAttribute('aria-pressed'" in script
    assert "localReportState" in script, "report state must be an in-memory Set"
    assert "new Set()" in script
    assert "nothing was sent" in script.lower()


# --------------------------------------------------------------------------- #
# Evidence separation
# --------------------------------------------------------------------------- #


def test_not_evidence_boundary_is_stated_in_the_page(html: str) -> None:
    lowered = _prose(html)
    assert "community experience is not scientific evidence" in lowered
    assert 'role="region"' in lowered, "the banner needs a landmark role"
    assert 'aria-label="scientific boundary notice"' in lowered
    # The banner is persistent, not a dismissible toast.
    assert "position: sticky" in html


def test_page_does_not_link_the_dashboard_stylesheet(html: str) -> None:
    assert "../css/dashboard.css" not in html
    assert "@import" not in html
    assert "../css/tokens.css" in html


# --------------------------------------------------------------------------- #
# Synthetic labelling
# --------------------------------------------------------------------------- #


def test_every_fixture_post_is_marked_synthetic(script: str) -> None:
    post_count = script.count("content_origin: 'fabricated_placeholder'")
    assert post_count >= 6, f"expected at least 6 synthetic posts, found {post_count}"
    # The trailing comma restricts this to the fixture objects; the file-header
    # comment also mentions the key in prose.
    assert script.count("synthetic: true,") == post_count, (
        "each fixture post must carry synthetic: true and a fabricated origin"
    )
    assert "Synthetic example" in script, "a visible synthetic badge label is required"
    assert "Not a real account" in script


def test_renderer_fails_closed_on_unlabelled_posts(script: str) -> None:
    guard = re.search(r"if \(post\.synthetic !== true\)", script)
    assert guard, "the renderer must refuse a post without synthetic: true"


def test_fixture_posts_avoid_clinical_specifics(script: str) -> None:
    # Inventing doses, severities, or outcomes would be fabricating health data.
    lowered = script.lower()
    for forbidden in ("dosage", " mg", "milligram", "blood pressure", "diagnosis"):
        assert forbidden not in lowered, forbidden


# --------------------------------------------------------------------------- #
# Moderation vocabulary
# --------------------------------------------------------------------------- #


def test_moderation_states_are_a_closed_explicit_vocabulary(script: str) -> None:
    for state in MODERATION_STATES:
        assert f"moderation: '{state}'" in script, f"no fixture exercises {state}"
    assert "const MODERATION_GLOSS = {" in script
    for state in MODERATION_STATES:
        glossed = re.search(rf"^\s+{state}: '", script, re.MULTILINE)
        assert glossed, f"{state} needs a plain-language gloss"


def test_moderation_states_are_not_colour_only(html: str) -> None:
    for state in MODERATION_STATES:
        assert f".comm-state--{state}::before" in html, state
    # One distinct glyph per state.
    for glyph in ('content: "\\25CF"', 'content: "\\25D0"', 'content: "\\2298"'):
        assert glyph in html, glyph
    # Plus one distinct border treatment per state.
    for border_style in ("border-style: solid", "border-style: dashed"):
        assert border_style in html, border_style
    assert "border-style: dotted" in html


def test_hidden_state_is_described_as_a_curation_gap(design_doc: str) -> None:
    lowered = _prose(design_doc)
    assert "curation gap" in lowered
    assert "not a finding about" in lowered


# --------------------------------------------------------------------------- #
# Accessibility
# --------------------------------------------------------------------------- #


def test_prototype_is_a_responsive_document(html: str) -> None:
    assert 'name="viewport"' in html
    assert "width=device-width, initial-scale=1" in html
    assert "overflow-x: hidden" in html


def test_accessible_landmarks_and_skip_link(html: str) -> None:
    for landmark in ("<header", "<main", "<footer"):
        assert landmark in html, landmark
    assert 'class="comm-skip-link"' in html
    assert 'href="#comm-main"' in html
    assert 'id="comm-main"' in html


def test_filter_controls_have_visible_labels(html: str) -> None:
    for control_id in ("comm-disease-filter", "comm-state-filter"):
        assert f'<label for="{control_id}">' in html, control_id
        assert f'id="{control_id}"' in html, control_id


def test_live_regions_announce_state_changes(html: str, script: str) -> None:
    for region_id in ("comm-result-count", "comm-report-status"):
        match = re.search(rf'id="{region_id}"([^>]*)>', html)
        assert match is not None, region_id
        attributes = match.group(1)
        assert 'role="status"' in attributes, region_id
        assert 'aria-live="polite"' in attributes, region_id
        assert region_id in script, f"{region_id} is never updated"


def test_focus_ring_and_tap_target_floor(html: str) -> None:
    assert ":focus-visible" in html
    assert "var(--ng-comm-focus-ring)" in html
    assert "var(--ng-comm-focus-ring-width)" in html
    assert "--ng-comm-tap: 44px;" in html
    assert html.count("var(--ng-comm-tap)") >= 2


def test_motion_and_contrast_preferences_are_honoured(html: str) -> None:
    assert "@media (prefers-reduced-motion: reduce)" in html
    start = html.index("@media (prefers-reduced-motion: reduce)")
    block = html[start : start + 600]
    assert "transition-duration" in block
    assert "animation-duration" in block
    assert "animation-iteration-count" in block
    assert "scroll-behavior: auto" in block
    assert "@media (prefers-contrast: more)" in html


def test_no_javascript_fallback_is_documented(html: str) -> None:
    assert "<noscript>" in html
    assert '<script src="prototype.js">' in html


# --------------------------------------------------------------------------- #
# Disclosure documents
# --------------------------------------------------------------------------- #


def test_privacy_boundary_is_disclosed_in_the_page(html: str) -> None:
    lowered = _prose(html)
    assert "privacy architecture has not been assessed" in lowered
    assert "does not collect, transmit, or store anything" in lowered
    assert "complete anonymity is not claimed or verified" in lowered
    assert "do not paste personal health information" in lowered


def test_design_doc_states_the_unassessed_privacy_position(design_doc: str) -> None:
    lowered = _prose(design_doc)
    assert "privacy architecture has not been assessed" in lowered
    assert "must not be described as anonymous" in lowered
    position = "not collected, not transmitted, not persisted, and not assessed"
    assert position in lowered


def test_design_doc_lists_pre_deployment_requirements(design_doc: str) -> None:
    lowered = _prose(design_doc)
    for requirement in (
        "threat model",
        "retention",
        "consent",
        "moderation duty-of-care",
        "independent privacy and security review",
        "owner authorization",
    ):
        assert requirement in lowered, requirement
    assert "what is deliberately not implemented" in lowered


def test_readme_points_at_the_design_notes() -> None:
    readme = _prose(_read(COMMUNITY_README))
    assert "not scientific evidence" in readme
    assert "privacy architecture has not been assessed" in readme
    assert "docs/concepts/community-prototype.md" in readme
    assert "no submissions" in readme


def test_design_doc_is_linked_from_the_prototype(html: str) -> None:
    assert "docs/concepts/community-prototype.md" in html
