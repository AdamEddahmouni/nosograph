"""Evidence Gatherer HTML Report Generator."""

from datetime import datetime
from pathlib import Path

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


def generate_html_report(
    gathered: dict,
    *,
    provenance: dict | None = None,
    disease_id: str | None = None,
) -> str:
    """Generate multi-source evidence gathering report."""
    resolved_disease_id = disease_id or (provenance or {}).get("disease_id", "sle")
    context = disease_context(resolved_disease_id)
    now = datetime.now().strftime("%B %d, %Y at %H:%M")
    results = gathered["all_results"]

    source_icons = {
        "pubmed": "📄",
        "preprints": "🧪",
        "patents": "💡",
        "clinical_trials": "🏥",
        "fda_labels": "💊",
    }
    source_colors = {
        "pubmed": "#60a5fa",
        "preprints": "#a78bfa",
        "patents": "#fbbf24",
        "clinical_trials": "#4ade80",
        "fda_labels": "#f87171",
    }

    # Stats
    n = gathered["total_results"]
    n_sources = len(gathered["results_by_source"])
    n_pubmed = gathered["results_by_source"].get("pubmed", 0)
    n_trials = gathered["results_by_source"].get("clinical_trials", 0)

    # Highlights — top 6 across sources
    highlights_rows = ""
    for i, r in enumerate(results[:6], 1):
        src = r.get("source_type", "pubmed")
        icon = source_icons.get(src, "📌")
        color = source_colors.get(src, "#9ca3af")
        title = escape_html(r.get("title", "")[:80])
        highlights_rows += f"""
            <div class="highlight-card">
                <div class="highlight-rank">#{i}</div>
                <div class="highlight-source" style="color:{color}">{icon} {src.replace("_", " ").title()}</div>
                <div class="highlight-title">{title}</div>
                <div class="highlight-year">{r.get("year", "?")}</div>
            </div>"""

    # Source breakdown cards
    source_cards = ""
    for src, count in gathered["results_by_source"].items():
        icon = source_icons.get(src, "📌")
        color = source_colors.get(src, "#9ca3af")
        source_cards += f"""
            <div class="stat-card">
                <div class="stat-value" style="color:{color};">{count}</div>
                <div class="stat-label">{icon} {src.replace("_", " ").title()}</div>
            </div>"""

    # Results table
    table_rows = ""
    for i, r in enumerate(results[:50], 1):
        src = r.get("source_type", "pubmed")
        color = source_colors.get(src, "#9ca3af")
        icon = source_icons.get(src, "")
        title = escape_html(r.get("title", "")[:100])
        snippet = escape_html(r.get("snippet", "")[:200])
        url = escape_html(r.get("url", ""))
        year = r.get("year", "?")
        src_label = src.replace("_", " ").title()
        table_rows += f"""
            <tr>
                <td class="col-rank">{i}</td>
                <td class="col-source" style="color:{color}">{icon} {src_label}</td>
                <td class="col-title"><a href="{url}" target="_blank" style="color:#e2e8f0;text-decoration:none;">{title}</a><br><span class="snippet">{snippet}</span></td>
                <td class="col-year">{year}</td>
            </tr>"""

    # Crossref section
    crossref_html = ""
    pairs = gathered.get("crossref", {}).get("pairs", [])
    overlap_pairs = [p for p in pairs if p.get("overlap_count", 0) > 0]
    if overlap_pairs:
        crossref_items = ""
        for p in overlap_pairs:
            a = p["source_a"].replace("_", " ").title()
            b = p["source_b"].replace("_", " ").title()
            crossref_items += (
                f"<li>{a} ↔ {b}: <strong>{p['overlap_count']}</strong> overlapping results</li>"
            )
        crossref_html = f"""
        <h2 class="section-title">🔗 Cross-Source Overlaps</h2>
        <div class="methodology"><ul>{crossref_items}</ul></div>"""

    html = render_report(
        "reports/evidence_gatherer.html",
        {
            "disease_name": context["name"],
            "query": escape_html(gathered["query"]),
            "generated_at": now,
            "elapsed_seconds": gathered["elapsed_seconds"],
            "n_sources": n_sources,
            "total_results": n,
            "n_pubmed": n_pubmed,
            "n_trials": n_trials,
            "source_cards": source_cards,
            "crossref_html": crossref_html,
            "highlights_rows": highlights_rows,
            "table_rows": table_rows,
        },
        resolved_disease_id,
        provenance=provenance,
    )

    report_path = Path(__file__).parent / "report.html"
    report_path.write_text(html, encoding="utf-8")
    return str(report_path)
