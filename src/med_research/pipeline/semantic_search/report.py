"""Semantic Search HTML Report Generator."""

from collections.abc import Mapping
from datetime import datetime
from pathlib import Path
from typing import Any

from med_research.pipeline.provenance import ProvenanceMetadata
from med_research.pipeline.reporting import disease_context, render_report


def escape_html(value):
    if value is None:
        return ""
    return (
        str(value)
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )


def generate_semantic_report(
    results: list,
    query: str,
    indexed_count: int,
    disease_id: str = "sle",
    *,
    provenance: ProvenanceMetadata | Mapping[str, Any] | None = None,
) -> str:
    """Generate semantic search results report."""
    context = disease_context(disease_id)
    html = render_report(
        "reports/semantic_search.html",
        {
            "results": results,
            "query": query,
            "indexed_count": indexed_count,
            "n_results": len(results),
            "generated_at": datetime.now().strftime("%B %d, %Y at %H:%M"),
            "ctx_disease": context["name"],
            "ctx_disease_id": context["id"],
        },
        disease_id,
        provenance=provenance,
    )

    report_path = Path(__file__).parent / "report.html"
    report_path.write_text(html, encoding="utf-8")
    return str(report_path)
