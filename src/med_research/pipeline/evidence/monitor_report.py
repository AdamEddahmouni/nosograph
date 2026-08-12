"""
HTML report generator for Evidence Monitor diff results.
"""

from datetime import datetime
from pathlib import Path
from typing import Any

from med_research.pipeline.reporting import disease_context, render_report


def generate_html_report(
    diff: dict,
    prev_snapshot: dict,
    curr_snapshot: dict,
    *,
    provenance: dict | None = None,
    disease_id: str | None = None,
) -> str:
    """Generate a standalone HTML report from a snapshot diff.

    Args:
        diff: Output dict from compare_snapshots().
        prev_snapshot: The older snapshot dict.
        curr_snapshot: The newer snapshot dict.

    Returns:
        Path to the generated HTML file.
    """
    resolved_disease_id = disease_id or (provenance or {}).get("disease_id", "sle")
    context = disease_context(resolved_disease_id)
    prev_id = diff.get("prev_snapshot", "?")
    curr_id = diff.get("curr_snapshot", "?")
    hours = diff.get("hours_elapsed", 0)
    total_changes = diff.get("total_changes", 0)
    alerts = diff.get("alerts", [])
    changes = diff.get("changes", {})
    gen_time = datetime.now().strftime("%B %d, %Y at %H:%M")

    # Counts
    prev_queries = len(prev_snapshot.get("queries", {}))
    curr_queries = len(curr_snapshot.get("queries", {}))
    prev_drugs = len(prev_snapshot.get("drugs", {}))
    curr_drugs = len(curr_snapshot.get("drugs", {}))
    prev_genes = len(prev_snapshot.get("genes", {}))
    curr_genes = len(curr_snapshot.get("genes", {}))

    # Aggregate results
    prev_total = sum(q.get("total", 0) for q in prev_snapshot.get("queries", {}).values())
    curr_total = sum(q.get("total", 0) for q in curr_snapshot.get("queries", {}).values())

    # Alert count by severity
    high_alerts = [a for a in alerts if a["severity"] == "high"]
    med_alerts = [a for a in alerts if a["severity"] == "medium"]
    low_alerts = [a for a in alerts if a["severity"] == "low"]

    # Alert rows
    alerts_html = ""
    for a in alerts:
        icon = {"high": "🔴", "medium": "🟡", "low": "🟢"}.get(a["severity"], "⚪")
        badge_class = f"alert-{a['severity']}"
        new_items_html = ""
        for item in a.get("new_items", [])[:3]:
            new_items_html += (
                f'<div class="new-item">'
                f'<a href="{item.get("url", "#")}" target="_blank" class="item-link">'
                f"{item.get('title', 'Untitled')[:100]}</a>"
                f'<span class="item-meta">[{item.get("year", "?")}] {item.get("source_type", "")}</span>'
                f"</div>"
            )
        alerts_html += f"""
            <div class="alert-card {badge_class}">
                <div class="alert-header">
                    <span class="alert-icon">{icon}</span>
                    <span class="alert-entity">{a["entity"]}</span>
                    <span class="alert-type">({a["type"].replace("_", " ").title()})</span>
                    <span class="alert-severity badge-{a["severity"]}">{a["severity"].upper()}</span>
                </div>
                <div class="alert-body">
                    <div class="alert-count">{a["new_count"]} new item{"s" if a["new_count"] != 1 else ""}</div>
                    {new_items_html}
                </div>
            </div>
        """

    # Changed queries
    changed_q = changes.get("changed_queries", [])
    changed_q_html = (
        "".join(f'<span class="changed-tag">"{q}"</span>' for q in changed_q[:10])
        if changed_q
        else '<span class="no-changes">No changes detected</span>'
    )

    # Changed drugs
    changed_d = changes.get("changed_drugs", [])
    changed_d_html = (
        "".join(f'<span class="changed-tag drug">💊 {d}</span>' for d in changed_d[:10])
        if changed_d
        else '<span class="no-changes">No changes detected</span>'
    )

    # Changed genes
    changed_g = changes.get("changed_genes", [])
    changed_g_html = (
        "".join(f'<span class="changed-tag gene">🧬 {g}</span>' for g in changed_g[:10])
        if changed_g
        else '<span class="no-changes">No changes detected</span>'
    )

    alerts_empty_html = (
        '<div class="no-changes" style="padding:20px;background:var(--bg-card);border-radius:12px;">'
        "🎉 No new evidence detected — everything up to date!</div>"
    )

    html = render_report(
        "reports/evidence_monitor.html",
        {
            "disease_name": context["name"],
            "generated_at": gen_time,
            "curr_snapshot_id": curr_id,
            "total_changes": total_changes,
            "n_high_alerts": len(high_alerts),
            "n_med_alerts": len(med_alerts),
            "n_low_alerts": len(low_alerts),
            "hours_elapsed": f"{hours:.1f}",
            "evidence_delta": f"{curr_total - prev_total:+d}",
            "prev_snapshot_id": prev_id,
            "prev_total": prev_total,
            "curr_total": curr_total,
            "prev_queries": prev_queries,
            "curr_queries": curr_queries,
            "prev_drugs": prev_drugs,
            "curr_drugs": curr_drugs,
            "prev_genes": prev_genes,
            "curr_genes": curr_genes,
            "n_changed_queries": len(changed_q),
            "n_changed_drugs": len(changed_d),
            "n_changed_genes": len(changed_g),
            "changed_queries_html": changed_q_html,
            "changed_drugs_html": changed_d_html,
            "changed_genes_html": changed_g_html,
            "n_alerts": len(alerts),
            "alerts_html": alerts_html if alerts else alerts_empty_html,
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
        str(text)
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )
