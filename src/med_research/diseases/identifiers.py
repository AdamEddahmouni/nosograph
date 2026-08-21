"""Central disease identifier resolution and platform reference constants."""

from __future__ import annotations

import re
from typing import Any

from med_research.diseases.scaffold import load_disease_registry, sanitize_id

# Eight modules validated with ``--strict`` on every CI run (see .github/workflows/test.yml).
CI_VALIDATED_DISEASES: frozenset[str] = frozenset(
    {"sle", "ra", "ms", "ss", "ssc", "t1d", "ibd", "ad"}
)

# Diverse reference diseases for tests, coverage samples, and documentation examples.
# Categories: autoimmune, Mendelian, infectious, neoplastic, neurodegenerative, metabolic.
REFERENCE_DISEASES: tuple[str, ...] = (
    "sle",
    "cystic_fibrosis",
    "tuberculosis",
    "melanoma",
    "als",
    "t2d",
)

# Common aliases → canonical slug (lowercase keys).
DISEASE_ALIASES: dict[str, str] = {
    "lupus": "sle",
    "sle": "sle",
    "systemic lupus erythematosus": "sle",
    "systemic_lupus_erythematosus": "sle",
    "ra": "ra",
    "rheumatoid arthritis": "ra",
    "rheumatoid_arthritis": "ra",
    "ms": "ms",
    "multiple sclerosis": "ms",
    "multiple_sclerosis": "ms",
    "ibd": "ibd",
    "crohn": "ibd",
    "crohns": "ibd",
    "t1d": "t1d",
    "type 1 diabetes": "t1d",
    "type_1_diabetes": "t1d",
    "ad": "ad",
    "alzheimer": "ad",
    "alzheimers": "ad",
    "alzheimer's disease": "ad",
}

_MONDO_RE = re.compile(r"^MONDO:\d+$", re.I)
_EFO_RE = re.compile(r"^EFO[_:]\d+$", re.I)

_registry_slug_by_mondo: dict[str, str] | None = None
_registry_slug_by_efo: dict[str, str] | None = None
_known_slugs: frozenset[str] | None = None


def _load_registry_indexes() -> tuple[dict[str, str], dict[str, str], frozenset[str]]:
    global _registry_slug_by_mondo, _registry_slug_by_efo, _known_slugs
    if _registry_slug_by_mondo is not None:
        return _registry_slug_by_mondo, _registry_slug_by_efo or {}, _known_slugs or frozenset()

    mondo_index: dict[str, str] = {}
    efo_index: dict[str, str] = {}
    slugs: set[str] = set()
    for entry in load_disease_registry():
        slug = sanitize_id(entry.get("id", ""))
        if not slug:
            continue
        slugs.add(slug)
        mondo = str(entry.get("mondo_id") or "").strip().upper()
        if mondo.startswith("MONDO:"):
            mondo_index[mondo] = slug
        efo = str(entry.get("efo_id") or "").strip().upper().replace("EFO:", "EFO_")
        if efo.startswith("EFO_"):
            efo_index[efo] = slug

    _registry_slug_by_mondo = mondo_index
    _registry_slug_by_efo = efo_index
    _known_slugs = frozenset(slugs)
    return mondo_index, efo_index, _known_slugs


def invalidate_identifier_cache() -> None:
    """Clear cached registry indexes (e.g. after scaffold generation)."""
    global _registry_slug_by_mondo, _registry_slug_by_efo, _known_slugs
    _registry_slug_by_mondo = None
    _registry_slug_by_efo = None
    _known_slugs = None


def resolve_disease_identifier(raw: str) -> str:
    """Resolve slug, alias, MONDO CURIE, or EFO ID to a canonical disease slug."""
    value = str(raw or "").strip()
    if not value:
        raise ValueError("disease_id must not be empty")

    lowered = value.lower()
    if lowered in DISEASE_ALIASES:
        return DISEASE_ALIASES[lowered]

    slug = sanitize_id(value)
    mondo_index, efo_index, known_slugs = _load_registry_indexes()

    if slug in known_slugs:
        return slug

    upper = value.upper()
    if _MONDO_RE.match(upper):
        mondo_key = upper if upper.startswith("MONDO:") else f"MONDO:{upper.split(':')[-1]}"
        if mondo_key in mondo_index:
            return mondo_index[mondo_key]

    efo_norm = upper.replace("EFO:", "EFO_")
    if _EFO_RE.match(efo_norm) and efo_norm in efo_index:
        return efo_index[efo_norm]

    from med_research.diseases.base import Disease

    if slug in Disease.list_all():
        return slug

    raise ValueError(
        f"unknown disease identifier: {raw!r}. Use a disease slug, alias, MONDO CURIE, or EFO ID."
    )


def require_disease_identifier(raw: str | None) -> str:
    """Resolve a disease identifier or raise when none was supplied."""
    if raw is None or not str(raw).strip():
        raise ValueError("disease_id is required")
    return resolve_disease_identifier(raw)


def default_disease_for_selection(*, prefer_ci_validated: bool = True) -> str:
    """Return a generic default disease slug (never hard-coded to SLE).

    Prefers the first CI-validated module that exists on disk, otherwise the
    first lexicographic registry slug.
    """
    from med_research.diseases.base import Disease

    available = set(Disease.list_all())
    if prefer_ci_validated:
        for did in sorted(CI_VALIDATED_DISEASES):
            if did in available:
                return did
    if available:
        return sorted(available)[0]
    raise RuntimeError("no disease modules available")


def add_required_disease_cli_argument(
    parser: Any, *, help_text: str = "Disease ID (required)"
) -> None:
    """Register a required ``--disease`` / ``-d`` argument on an argparse parser."""
    parser.add_argument("--disease", "-d", required=True, help=help_text)
