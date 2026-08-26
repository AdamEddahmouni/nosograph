"""Validate public-facing version, positioning, links, DOI, and asset consistency."""

from __future__ import annotations

import json
import re
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TAGLINE = "Disease Intelligence. Connected."
DESCRIPTOR = (
    "Open-source research software for connecting disease knowledge, evidence, "
    "and provenance across biomedical sources."
)
PACKAGE_DESCRIPTION = f"NosoGraph — {TAGLINE} {DESCRIPTOR}"
RETIRED_POSITIONING_PATTERNS = (
    re.compile(r"\b(?:the|an)\s+open computational map of human disease\b", re.IGNORECASE),
    re.compile(r"\bevidence-native computational map of human disease\b", re.IGNORECASE),
)

CURRENT_SURFACES = (
    "README.md",
    "docs/index.md",
    "docs/public-launch.md",
    "docs/data/coverage.md",
    "docs/getting-started/demo.md",
    "docs/getting-started/faq.md",
    "docs/media/README.md",
    "docs/project/citation.md",
    "docs/project/github-public-settings.md",
    "docs/project/releases.md",
    "docs/project/status.md",
)
TAGLINE_SURFACES = (
    "README.md",
    "CITATION.cff",
    "GOVERNANCE.md",
    "pyproject.toml",
    "docs/index.md",
    "docs-theme/main.html",
    "docs/legal/trademark-policy.md",
    "src/med_research/__init__.py",
    "src/med_research/cli.py",
    "src/med_research/web/config.py",
    "src/med_research/web/static/index.html",
)
DESCRIPTOR_SURFACES = (
    "README.md",
    "CITATION.cff",
    "pyproject.toml",
    "codemeta.json",
    "docs/index.md",
    "docs-theme/main.html",
)
ACTIVE_POSITIONING_SURFACES = tuple(dict.fromkeys((*TAGLINE_SURFACES, *DESCRIPTOR_SURFACES)))
ACTIVE_POSITIONING_SURFACES += (
    "CONTRIBUTING.md",
    "docs/architecture/overview.md",
    "docs/assets/screenshots/dashboard.svg",
    "docs/getting-started/faq.md",
    "docs/getting-started/what-is.md",
    "docs/project/release-notes-template.md",
)
REQUIRED_ASSETS = (
    "symbol.svg",
    "symbol-mono-dark.svg",
    "symbol-reversed.svg",
    "mark.svg",
    "mark-light.svg",
    "compact.svg",
    "micro.svg",
    "favicon.svg",
    "logo-dark.svg",
    "logo-light.svg",
    "logo-mono-dark.svg",
    "logo-reversed.svg",
    "tagline-lockup.svg",
    "github-avatar.svg",
    "hero.svg",
    "social-preview.svg",
    "social-preview.png",
)


def _text(relative: str) -> str:
    return (ROOT / relative).read_text(encoding="utf-8")


def _field(relative: str, pattern: str, label: str) -> str:
    match = re.search(pattern, _text(relative))
    if not match:
        raise SystemExit(f"{label} not found")
    return match.group(1).strip().strip('"')


def _pyproject() -> dict[str, object]:
    return tomllib.loads(_text("pyproject.toml"))["project"]


def _status_version() -> str:
    return _field(
        "docs/generated/public-status.yaml",
        r'(?m)^version:\s*"([^"]+)"',
        "public-status.yaml version",
    )


def _citation_page_version() -> str:
    return _field(
        "docs/project/citation.md",
        r"version \*\*([^*]+)\*\*",
        "docs/project/citation.md version",
    )


def _doi_from_description(cff: str, description: str) -> str | None:
    pattern = (
        r"(?ms)^\s*-\s+type:\s*doi\s*\n"
        r"\s+value:\s*[\"']?([^\"'\n]+)[\"']?\s*\n"
        rf"\s+description:\s*{re.escape(description)}\s*$"
    )
    match = re.search(pattern, cff)
    return match.group(1).strip() if match else None


def main() -> None:
    project = _pyproject()
    version = str(project["version"])
    package_description = str(project["description"])
    citation = _text("CITATION.cff")
    codemeta_text = _text("codemeta.json")
    codemeta = json.loads(codemeta_text)
    citation_version = _field(
        "CITATION.cff", r"(?m)^version:\s*([\"']?[^\"'\n]+)", "CITATION.cff version"
    )
    preferred_version = _field(
        "CITATION.cff",
        r"(?ms)^preferred-citation:.*?^\s+version:\s*([\"']?[^\"'\n]+)",
        "CITATION.cff preferred-citation version",
    )
    readme = _text("README.md")
    errors: list[str] = []

    for label, actual in {
        "CITATION.cff version": citation_version,
        "CITATION.cff preferred-citation version": preferred_version,
        "public-status.yaml version": _status_version(),
        "docs/project/citation.md version": _citation_page_version(),
        "codemeta.json version": str(codemeta.get("version", "")),
    }.items():
        if actual != version:
            errors.append(f"{label} {actual} != pyproject {version}")

    if package_description != PACKAGE_DESCRIPTION:
        errors.append("pyproject.toml description does not match canonical package description")
    if codemeta.get("description") != DESCRIPTOR:
        errors.append("codemeta.json description does not match canonical descriptor")
    if "Development Status :: 3 - Alpha" not in project.get("classifiers", []):
        errors.append("pyproject.toml classifier does not mark the package Alpha")

    if f"v{version}" not in readme and version not in readme:
        errors.append("README.md does not mention the current version")
    if "https://github.com/AdamEddahmouni/nosograph" not in readme:
        errors.append("README.md missing canonical repository URL")
    if "https://adameddahmouni.github.io/nosograph/" not in readme:
        errors.append("README.md missing canonical documentation URL")
    if f"## [{version}]" not in _text("CHANGELOG.md"):
        errors.append(f"CHANGELOG.md missing ## [{version}] heading")

    citation_repo = _field(
        "CITATION.cff", r'(?m)^repository-code:\s*"([^"]+)"', "CITATION.cff repository-code"
    )
    if citation_repo != "https://github.com/AdamEddahmouni/nosograph":
        errors.append(f"CITATION.cff repository-code is not canonical: {citation_repo}")

    for relative in CURRENT_SURFACES:
        text = _text(relative)
        if f"v{version}" not in text and version not in text:
            errors.append(f"{relative} does not mention current version {version}")

    for relative in TAGLINE_SURFACES:
        if TAGLINE not in _text(relative):
            errors.append(f"{relative} missing canonical positioning tagline")
    for relative in DESCRIPTOR_SURFACES:
        if DESCRIPTOR not in _text(relative):
            errors.append(f"{relative} missing canonical positioning descriptor")
    for relative in ACTIVE_POSITIONING_SURFACES:
        if any(pattern.search(_text(relative)) for pattern in RETIRED_POSITIONING_PATTERNS):
            errors.append(f"{relative} contains retired positioning")

    brand_dir = ROOT / "docs" / "assets" / "brand"
    for asset in REQUIRED_ASSETS:
        if not (brand_dir / asset).is_file():
            errors.append(f"missing required brand asset: docs/assets/brand/{asset}")

    template = _text("docs-theme/main.html")
    if template.count("assets/brand/social-preview.png") < 2:
        errors.append("docs-theme/main.html missing PNG social preview metadata")
    if 'property="og:image:type" content="image/png"' not in template:
        errors.append("docs-theme/main.html missing PNG social preview type")
    if "assets/brand/social-preview.svg" in template:
        errors.append("docs-theme/main.html still references SVG social metadata")

    for label, text in {
        "README.md": readme,
        "CITATION.cff": citation,
        "SECURITY.md": _text("SECURITY.md"),
        ".github/SUPPORT.md": _text(".github/SUPPORT.md"),
    }.items():
        if "https://github.com/AdamEddahmouni/med-research" in text:
            errors.append(f"{label} contains stale public URL")

    bibtex = readme.split("```bibtex", 1)[-1] if "```bibtex" in readme else ""
    if version not in bibtex[:1200]:
        errors.append(f"README BibTeX citation is missing version {version}")
    if "AdamEddahmouni/med-research" in bibtex:
        errors.append("README BibTeX still points at med-research")

    init_text = _text("src/med_research/__init__.py")
    if f'__version__ = "{version}"' not in init_text:
        errors.append("src/med_research/__init__.py __version__ does not match pyproject")

    concept_doi = _doi_from_description(citation, "Concept DOI (all versions)")
    version_doi = _doi_from_description(citation, f"Version DOI for v{version}")
    doi_surfaces = {
        "README.md": readme,
        "docs/project/citation.md": _text("docs/project/citation.md"),
        "codemeta.json": codemeta_text,
    }
    any_doi = bool(re.search(r"10\.5281/zenodo\.\d+", "\n".join(doi_surfaces.values())))
    if concept_doi or version_doi or any_doi:
        if not concept_doi:
            errors.append("CITATION.cff must define the concept DOI")
        elif version_doi:
            if concept_doi == version_doi:
                errors.append("CITATION.cff concept and version DOIs must be distinct")
            preferred_doi = _field(
                "CITATION.cff",
                r"(?ms)^preferred-citation:.*?^\s+doi:\s*([\"']?[^\"'\n]+)",
                "CITATION.cff preferred-citation DOI",
            )
            if preferred_doi != version_doi:
                errors.append("CITATION.cff preferred-citation DOI is not the version DOI")
            for relative, text in doi_surfaces.items():
                for doi in (concept_doi, version_doi):
                    if doi not in text:
                        errors.append(f"{relative} missing DOI {doi}")
            if version_doi not in bibtex[:1200]:
                errors.append("README BibTeX citation is missing the version DOI")
            if codemeta.get("identifier") != f"https://doi.org/{version_doi}":
                errors.append("codemeta.json identifier is not the version DOI")
            if codemeta.get("sameAs") != f"https://doi.org/{concept_doi}":
                errors.append("codemeta.json sameAs is not the concept DOI")
        else:
            preferred_doi = _field(
                "CITATION.cff",
                r"(?ms)^preferred-citation:.*?^\s+doi:\s*([\"']?[^\"'\n]+)",
                "CITATION.cff preferred-citation DOI",
            )
            if preferred_doi != concept_doi:
                errors.append(
                    "CITATION.cff preferred-citation DOI is not the concept DOI "
                    "for an unarchived release"
                )
            for relative, text in doi_surfaces.items():
                if concept_doi not in text:
                    errors.append(f"{relative} missing DOI {concept_doi}")
            if concept_doi not in bibtex[:1200]:
                errors.append("README BibTeX citation is missing the concept DOI")
            if codemeta.get("identifier") != f"https://doi.org/{concept_doi}":
                errors.append("codemeta.json identifier is not the concept DOI")
            if codemeta.get("sameAs") != f"https://doi.org/{concept_doi}":
                errors.append("codemeta.json sameAs is not the concept DOI")

    if errors:
        raise SystemExit("public metadata check failed:\n- " + "\n- ".join(errors))
    print(
        f"public metadata ok (version {version}; {len(CURRENT_SURFACES)} current surfaces checked)"
    )


if __name__ == "__main__":
    main()
