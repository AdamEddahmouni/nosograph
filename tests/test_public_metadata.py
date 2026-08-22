"""Public metadata consistency."""

from __future__ import annotations

import importlib.util
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


def _load_checker():
    spec = importlib.util.spec_from_file_location(
        "check_public_metadata", ROOT / "scripts" / "check_public_metadata.py"
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
        citation.replace("0.1.0", "9.9.9"),
        r"docs/project/citation\.md version",
    )


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
