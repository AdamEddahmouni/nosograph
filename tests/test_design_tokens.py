"""Parity + discipline contracts for the shared NosoGraph design tokens.

The MkDocs site (``docs/stylesheets/tokens.css``) and the FastAPI dashboard
(``src/med_research/web/static/css/tokens.css``) load separate copies of the
same token file. These tests parse both copies and assert:

- identical scopes, token names, and values across the two files;
- no duplicate declarations within a scope;
- every required token category is present (typography, spacing, radii,
  borders, elevation, surfaces, semantic/status/brand colors, evidence
  states, data-viz palette, focus ring, interaction states, links, layout
  widths, breakpoints, motion, z-index);
- WCAG AA contrast for the core text/status pairs in both color schemes
  (4.5:1 body text, 3:1 for the focus ring as UI chrome).

The parser is intentionally small: tokens.css must stay flat (no nested
blocks such as @media) so name/value extraction stays unambiguous.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

pytestmark = pytest.mark.unit

ROOT = Path(__file__).resolve().parents[1]
DOCS_TOKENS = ROOT / "docs" / "stylesheets" / "tokens.css"
APP_TOKENS = ROOT / "src" / "med_research" / "web" / "static" / "css" / "tokens.css"

SYNC_MARKER = "KEPT-IN-SYNC PAIR"

_DECL_RE = re.compile(r"(--[\w-]+)\s*:\s*([^;]+);")
_HEX_RE = re.compile(r"^#[0-9a-f]{6}$")
_VAR_RE = re.compile(r"^var\((--[\w-]+)\)$")

# Canonical scope keys: ":root" for the light/reference set, "dark" for the
# slate/data-ng-theme override set.
DARK_SELECTOR_PARTS = {"[data-md-color-scheme='slate']", "[data-ng-theme='dark']"}


def _strip_comments(css: str) -> str:
    return re.sub(r"/\*.*?\*/", "", css, flags=re.DOTALL)


def _canonical_scope(selector: str) -> str:
    parts = {p.strip().replace('"', "'") for p in selector.split(",") if p.strip()}
    if parts == {":root"}:
        return ":root"
    if parts == DARK_SELECTOR_PARTS:
        return "dark"
    raise AssertionError(f"unexpected token scope selector: {selector!r}")


def parse_token_file(path: Path) -> dict[str, dict[str, str]]:
    """Parse a flat token stylesheet into {scope: {name: value}}.

    Values are whitespace-normalized. Raises on nested blocks or duplicate
    declarations within a scope.
    """
    css = _strip_comments(path.read_text(encoding="utf-8"))
    scopes: dict[str, dict[str, str]] = {}
    pos = 0
    while pos < len(css):
        open_brace = css.find("{", pos)
        if open_brace == -1:
            tail = css[pos:].strip()
            assert not tail, f"{path.name}: trailing content outside a block: {tail!r}"
            break
        selector = css[pos:open_brace].strip()
        close_brace = css.find("}", open_brace)
        assert close_brace != -1, f"{path.name}: unclosed block for {selector!r}"
        body = css[open_brace + 1 : close_brace]
        assert "{" not in body, f"{path.name}: nested block inside {selector!r}"
        scope = _canonical_scope(selector)
        assert scope not in scopes, f"{path.name}: scope {scope!r} declared twice"
        declarations: dict[str, str] = {}
        for name, raw_value in _DECL_RE.findall(body):
            value = re.sub(r"\s+", " ", raw_value).strip()
            assert name not in declarations, (
                f"{path.name}: duplicate declaration of {name} in {scope}"
            )
            declarations[name] = value
        scopes[scope] = declarations
        pos = close_brace + 1
    return scopes


def _resolve(scopes: dict[str, dict[str, str]], scope: str, name: str) -> str:
    """Resolve a token to a concrete value, following one-level var() aliases."""
    value = scopes[scope].get(name) or scopes[":root"][name]
    alias = _VAR_RE.match(value)
    if alias:
        target = alias.group(1)
        value = scopes[scope].get(target) or scopes[":root"][target]
    return value


def _relative_luminance(hex_color: str) -> float:
    assert _HEX_RE.match(hex_color), f"expected 6-digit hex, got {hex_color!r}"
    channels = [int(hex_color[i : i + 2], 16) / 255 for i in (1, 3, 5)]
    linear = [c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4 for c in channels]
    return 0.2126 * linear[0] + 0.7152 * linear[1] + 0.0722 * linear[2]


def _contrast(a: str, b: str) -> float:
    la, lb = _relative_luminance(a), _relative_luminance(b)
    lighter, darker = max(la, lb), min(la, lb)
    return (lighter + 0.05) / (darker + 0.05)


@pytest.fixture(scope="module")
def scopes() -> dict[str, dict[str, str]]:
    return parse_token_file(DOCS_TOKENS)


def test_both_surfaces_ship_the_sync_header() -> None:
    for path in (DOCS_TOKENS, APP_TOKENS):
        text = path.read_text(encoding="utf-8")
        assert SYNC_MARKER in text, f"{path} is missing the kept-in-sync header"
        assert "docs/stylesheets/tokens.css" in text
        assert "src/med_research/web/static/css/tokens.css" in text


def test_token_files_are_in_parity() -> None:
    docs = parse_token_file(DOCS_TOKENS)
    app = parse_token_file(APP_TOKENS)
    assert set(docs) == set(app) == {":root", "dark"}
    for scope in (":root", "dark"):
        missing_in_app = set(docs[scope]) - set(app[scope])
        missing_in_docs = set(app[scope]) - set(docs[scope])
        assert not missing_in_app, f"{scope}: tokens missing in app copy: {missing_in_app}"
        assert not missing_in_docs, f"{scope}: tokens missing in docs copy: {missing_in_docs}"
        diverged = {
            name for name in docs[scope] if docs[scope][name] != app[scope][name]
        }
        assert not diverged, f"{scope}: values diverged: {diverged}"


def test_required_token_categories(scopes: dict[str, dict[str, str]]) -> None:
    root = scopes[":root"]
    expected = {
        # typography
        "--ng-font-display", "--ng-font-text", "--ng-font-mono",
        "--ng-text-micro", "--ng-text-sm", "--ng-text-md", "--ng-text-ui",
        "--ng-text-base", "--ng-text-lede", "--ng-text-h3", "--ng-text-h2",
        "--ng-text-display",
        "--ng-leading-display", "--ng-leading-tight", "--ng-leading-body",
        "--ng-leading-lede", "--ng-tracking-display", "--ng-tracking-caps",
        "--ng-weight-regular", "--ng-weight-medium", "--ng-weight-semibold",
        "--ng-weight-bold",
        # spacing
        "--ng-sp-4", "--ng-sp-8", "--ng-sp-12", "--ng-sp-16", "--ng-sp-24",
        "--ng-sp-32", "--ng-sp-48", "--ng-sp-64", "--ng-sp-96", "--ng-sp-128",
        "--ng-space-inline", "--ng-space-section",
        # radii, borders, elevation
        "--ng-radius-xs", "--ng-radius-sm", "--ng-radius-md", "--ng-radius-pill",
        "--ng-border-w", "--ng-border-w-strong", "--ng-border-w-accent",
        "--ng-shadow-plate", "--ng-shadow-overlay",
        # surfaces + semantic ink
        "--ng-bg", "--ng-surface", "--ng-surface-alt", "--ng-elevated",
        "--ng-ink", "--ng-ink-soft", "--ng-ink-muted",
        "--ng-border", "--ng-border-strong", "--ng-scrim",
        # brand (signal only) + status
        "--ng-deep-navy", "--ng-teal", "--ng-blue", "--ng-violet",
        "--ng-brand-gradient",
        "--ng-success", "--ng-warning", "--ng-error", "--ng-info",
        # evidence semantics (never the brand spectrum)
        "--ng-ev-supports", "--ng-ev-contradicts", "--ng-ev-inconclusive",
        "--ng-ev-unasserted", "--ng-provenance",
        # data-viz categorical palette
        "--ng-data-1", "--ng-data-2", "--ng-data-3", "--ng-data-4",
        "--ng-data-5", "--ng-data-6", "--ng-data-7", "--ng-data-8",
        # focus ring + interaction states + links
        "--ng-focus", "--ng-focus-ring", "--ng-focus-ring-width",
        "--ng-focus-ring-offset",
        "--ng-hover", "--ng-active", "--ng-disabled-opacity",
        "--ng-link", "--ng-link-hover",
        # layout widths + breakpoints
        "--ng-width-reading", "--ng-width-standard", "--ng-width-wide",
        "--ng-gutter",
        "--ng-bp-sm", "--ng-bp-md", "--ng-bp-lg", "--ng-bp-xl",
        # motion + z-index
        "--ng-ease", "--ng-fast", "--ng-normal", "--ng-slow",
        "--ng-z-sticky", "--ng-z-dropdown", "--ng-z-overlay", "--ng-z-modal",
        "--ng-z-toast", "--ng-z-skip-link",
    }
    missing = expected - set(root)
    assert not missing, f"missing tokens: {sorted(missing)}"


def test_breakpoints_match_the_canonical_set(
    scopes: dict[str, dict[str, str]],
) -> None:
    root = scopes[":root"]
    assert root["--ng-bp-sm"] == "375px"
    assert root["--ng-bp-md"] == "768px"
    assert root["--ng-bp-lg"] == "1024px"
    assert root["--ng-bp-xl"] == "1440px"


def test_brand_spectrum_is_not_evidence_coded(scopes: dict[str, dict[str, str]]) -> None:
    """Evidence tokens must not alias the brand gradient stops (PR #104)."""
    brand_stops = {"--ng-teal", "--ng-blue", "--ng-violet"}
    for scope in (":root", "dark"):
        for evidence in (
            "--ng-ev-supports",
            "--ng-ev-contradicts",
            "--ng-ev-inconclusive",
            "--ng-ev-unasserted",
        ):
            value = scopes[scope][evidence]
            alias = _VAR_RE.match(value)
            assert not alias or alias.group(1) not in brand_stops, (
                f"{scope} {evidence} aliases a brand color ({value})"
            )


@pytest.mark.parametrize("scope", [":root", "dark"])
def test_wcag_aa_text_contrast(scope: str, scopes: dict[str, dict[str, str]]) -> None:
    bg = _resolve(scopes, scope, "--ng-bg")
    text_tokens = (
        "--ng-ink",
        "--ng-ink-soft",
        "--ng-ink-muted",
        "--ng-link",
        "--ng-success",
        "--ng-warning",
        "--ng-error",
        "--ng-info",
        "--ng-ev-supports",
        "--ng-ev-contradicts",
        "--ng-ev-inconclusive",
        "--ng-ev-unasserted",
        "--ng-provenance",
    )
    for name in text_tokens:
        ratio = _contrast(_resolve(scopes, scope, name), bg)
        assert ratio >= 4.5, f"{scope} {name} on --ng-bg: {ratio:.2f}:1 < 4.5:1"


@pytest.mark.parametrize("scope", [":root", "dark"])
def test_wcag_aa_focus_ring_chrome_contrast(
    scope: str, scopes: dict[str, dict[str, str]]
) -> None:
    ratio = _contrast(_resolve(scopes, scope, "--ng-focus-ring"), _resolve(scopes, scope, "--ng-bg"))
    assert ratio >= 3.0, f"{scope} --ng-focus-ring on --ng-bg: {ratio:.2f}:1 < 3:1"
