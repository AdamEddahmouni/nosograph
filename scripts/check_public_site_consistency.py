"""Post-build public-site consistency checks for the built MkDocs output.

Complements check_public_metadata.py (source-level) by validating the SHIPPED
tree under site/:

  1. robots.txt exists and points at the production sitemap.
  2. sitemap.xml URLs use the production base and never reference internal
     QA/planning areas or legacy prototype-version pages.
  3. Every built page has exactly one non-empty meta description, a real
     title, no leaked {{NG_*}} placeholders, and production-based
     canonical/og:url URLs when present.

Run after `mkdocs build --strict`. Exit code 0 = clean, 1 = defects found.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SITE = ROOT / "site"

PRODUCTION_BASE = "https://adameddahmouni.github.io/nosograph/"
SITEMAP_URL = PRODUCTION_BASE + "sitemap.xml"

# Internal/QA/legacy areas that must never ship in the public build.
FORBIDDEN_SITEMAP_PREFIXES = (
    "audits/",
    "superpowers/",
    "roadmaps/",
    "media/",
    "style-test",
    "public-launch",
    "release-notes/v2.",
    "deployment/public-demo",
    "project/launch-copy",
    "project/github-discussions-seed",
    "project/github-public-settings",
    "project/adoption-metrics",
    "project/openssf-readiness",
    "project/release-notes-template",
    "project/zenodo-setup",
    "architecture/commercialization-boundaries",
    "architecture/decisions/",
)

BAD_HOST_PATTERN = re.compile(r"https?://(localhost|127\.0\.0\.1)|file://")
PLACEHOLDER_PATTERN = re.compile(r"\{\{NG_[A-Z_]+\}\}")
DESCRIPTION_PATTERN = re.compile(
    r"<meta name=\"description\" content=\"([^\"]*)\"\s*/?>"
)
TITLE_PATTERN = re.compile(r"<title>([^<]*)</title>")
CANONICAL_PATTERN = re.compile(r"<link rel=\"canonical\" href=\"([^\"]+)\"")


def _defects() -> list[str]:
    defects: list[str] = []

    if not SITE.is_dir():
        return [f"built site missing at {SITE}; run `mkdocs build --strict` first"]

    # --- robots.txt -------------------------------------------------------
    robots = SITE / "robots.txt"
    if not robots.is_file():
        defects.append("robots.txt missing from build")
    else:
        text = robots.read_text(encoding="utf-8")
        if SITEMAP_URL not in text:
            defects.append(f"robots.txt does not declare production sitemap {SITEMAP_URL}")

    # --- sitemap.xml ------------------------------------------------------
    sitemap = SITE / "sitemap.xml"
    if not sitemap.is_file():
        defects.append("sitemap.xml missing from build")
    else:
        stext = sitemap.read_text(encoding="utf-8")
        urls = re.findall(r"<loc>([^<]+)</loc>", stext)
        for url in urls:
            if not url.startswith(PRODUCTION_BASE):
                defects.append(f"sitemap URL outside production base: {url}")
            elif BAD_HOST_PATTERN.search(url):
                defects.append(f"sitemap URL uses local host: {url}")
        for url in urls:
            rel = url[len(PRODUCTION_BASE):]
            for prefix in FORBIDDEN_SITEMAP_PREFIXES:
                if rel.startswith(prefix):
                    defects.append(f"internal page in sitemap: {rel}")

    # --- per-page checks --------------------------------------------------
    pages = sorted(SITE.rglob("index.html"))
    for page in pages:
        html = page.read_text(encoding="utf-8", errors="ignore")
        rel = page.relative_to(SITE).as_posix()

        descriptions = DESCRIPTION_PATTERN.findall(html)
        if len(descriptions) != 1:
            defects.append(f"{rel}: expected 1 meta description, found {len(descriptions)}")
        elif not descriptions[0].strip():
            defects.append(f"{rel}: empty meta description")

        title_match = TITLE_PATTERN.search(html)
        if not title_match or not title_match.group(1).strip():
            defects.append(f"{rel}: missing or empty <title>")

        if PLACEHOLDER_PATTERN.search(html):
            defects.append(f"{rel}: leaked {{NG_*}} placeholder")

        for pattern, label in ((CANONICAL_PATTERN, "canonical"),):
            match = pattern.search(html)
            if match:
                url = match.group(1)
                if BAD_HOST_PATTERN.search(url) or not url.startswith(PRODUCTION_BASE):
                    defects.append(f"{rel}: {label} URL is not production-based: {url}")

    # --- social preview asset --------------------------------------------
    og_image = SITE / "assets/brand/social-preview.png"
    if not og_image.is_file():
        defects.append("og:image asset missing: assets/brand/social-preview.png")

    return defects


def main() -> int:
    defects = _defects()
    if defects:
        print(f"public site consistency FAILED ({len(defects)} defect(s)):")
        for defect in defects:
            print(f"  - {defect}")
        return 1
    pages = sum(1 for _ in SITE.rglob("index.html"))
    print(f"public site consistency ok ({pages} pages; robots, sitemap, metadata, canonicals)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
