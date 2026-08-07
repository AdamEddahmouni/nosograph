"""Shared disease-derived display context for reports and exports."""

from __future__ import annotations

from html import escape
from typing import Any

from med_research.diseases.base import Disease


def provenance_footer_html(provenance: dict[str, Any] | None) -> str:
    """Render a concise reproducibility footer from build_provenance() output."""
    if not provenance:
        return ""
    fingerprint = escape(str(provenance.get("fingerprint", "not available")))
    generated = escape(str(provenance.get("generated_at", "not available")))
    cache_mode = escape(str(provenance.get("cache_or_live", "unknown")))
    run_id = escape(str(provenance.get("run_id", "not available")))
    return (
        '<div class="meta provenance"><strong>Reproducibility:</strong> '
        f'run <code>{run_id}</code> · fingerprint <code>{fingerprint}</code> · '
        f"generated {generated} · mode {cache_mode}"
        "</div>"
    )


def disease_context(disease_id: str = "sle") -> dict[str, str]:
    """Return stable display labels derived from the active disease config."""
    disease = Disease(str(disease_id).strip().lower())
    try:
        name = disease.get_display_name()
    except (OSError, ValueError, UnicodeDecodeError):
        # Report generation in fixture-only tests may use a temporary/empty
        # disease data directory; retain the stable legacy label in that case.
        name = "Lupus (SLE)" if disease.disease_id == "sle" else disease.disease_id.upper()
    try:
        profile_name = disease.profile.name
    except (OSError, ValueError, UnicodeDecodeError):
        profile_name = name
    return {
        "id": disease.disease_id,
        "name": name,
        "name_html": escape(name),
        "profile_name": profile_name,
        "profile_name_html": escape(profile_name),
        "name_jinja": name,
        "profile_name_jinja": profile_name,
        "report_name": "Lupus" if disease.disease_id == "sle" else name,
        "short_label": disease.disease_id.upper(),
    }


def apply_disease_labels(content: str, disease_id: str = "sle") -> str:
    """Replace legacy SLE copy in rendered reports for non-SLE contexts."""
    context = disease_context(disease_id)
    if context["id"] == "sle":
        return content
    # This helper runs after Jinja has rendered HTML. Use escaped replacement
    # values so names containing &, quotes, or angle brackets cannot become
    # markup and are not double-escaped by a second template pass.
    replacements = (
        ("Lupus (SLE)", context["name_html"]),
        ("Systemic Lupus Erythematosus", context["profile_name_html"]),
        ("Lupus", context["profile_name_html"]),
        ("lupus", escape(context["profile_name"].lower())),
        ("SLE", context["short_label"]),
        ("sle", context["short_label"].lower()),
    )
    for old, new in replacements:
        content = content.replace(old, new)
    return content
