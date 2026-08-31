"""Validate the self-hosted public font bundle and its CSS loading contract."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
FONT_DIR = ROOT / "docs" / "assets" / "fonts"
MANIFEST_PATH = FONT_DIR / "manifest.json"
CSS_PATH = ROOT / "docs" / "stylesheets" / "base.css"


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _validate_format(path: Path, font_format: str) -> bool:
    with path.open("rb") as stream:
        header = stream.read(4)
    if font_format == "woff2":
        return header == b"wOF2"
    if font_format == "truetype":
        return header in {b"\x00\x01\x00\x00", b"true"}
    return False


def _font_entries() -> list[dict[str, Any]]:
    try:
        payload = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise SystemExit(f"could not read font manifest: {exc}") from exc
    entries = payload.get("fonts")
    if not isinstance(entries, list) or not entries:
        raise SystemExit("font manifest must contain a non-empty fonts list")
    return entries


def main() -> None:
    errors: list[str] = []
    if not MANIFEST_PATH.is_file():
        errors.append("missing docs/assets/fonts/manifest.json")
        entries: list[dict[str, Any]] = []
    else:
        entries = _font_entries()

    license_path = FONT_DIR / "OFL-1.1.txt"
    if not license_path.is_file():
        errors.append("missing docs/assets/fonts/OFL-1.1.txt")
    else:
        license_text = license_path.read_text(encoding="utf-8")
        if "SIL OPEN FONT LICENSE Version 1.1" not in license_text:
            errors.append("OFL-1.1.txt is not the SIL Open Font License 1.1")

    css = CSS_PATH.read_text(encoding="utf-8") if CSS_PATH.is_file() else ""
    if not css:
        errors.append("missing docs/stylesheets/base.css")
    for external_url in ("fonts.googleapis.com", "fonts.gstatic.com", "use.typekit.net"):
        if external_url in css:
            errors.append(f"CSS contains an external font dependency: {external_url}")

    manifest_files: list[str] = []
    referenced_files: set[str] = set()
    for entry in entries:
        filename = entry.get("file")
        family = entry.get("family")
        font_format = entry.get("format")
        expected_hash = entry.get("sha256")
        if not all(isinstance(value, str) and value for value in (filename, family, font_format)):
            errors.append("font manifest contains an incomplete font entry")
            continue
        path = FONT_DIR / filename
        if not path.is_file():
            errors.append(f"missing font file: docs/assets/fonts/{filename}")
            continue
        if path.stat().st_size < 1024:
            errors.append(f"font file is unexpectedly small: docs/assets/fonts/{filename}")
        if not _validate_format(path, font_format):
            errors.append(f"font file format does not match manifest: {filename}")
        if _sha256(path) != expected_hash:
            errors.append(f"SHA-256 mismatch: docs/assets/fonts/{filename}")
        if f'font-family: "{family}";' not in css:
            errors.append(f"CSS has no @font-face declaration for {family}")
        if f'url("../assets/fonts/{filename}")' not in css:
            errors.append(f"CSS does not load local font file: {filename}")
        if f"font-weight: {entry.get('weight_range')};" not in css:
            errors.append(f"CSS weight range is missing for {family}")
        manifest_files.append(filename)
        referenced_files.add(filename)

    if len(manifest_files) != len(referenced_files):
        errors.append("font manifest contains duplicate file entries")
    bundled_files = {
        path.name
        for path in FONT_DIR.iterdir()
        if path.is_file() and path.suffix.lower() in {".ttf", ".woff", ".woff2"}
    }
    unlisted_files = sorted(bundled_files - referenced_files)
    if unlisted_files:
        errors.append("font files missing from manifest: " + ", ".join(unlisted_files))
    if "font-display: swap;" not in css:
        errors.append("CSS @font-face declarations must use font-display: swap")

    if errors:
        raise SystemExit("public font check failed:\n- " + "\n- ".join(errors))
    print(
        f"public fonts ok ({len(entries)} variable families; local loading and checksums verified)"
    )


if __name__ == "__main__":
    main()
