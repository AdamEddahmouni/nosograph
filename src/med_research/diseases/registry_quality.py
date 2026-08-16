"""Registry admission gates and non-disease slug detection."""

from __future__ import annotations

import re
from typing import Any

# Known biological-process slugs that slipped into the registry.
NON_DISEASE_BLOCKLIST: frozenset[str] = frozenset(
    {
        "positive_regulation_of_ovulation",
        "sensory_perception_of_sound",
    }
)

_GO_PROCESS_PATTERNS = re.compile(
    r"(?:^|_)(?:positive|negative|regulation)_of_|"
    r"(?:^|_)response_to_|"
    r"(?:^|_)sensory_perception_of_|"
    r"(?:^|_)biological_process",
    re.I,
)


def is_blocked_slug(disease_id: str) -> bool:
    slug = (disease_id or "").strip().lower()
    return slug in NON_DISEASE_BLOCKLIST


def looks_like_go_process_slug(disease_id: str) -> bool:
    slug = (disease_id or "").strip().lower()
    if is_blocked_slug(slug):
        return True
    return bool(_GO_PROCESS_PATTERNS.search(slug))


def has_valid_disease_identifier(entry: dict[str, Any]) -> bool:
    efo = str(entry.get("efo_id") or "").strip()
    mondo = str(entry.get("mondo_id") or "").strip()
    if efo.startswith("EFO_") or efo.startswith("EFO:"):
        return True
    return mondo.startswith("MONDO:")


def is_disease_like_entry(entry: dict[str, Any]) -> bool:
    """Return True when a registry/candidate entry should be admitted."""
    disease_id = str(entry.get("id") or "").strip()
    if not disease_id:
        return False
    if looks_like_go_process_slug(disease_id):
        return False
    name = str(entry.get("name") or "").lower()
    if "biological process" in name or name.startswith("go:"):
        return False
    return has_valid_disease_identifier(entry) or bool(name)


def filter_disease_entries(entries: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], list[str]]:
    """Drop non-disease entries; return (kept, rejected_ids)."""
    kept: list[dict[str, Any]] = []
    rejected: list[str] = []
    for entry in entries:
        if is_disease_like_entry(entry):
            kept.append(entry)
        else:
            rejected.append(str(entry.get("id", "")))
    return kept, rejected
