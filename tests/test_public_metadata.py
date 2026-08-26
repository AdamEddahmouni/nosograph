"""Public metadata consistency."""

from __future__ import annotations

import importlib.util
import re
import subprocess
import sys
import tomllib
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
CURRENT_VERSION = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))["project"][
    "version"
]


def _load_checker():
    spec = importlib.util.spec_from_file_location(
        "check_public_metadata", ROOT / "scripts" / "check_public_metadata.py"
    )
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _load_brand_generator():
    spec = importlib.util.spec_from_file_location(
        "generate_brand_assets", ROOT / "scripts" / "generate_brand_assets.py"
    )
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _assert_overlay_fails(
    monkeypatch: pytest.MonkeyPatch,
    relative: str,
    replacement: str,
    expected: str,
) -> None:
    checker = _load_checker()
    original_text = checker._text

    def overlay(path: str) -> str:
        return replacement if path == relative else original_text(path)

    monkeypatch.setattr(checker, "_text", overlay)
    with pytest.raises(SystemExit, match=expected):
        checker.main()


def test_public_metadata() -> None:
    subprocess.check_call(
        [sys.executable, str(ROOT / "scripts" / "check_public_metadata.py")],
        cwd=ROOT,
    )


def test_rejects_stale_citation_page_version(monkeypatch: pytest.MonkeyPatch) -> None:
    citation = (ROOT / "docs" / "project" / "citation.md").read_text(encoding="utf-8")
    _assert_overlay_fails(
        monkeypatch,
        "docs/project/citation.md",
        citation.replace(CURRENT_VERSION, "9.9.9"),
        r"docs/project/citation\.md version",
    )


