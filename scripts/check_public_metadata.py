"""Validate public-facing version, positioning, links, and asset consistency."""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CURRENT_SURFACES = (
    "README.md",
    "docs/index.md",
    "docs/public-launch.md",
    "docs/data/coverage.md",
    "docs/getting-started/demo.md",
    "docs/getting-started/faq.md",
    "docs/media/README.md",
    "docs/project/github-public-settings.md",
    "docs/project/releases.md",
    "docs/project/status.md",
)
REQUIRED_ASSETS = (
    "symbol.svg",
    "mark.svg",
    "mark-light.svg",
    "compact.svg",
    "micro.svg",
    "favicon.svg",
    "logo-dark.svg",
    "logo-light.svg",
    "tagline-lockup.svg",
    "github-avatar.svg",
    "hero.svg",
    "social-preview.svg",
)


def _text(relative: str) -> str:
    return (ROOT / relative).read_text(encoding="utf-8")


def _field(relative: str, pattern: str, label: str) -> str:
    match = re.search(pattern, _text(relative))
    if not match:
        raise SystemExit(f"{label} not found")
    return match.group(1).strip().strip('"')


def _pyproject_version() -> str:
    return _field("pyproject.toml", r'(?m)^version\s*=\s*"([^"]+)"', "pyproject.toml version")


def _status_version() -> str:
    return _field(
        "docs/generated/public-status.yaml",
        r'(?m)^version:\s*"([^"]+)"',
        "public-status.yaml version",
    )


def main() -> None:
    version = _pyproject_version()
    citation_version = _field(
        "CITATION.cff", r"(?m)^version:\s*([\"']?[^\"'\n]+)", "CITATION.cff version"
    )
    preferred_version = _field(
        "CITATION.cff",
        r"(?ms)^preferred-citation:.*?^  version:\s*([\"']?[^\"'\n]+)",
        "CITATION.cff preferred-citation version",
    )
    status_version = _status_version()
    readme = _text("README.md")
    errors: list[str] = []

    if citation_version != version:
        errors.append(f"CITATION.cff version {citation_version} != pyproject {version}")
    if preferred_version != version:
        errors.append(
            f"CITATION.cff preferred-citation version {preferred_version} != pyproject {version}"
        )
    if status_version != version:
        errors.append(f"public-status.yaml version {status_version} != pyproject {version}")
    if f"v{version}" not in readme and version not in readme:
        errors.append("README.md does not mention the current version")
    if "https://github.com/AdamEddahmouni/nosograph" not in readme:
        errors.append("README.md missing canonical repository URL")
    if "Disease Intelligence. Connected." not in readme:
        errors.append("README.md missing canonical positioning")
    if "https://adameddahmouni.github.io/nosograph/" not in readme:
        errors.append("README.md missing canonical documentation URL")
    if f"## [{version}]" not in _text("CHANGELOG.md"):
        errors.append(f"CHANGELOG.md missing ## [{version}] heading")

    citation_repo = _field(
        "CITATION.cff", r'(?m)^repository-code:\s*"([^"]+)"', "CITATION.cff repository-code"
    )
    if "nosograph" not in citation_repo:
        errors.append(f"CITATION.cff repository-code is not nosograph: {citation_repo}")

    for relative in CURRENT_SURFACES:
        text = _text(relative)
        if f"v{version}" not in text and version not in text:
            errors.append(f"{relative} does not mention current version {version}")

    brand_dir = ROOT / "docs" / "assets" / "brand"
    for asset in REQUIRED_ASSETS:
        if not (brand_dir / asset).is_file():
            errors.append(f"missing required brand asset: docs/assets/brand/{asset}")

    if "Disease Intelligence. Connected." not in _text("docs/index.md"):
        errors.append("docs/index.md missing canonical positioning")
    if "assets/brand/social-preview.svg" not in _text("docs-theme/main.html"):
        errors.append("docs-theme/main.html missing canonical social preview")

    for label, text in {
        "README.md": readme,
        "CITATION.cff": _text("CITATION.cff"),
        "SECURITY.md": _text("SECURITY.md"),
        ".github/SUPPORT.md": _text(".github/SUPPORT.md"),
    }.items():
        if "https://github.com/AdamEddahmouni/med-research" in text:
            errors.append(f"{label} contains stale public URL")

    bibtex = readme.split("```bibtex", 1)[-1] if "```bibtex" in readme else ""
    if version not in bibtex[:800]:
        errors.append(f"README BibTeX citation is missing version {version}")
    if "AdamEddahmouni/med-research" in bibtex:
        errors.append("README BibTeX still points at med-research")

    init_text = _text("src/med_research/__init__.py")
    if f'__version__ = "{version}"' not in init_text:
        errors.append("src/med_research/__init__.py __version__ does not match pyproject")
    if f'"version": "{version}"' not in _text("codemeta.json"):
        errors.append("codemeta.json is missing the current version")

    if errors:
        raise SystemExit("public metadata check failed:\n- " + "\n- ".join(errors))
    print(
        f"public metadata ok (version {version}; {len(CURRENT_SURFACES)} current surfaces checked)"
    )


if __name__ == "__main__":
    main()
