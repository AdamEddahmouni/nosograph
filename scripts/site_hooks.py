"""MkDocs hooks — inject authoritative public metadata into template context.

Feeds docs/generated/public-status.yaml (canonical public metrics file, see
check_public_metadata.py) into templates as config.extra.ng_public_status so
the shell never hard-codes release data (audit P0-4). Placeholders fail the
build when the authority file is missing/incomplete: a half-known version or
metric must never reach public metadata.
"""

from __future__ import annotations

import pathlib
import shutil

import yaml

_STATUS_PATH = pathlib.Path(__file__).resolve().parents[1] / "docs" / "generated" / "public-status.yaml"


def _load_public_status() -> dict | None:
    try:
        data = yaml.safe_load(_STATUS_PATH.read_text(encoding="utf-8")) or {}
    except OSError:
        return None
    version = str(data.get("version", "")).strip()
    metrics = data.get("metrics") or {}
    if not version or not isinstance(metrics, dict):
        return None
    required_metrics = {
        "l2_strict_validated": metrics.get("l2_strict_validated"),
        "offline_tests": metrics.get("offline_tests"),
    }
    if any(value in (None, "") for value in required_metrics.values()):
        return None
    return {
        "version": version,
        "maturity": str(data.get("maturity", "")).strip(),
        "release_date": str(data.get("release_date", "")).strip(),
        "metrics": required_metrics,
        "status_page": "project/status/",
    }


def on_config(config):
    status = _load_public_status()
    if status:
        config.extra["ng_public_status"] = status
    return config


_LUNR_DIR = "assets/javascripts/lunr"


def on_post_build(*, config, **kwargs):
    """Drop deploy-only dead weight from site/: sourcemaps and Material's
    vestigial lunr/ tokenizer directory. In Material 9.7.x search runs in a
    self-contained web worker; nothing references assets/javascripts/lunr/
    at runtime, yet ~2.1 MB of tokenizers ship in every build. Deterministic,
    idempotent."""
    site = pathlib.Path(config["site_dir"])
    removed_bytes = 0
    removed_count = 0
    maps: list[pathlib.Path] = list(site.glob("assets/**/*.min.js.map"))
    maps.extend(site.glob("assets/stylesheets/*.min.css.map"))
    for mapping in maps:
        removed_bytes += mapping.stat().st_size
        mapping.unlink()
        removed_count += 1
    lunr_root = site / _LUNR_DIR
    if lunr_root.is_dir():
        for path in sorted(lunr_root.rglob("*"), reverse=True):
            if path.is_file():
                removed_bytes += path.stat().st_size
                removed_count += 1
        shutil.rmtree(lunr_root, ignore_errors=True)
    if removed_count:
        print(f"Removed {removed_count} deploy-only files ({removed_bytes / 1024:.0f} KiB) from site output")
    return config


_TOKENS = ("{{NG_L2_STRICT_VALIDATED}}", "{{NG_OFFLINE_TESTS}}", "{{NG_VERSION}}")


def on_page_markdown(markdown, page, config, **kwargs):
    """Replace public-status placeholders at build time; fail closed."""
    if not any(token in markdown for token in _TOKENS):
        return markdown
    status = config.extra.get("ng_public_status")
    if not status:
        raise RuntimeError(
            f"{page.file.src_uri}: public-status placeholder present but "
            f"{_STATUS_PATH} is missing or incomplete; refusing to publish "
            "placeholder release data"
        )
    metrics = status["metrics"]
    replacements = {
        "{{NG_L2_STRICT_VALIDATED}}": str(metrics["l2_strict_validated"]),
        "{{NG_OFFLINE_TESTS}}": f"{int(metrics['offline_tests']):,}",
        "{{NG_VERSION}}": str(status["version"]),
    }
    for token, value in replacements.items():
        markdown = markdown.replace(token, value)
    return markdown