def test_accepts_future_release_before_zenodo_version_doi(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    checker = _load_checker()
    original_text = checker._text
    concept_doi = "10.5281/zenodo.22055279"
    future_version = "9.8.7"

    def overlay(path: str) -> str:
        text = original_text(path)
        if path == "CITATION.cff":
            metadata, preferred = text.split("preferred-citation:", 1)
            metadata = metadata.replace(
                f"version: {CURRENT_VERSION}", f"version: {future_version}", 1
            )
            preferred = preferred.replace(
                f"  version: {CURRENT_VERSION}", f"  version: {future_version}"
            )
            preferred = re.sub(r"(?m)^  doi:.*$", f'  doi: "{concept_doi}"', preferred, count=1)
            return f"{metadata}preferred-citation:{preferred}"
        if path == "codemeta.json":
            evolved = text.replace(
                f'"version": "{CURRENT_VERSION}"', f'"version": "{future_version}"'
            )
            return re.sub(
                r'"identifier": "https://doi.org/10\.5281/zenodo\.\d+"',
                f'"identifier": "https://doi.org/{concept_doi}"',
                evolved,
                count=1,
            )
        evolved = text.replace(f"v{CURRENT_VERSION}", f"v{future_version}").replace(
            CURRENT_VERSION, future_version
        )
        if path in {"README.md", "docs/project/citation.md"}:
            evolved = re.sub(r"10\.5281/zenodo\.\d+", concept_doi, evolved)
        return evolved

    monkeypatch.setattr(checker, "_text", overlay)
    checker.main()


def test_rejects_stale_codemeta_description(monkeypatch: pytest.MonkeyPatch) -> None:
    codemeta = (ROOT / "codemeta.json").read_text(encoding="utf-8")
    _assert_overlay_fails(
        monkeypatch,
        "codemeta.json",
        codemeta.replace(
            "Open-source research software for connecting disease knowledge, evidence, "
            "and provenance across biomedical sources.",
            "Wrong description",
        ),
        r"codemeta\.json description",
    )


def test_rejects_stale_package_description(monkeypatch: pytest.MonkeyPatch) -> None:
    pyproject = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
    _assert_overlay_fails(
        monkeypatch,
        "pyproject.toml",
        pyproject.replace(
            'description = "NosoGraph — Disease Intelligence. Connected. Open-source research software for connecting disease knowledge, evidence, and provenance across biomedical sources."',
            'description = "Wrong description"',
        ),
        "pyproject.toml description",
    )


def test_rejects_retired_positioning_on_current_surface(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    governance = (ROOT / "GOVERNANCE.md").read_text(encoding="utf-8")
    _assert_overlay_fails(
        monkeypatch,
        "GOVERNANCE.md",
        governance.replace(
            "Disease Intelligence. Connected.",
            "The Open Computational Map of Human Disease",
        ),
        "retired positioning",
    )


def test_rejects_lowercase_retired_positioning_variant(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    faq = (ROOT / "docs" / "getting-started" / "faq.md").read_text(encoding="utf-8")
    _assert_overlay_fails(
        monkeypatch,
        "docs/getting-started/faq.md",
        faq.replace(
            "Disease Intelligence. Connected.",
            "An open computational map of human disease.",
        ),
        "retired positioning",
    )


def test_rejects_svg_social_metadata(monkeypatch: pytest.MonkeyPatch) -> None:
    template = (ROOT / "docs-theme" / "main.html").read_text(encoding="utf-8")
    _assert_overlay_fails(
        monkeypatch,
        "docs-theme/main.html",
        template.replace("social-preview.png", "social-preview.svg").replace(
            '<meta property="og:image:type" content="image/png">\n', ""
        ),
        "PNG social preview",
    )


def test_brand_assets_match_the_canonical_reference_system() -> None:
    assets = _load_brand_generator().build_assets()
    variation_names = {
        "symbol-mono-dark.svg",
        "symbol-reversed.svg",
        "logo-mono-dark.svg",
        "logo-reversed.svg",
    }
    assert variation_names <= assets.keys()
    assert variation_names <= set(_load_checker().REQUIRED_ASSETS)
    symbol = assets["symbol.svg"]
    dark_logo = assets["logo-dark.svg"]
    lockup = assets["tagline-lockup.svg"]

    assert len(re.findall(r"<circle\b", symbol)) == 7
    assert 'font-weight="400"' in dark_logo
    assert 'letter-spacing="6"' in dark_logo
    assert "DISEASE INTELLIGENCE." in dark_logo
    assert "CONNECTED." in dark_logo
    assert "<rect" not in lockup


def test_product_surfaces_use_the_canonical_nosograph_identity() -> None:
    dashboard = (ROOT / "src/med_research/web/static/index.html").read_text(encoding="utf-8")
    dashboard_css = (ROOT / "src/med_research/web/static/css/dashboard.css").read_text(
        encoding="utf-8"
    )
    dashboard_js = (ROOT / "src/med_research/web/static/js/dashboard.js").read_text(
        encoding="utf-8"
    )
    launcher = (ROOT / "index.html").read_text(encoding="utf-8")

    assert '<img class="nav-logo" src="/brand/symbol.svg"' in dashboard
    assert '<span class="nav-logo">🧬</span>' not in dashboard
    assert "fonts.googleapis.com" not in dashboard
    assert "⚡ API v" not in dashboard_js
    assert "🦠 ${info.label}" not in dashboard_js
    for color in ("#08142d", "#102246", "#19d2c7", "#2f86ff", "#7252f4"):
        assert color in dashboard_css.lower()
    for font in (
        "InterVariable.woff2",
        "JetBrainsMono-Variable.woff2",
        "Sora-Variable.ttf",
        "OFL-1.1.txt",
    ):
        assert (ROOT / "src/med_research/web/static/fonts" / font).is_file()
    assert "Disease Intelligence. Connected." in launcher
    assert "docs/assets/brand/symbol.svg" in launcher


def test_public_homepage_hero_uses_the_canonical_lockup() -> None:
    homepage = (ROOT / "docs/index.md").read_text(encoding="utf-8")
    stylesheet = (ROOT / "docs/stylesheets/nosograph.css").read_text(encoding="utf-8")

    assert 'src="assets/brand/tagline-lockup.svg"' in homepage
    assert 'class="ng-visually-hidden"' in homepage
    assert ".ng-hero-lockup" in stylesheet
    assert "body:has(.ng-homepage) .md-sidebar--primary" in stylesheet


def test_satellite_research_pages_use_public_brand_name() -> None:
    for name in (
        "agent.html",
        "lead_opt.html",
        "patient_matching.html",
        "pgx.html",
        "spatial.html",
    ):
        page = (ROOT / "src/med_research/web/static" / name).read_text(encoding="utf-8")
        assert "— med-research" not in page
        assert "med-research Dashboard" not in page
        assert "NosoGraph" in page


def test_media_kit_contains_reusable_approved_marketing_copy() -> None:
    launch_copy = (ROOT / "docs/project/launch-copy.md").read_text(encoding="utf-8")

    assert "Turning fragmented disease evidence into connected intelligence." in launch_copy
    assert "## Social bio" in launch_copy
    assert "## 50-word boilerplate" in launch_copy
    assert "## 150-word boilerplate" in launch_copy
    assert "## Calls to action" in launch_copy
