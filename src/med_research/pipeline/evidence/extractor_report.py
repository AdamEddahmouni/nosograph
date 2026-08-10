"""
HTML report generator for LLM Evidence Extractor results.
"""

from datetime import datetime
from pathlib import Path
from typing import Any

from med_research.pipeline.reporting import disease_context, render_report


def generate_html_report(
    results: dict,
    *,
    provenance: dict | None = None,
    disease_id: str | None = None,
) -> str:
    """Generate a standalone HTML report from LLM extraction results.

    Args:
        results: Output dict from extract_all().

    Returns:
        Path to the generated HTML file.
    """
    resolved_disease_id = disease_id or (provenance or {}).get("disease_id", "sle")
    context = disease_context(resolved_disease_id)
    query = results.get("query", "")
    model = results.get("model", "?")
    total = results.get("total_extracted", 0)
    successful = results.get("successful_extractions", 0)
    elapsed = results.get("elapsed_seconds", 0)
    extractions = results.get("extractions", [])
    stats = results.get("stats", {})
    gen_time = datetime.now().strftime("%B %d, %Y at %H:%M")

    # Evidence level distribution for chart
    ev_levels = stats.get("evidence_levels", {})
    ev_labels = [k.replace("_", " ").title() for k in ev_levels]
    ev_values = list(ev_levels.values())

    # Model system distribution
    ms_levels = stats.get("model_systems", {})
    ms_labels = [k.replace("_", " ").title() for k in ms_levels]
    ms_values = list(ms_levels.values())

    # Top extractions sorted by confidence * relevance
    scored = sorted(
        extractions,
        key=lambda x: x.get("relevance_to_query", 50) * x.get("confidence", 0),
        reverse=True,
    )



    # Build extractions table rows
    rows_html = ""
    for i, e in enumerate(scored, 1):
        level = e.get("evidence_level", "?").replace("_", " ").title()
        label_level = level.lower().replace(" ", "-")
        system = e.get("model_system", "?").replace("_", " ").title()
        finding = e.get("key_findings", "—")[:200]
        drugs = ", ".join(e.get("drugs_mentioned", [])[:4]) or "—"
        confidence = e.get("confidence", 0)
        conf_color = (
            "#4ade80" if confidence >= 80 else
            "#fbbf24" if confidence >= 50 else
            "#f87171"
        )
        rel = e.get("relevance_to_query", 50)
        year = e.get("year", "?")
        source = e.get("source_type", "?")

        rows_html += f"""
            <tr>
                <td class="col-rank">{i}</td>
                <td class="col-title">
                    <div class="ext-title">{e.get("title", "")[:120]}</div>
                    <div class="ext-meta">[{year}] {source.upper()} · {e.get("source", "")[:40]}</div>
                </td>
                <td class="col-level">
                    <span class="badge badge-{label_level}">{level}</span>
                </td>
                <td class="col-system">{system}</td>
                <td class="col-drugs">{drugs}</td>
                <td class="col-findings">{finding}</td>
                <td class="col-confidence">
                    <span style="color:{conf_color}">{confidence}</span>
                </td>
                <td class="col-relevance">
                    <div class="mini-bar">
                        <div class="mini-bar-fill" style="width:{rel}%;background:{conf_color};"></div>
                    </div>
                    {rel}
                </td>
            </tr>
        """

    # Study design stats
    sd_html = ""
    for design, count in stats.get("study_designs", {}).items():
        label = design.replace("_", " ").title()
        sd_html += f'<div class="stat-row"><span class="stat-key">{label}</span><span class="stat-val">{count}</span></div>'

    # Drugs list
    drugs_html = ""
    unique_drugs = stats.get("unique_drugs_mentioned", [])
    if unique_drugs:
        drugs_html = '<div class="drug-list">' + "".join(
            f'<span class="drug-tag">{d}</span>' for d in unique_drugs[:20]
        ) + "</div>"

    _EV_CHART_COLORS = [
        "#a78bfa", "#c4b5fd", "#4ade80", "#fbbf24", "#fcd34d",
        "#f87171", "#fca5a5", "#818cf8", "#94a3b8",
    ]
    _MS_CHART_COLORS = [
        "#818cf8", "#4ade80", "#fbbf24", "#f87171", "#c084fc", "#fb923c", "#34d399",
    ]

    def _chart_bars(labels: list[str], values: list[int], colors: list[str]) -> str:
        if not labels:
            return '<p style="color:var(--text-muted);">No data</p>'
        max_val = max(values) if values else 0
        rows = []
        for i, (label, value) in enumerate(zip(labels, values, strict=True)):
            width = (value / max_val * 100) if max_val else 0
            color = colors[i % len(colors)]
            rows.append(
                f'<div class="chart-bar-row"><span class="chart-bar-label">{label}</span>'
                f'<div class="chart-bar-track"><div class="chart-bar-fill" '
                f'style="width:{width}%;background:{color};"></div></div>'
                f'<span class="chart-bar-value">{value}</span></div>'
            )
        return "".join(rows)

    evidence_chart_html = _chart_bars(ev_labels, ev_values, _EV_CHART_COLORS)
    model_system_chart_html = _chart_bars(ms_labels, ms_values, _MS_CHART_COLORS)

    html = render_report(
        "reports/evidence_extractor.html",
        {
            "query_title": query[:50],
            "disease_name": context["name"],
            "generated_at": gen_time,
            "total_extracted": total,
            "successful_extractions": successful,
            "model": model,
            "elapsed_seconds": elapsed,
            "avg_confidence": f"{stats.get('avg_confidence', 0):.0f}",
            "n_unique_drugs": stats.get("n_unique_drugs", 0),
            "evidence_chart_html": evidence_chart_html,
            "model_system_chart_html": model_system_chart_html,
            "study_designs_html": sd_html or '<p style="color:var(--text-muted);">No data</p>',
            "drugs_html": drugs_html or '<p style="color:var(--text-muted);">No drug mentions found</p>',
            "rows_html": rows_html,
            "query": query,
        },
        resolved_disease_id,
        provenance=provenance,
    )

    out_path = Path(__file__).parent / "report.html"
    out_path.write_text(html, encoding="utf-8")
    return str(out_path)


def escape_html(text: Any) -> str:
    """Escape HTML special characters."""
    if not text:
        return ""
    return (
        str(text).replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )
