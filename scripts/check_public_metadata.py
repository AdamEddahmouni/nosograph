"""Validate public-facing version, citation, and repository URL consistency."""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _pyproject_version() -> str:
    text = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
    match = re.search(r'(?m)^version\s*=\s*"([^"]+)"', text)
    if not match:
        raise SystemExit("pyproject.toml version not found")
    return match.group(1)


def _citation_field(name: str) -> str:
    text = (ROOT / "CITATION.cff").read_text(encoding="utf-8")
    match = re.search(rf"(?m)^{name}:\s*[\"']?([^\"'\n]+)", text)
    if not match:
        raise SystemExit(f"CITATION.cff {name} not found")
    return match.group(1).strip().strip('"')


def _status_version() -> str:
    text = (ROOT / "docs/generated/public-status.yaml").read_text(encoding="utf-8")
    match = re.search(r'(?m)^version:\s*"([^"]+)"', text)
    if not match:
        raise SystemExit("public-status.yaml version not found")
    return match.group(1)


def _changelog_has_version(version: str) -> bool:
    text = (ROOT / "CHANGELOG.md").read_text(encoding="utf-8")
    return f"## [{version}]" in text


STALE_PUBLIC = (
    "https://github.com/AdamEddahmouni/med-research",
)


def main() -> None:
    version = _pyproject_version()
    citation_version = _citation_field("version")
    citation_repo = _citation_field("repository-code")
    status_version = _status_version()
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    errors: list[str] = []

    if citation_version != version:
        errors.append(f"CITATION.cff version {citation_version} != pyproject {version}")
    if status_version != version:
        errors.append(f"public-status.yaml version {status_version} != pyproject {version}")
    if f"v{version}" not in readme and version not in readme:
        errors.append("README.md does not mention the current version")
    if "https://github.com/AdamEddahmouni/nosograph" not in readme:
        errors.append("README.md missing canonical repository URL")
    if not _changelog_has_version(version):
        errors.append(f"CHANGELOG.md missing ## [{version}] heading")
    if "nosograph" not in citation_repo:
        errors.append(f"CITATION.cff repository-code is not nosograph: {citation_repo}")

    for label, text in {
        "README.md": readme,
        "CITATION.cff": (ROOT / "CITATION.cff").read_text(encoding="utf-8"),
        "SECURITY.md": (ROOT / "SECURITY.md").read_text(encoding="utf-8"),
        ".github/SUPPORT.md": (ROOT / ".github/SUPPORT.md").read_text(encoding="utf-8"),
    }.items():
        for stale in STALE_PUBLIC:
            if stale in text:
                errors.append(f"{label} contains stale public URL {stale}")

    bibtex = readme.split("```bibtex", 1)[-1] if "```bibtex" in readme else ""
    if version not in bibtex[:800]:
        errors.append(f"README BibTeX citation is missing version {version}")
    if "AdamEddahmouni/med-research" in bibtex:
        errors.append("README BibTeX still points at med-research")

    init_text = (ROOT / "src/med_research/__init__.py").read_text(encoding="utf-8")
    if f'__version__ = "{version}"' not in init_text:
        errors.append("src/med_research/__init__.py __version__ does not match pyproject")
    codemeta = (ROOT / "codemeta.json").read_text(encoding="utf-8")
    if f'"{version}"' not in codemeta:
        errors.append("codemeta.json is missing the current version")

    if errors:
        raise SystemExit("public metadata check failed:\n- " + "\n- ".join(errors))
    print(f"public metadata ok (version {version})")


if __name__ == "__main__":
    main()
