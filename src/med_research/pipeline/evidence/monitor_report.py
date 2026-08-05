"""
HTML report generator for Evidence Monitor diff results.
"""

from datetime import datetime
from pathlib import Path


def generate_html_report(diff: dict, prev_snapshot: dict, curr_snapshot: dict) -> str:
    """Generate a standalone HTML report from a snapshot diff.

    Args:
        diff: Output dict from compare_snapshots().
        prev_snapshot: The older snapshot dict.
        curr_snapshot: The newer snapshot dict.

    Returns:
        Path to the generated HTML file.
    """
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
                f'{item.get("title", "Untitled")[:100]}</a>'
                f'<span class="item-meta">[{item.get("year","?")}] {item.get("source_type","")}</span>'
                f'</div>'
            )
        alerts_html += f"""
            <div class="alert-card {badge_class}">
                <div class="alert-header">
                    <span class="alert-icon">{icon}</span>
                    <span class="alert-entity">{a['entity']}</span>
                    <span class="alert-type">({a['type'].replace('_',' ').title()})</span>
                    <span class="alert-severity badge-{a['severity']}">{a['severity'].upper()}</span>
                </div>
                <div class="alert-body">
                    <div class="alert-count">{a['new_count']} new item{'s' if a['new_count'] != 1 else ''}</div>
                    {new_items_html}
                </div>
            </div>
        """

    # Changed queries
    changed_q = changes.get("changed_queries", [])
    changed_q_html = "".join(
        f'<span class="changed-tag">"{q}"</span>' for q in changed_q[:10]
    ) if changed_q else '<span class="no-changes">No changes detected</span>'

    # Changed drugs
    changed_d = changes.get("changed_drugs", [])
    changed_d_html = "".join(
        f'<span class="changed-tag drug">💊 {d}</span>' for d in changed_d[:10]
    ) if changed_d else '<span class="no-changes">No changes detected</span>'

    # Changed genes
    changed_g = changes.get("changed_genes", [])
    changed_g_html = "".join(
        f'<span class="changed-tag gene">🧬 {g}</span>' for g in changed_g[:10]
    ) if changed_g else '<span class="no-changes">No changes detected</span>'

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Evidence Monitor — {curr_id}</title>
<style>
:root {{
    --bg: #0f172a;
    --bg-card: #1e293b;
    --text: #e2e8f0;
    --text-muted: #94a3b8;
    --accent: #06b6d4;
    --accent2: #22d3ee;
    --border: #334155;
    --red: #ef4444;
    --yellow: #f59e0b;
    --green: #22c55e;
}}
*, *::before, *::after {{ box-sizing: border-box; margin: 0; padding: 0; }}
body {{
    font-family: 'Segoe UI', system-ui, -apple-system, sans-serif;
    background: var(--bg);
    color: var(--text);
    line-height: 1.6;
    min-height: 100vh;
}}
.container {{ max-width: 1200px; margin: 0 auto; padding: 24px 32px; }}

.hero {{
    text-align: center;
    padding: 48px 0 32px;
    border-bottom: 1px solid var(--border);
    margin-bottom: 32px;
}}
.hero h1 {{
    font-size: 2.4rem;
    font-weight: 700;
    background: linear-gradient(135deg, var(--accent), var(--accent2));
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
    background-clip: text;
}}
.hero .subtitle {{ color: var(--text-muted); font-size: 1rem; margin-top: 8px; }}
.hero .date {{ color: var(--text-muted); font-size: 0.8rem; margin-top: 4px; }}

.stats-grid {{
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(160px, 1fr));
    gap: 14px;
    margin-bottom: 36px;
}}
.stat-card {{
    background: var(--bg-card);
    border: 1px solid var(--border);
    border-radius: 12px;
    padding: 18px 14px;
    text-align: center;
}}
.stat-value {{ font-size: 1.8rem; font-weight: 700; }}
.stat-label {{ color: var(--text-muted); font-size: 0.75rem; margin-top: 4px; text-transform: uppercase; }}

.section-title {{
    font-size: 1.2rem;
    margin: 32px 0 14px;
    color: var(--accent2);
    border-bottom: 1px solid var(--border);
    padding-bottom: 8px;
}}

/* Changes section */
.changes-grid {{
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(300px, 1fr));
    gap: 20px;
    margin-bottom: 32px;
}}
.change-card {{
    background: var(--bg-card);
    border: 1px solid var(--border);
    border-radius: 12px;
    padding: 20px;
}}
.change-card h3 {{ font-size: 1rem; margin-bottom: 12px; color: var(--accent2); }}
.changed-tag {{
    display: inline-block;
    background: rgba(6, 182, 212, 0.12);
    color: var(--accent2);
    padding: 4px 10px;
    border-radius: 6px;
    font-size: 0.78rem;
    margin: 3px 4px 3px 0;
}}
.changed-tag.drug {{ background: rgba(245, 158, 11, 0.12); color: #f59e0b; }}
.changed-tag.gene {{ background: rgba(167, 139, 250, 0.12); color: #a78bfa; }}
.no-changes {{ color: var(--text-muted); font-style: italic; font-size: 0.85rem; }}

/* Alerts */
.alert-card {{
    background: var(--bg-card);
    border: 1px solid var(--border);
    border-radius: 10px;
    padding: 16px;
    margin-bottom: 12px;
    transition: transform 0.15s, box-shadow 0.15s;
}}
.alert-card:hover {{ transform: translateY(-1px); box-shadow: 0 4px 16px rgba(6,182,212,0.08); }}
.alert-card.alert-high {{ border-left: 3px solid var(--red); }}
.alert-card.alert-medium {{ border-left: 3px solid var(--yellow); }}
.alert-card.alert-low {{ border-left: 3px solid var(--green); }}

.alert-header {{
    display: flex;
    align-items: center;
    gap: 8px;
    flex-wrap: wrap;
    margin-bottom: 8px;
}}
.alert-icon {{ font-size: 1rem; }}
.alert-entity {{ font-weight: 600; }}
.alert-type {{ color: var(--text-muted); font-size: 0.78rem; }}
.alert-severity {{
    padding: 2px 8px;
    border-radius: 10px;
    font-size: 0.65rem;
    font-weight: 700;
    margin-left: auto;
}}
.badge-high {{ background: rgba(239, 68, 68, 0.15); color: var(--red); }}
.badge-medium {{ background: rgba(245, 158, 11, 0.15); color: var(--yellow); }}
.badge-low {{ background: rgba(34, 197, 94, 0.15); color: var(--green); }}

.alert-body {{ padding-left: 24px; }}
.alert-count {{ color: var(--text-muted); font-size: 0.82rem; margin-bottom: 6px; }}
.new-item {{
    margin: 4px 0;
    padding: 4px 0;
    border-bottom: 1px solid rgba(51,65,85,0.3);
}}
.item-link {{
    color: var(--accent2);
    text-decoration: none;
    font-size: 0.82rem;
    display: block;
}}
.item-link:hover {{ text-decoration: underline; }}
.item-meta {{ color: var(--text-muted); font-size: 0.7rem; }}

/* Snapshot info */
.snapshot-info {{
    background: var(--bg-card);
    border: 1px solid var(--border);
    border-radius: 12px;
    padding: 20px;
    margin-bottom: 32px;
}}
.snapshot-info h3 {{ font-size: 1rem; margin-bottom: 10px; }}
.snapshot-row {{
    display: flex;
    justify-content: space-between;
    padding: 5px 0;
    border-bottom: 1px solid rgba(51,65,85,0.2);
    font-size: 0.82rem;
}}
.snapshot-row .label {{ color: var(--text-muted); }}
.snapshot-row .value {{ font-weight: 500; }}

.footer {{
    text-align: center;
    padding: 24px 0;
    color: var(--text-muted);
    font-size: 0.78rem;
    border-top: 1px solid var(--border);
    margin-top: 32px;
}}
</style>
</head>
<body>
<div class="container">
    <div class="hero">
        <h1>📡 Evidence Monitor</h1>
        <p class="subtitle">Continuous monitoring of new publications, trials, and evidence changes</p>
        <p class="date">Generated: {gen_time}</p>
    </div>

    <div class="stats-grid">
        <div class="stat-card">
            <div class="stat-value" style="color:var(--accent2);">{total_changes}</div>
            <div class="stat-label">Total Changes</div>
        </div>
        <div class="stat-card">
            <div class="stat-value" style="color:var(--red);">{len(high_alerts)}</div>
            <div class="stat-label">🔴 High Alerts</div>
        </div>
        <div class="stat-card">
            <div class="stat-value" style="color:var(--yellow);">{len(med_alerts)}</div>
            <div class="stat-label">🟡 Medium Alerts</div>
        </div>
        <div class="stat-card">
            <div class="stat-value" style="color:var(--green);">{len(low_alerts)}</div>
            <div class="stat-label">🟢 Low Alerts</div>
        </div>
        <div class="stat-card">
            <div class="stat-value" style="color:#818cf8;">{hours:.1f}h</div>
            <div class="stat-label">Elapsed Since Last</div>
        </div>
        <div class="stat-card">
            <div class="stat-value" style="color:#c084fc;">{curr_total - prev_total:+d}</div>
            <div class="stat-label">New Evidence Items</div>
        </div>
    </div>

    <div class="snapshot-info">
        <h3>📸 Snapshot Comparison</h3>
        <div class="snapshot-row"><span class="label">Previous</span><span class="value">{prev_id} ({prev_total} items)</span></div>
        <div class="snapshot-row"><span class="label">Current</span><span class="value">{curr_id} ({curr_total} items)</span></div>
        <div class="snapshot-row"><span class="label">Queries</span><span class="value">{prev_queries} → {curr_queries}</span></div>
        <div class="snapshot-row"><span class="label">Drugs Tracked</span><span class="value">{prev_drugs} → {curr_drugs}</span></div>
        <div class="snapshot-row"><span class="label">Genes Tracked</span><span class="value">{prev_genes} → {curr_genes}</span></div>
    </div>

    <h2 class="section-title">📊 Changed Entities</h2>
    <div class="changes-grid">
        <div class="change-card">
            <h3>🔎 Queries ({len(changed_q)})</h3>
            {changed_q_html}
        </div>
        <div class="change-card">
            <h3>💊 Drugs ({len(changed_d)})</h3>
            {changed_d_html}
        </div>
        <div class="change-card">
            <h3>🧬 Genes ({len(changed_g)})</h3>
            {changed_g_html}
        </div>
    </div>

    <h2 class="section-title">🚨 Alerts ({len(alerts)})</h2>
    {alerts_html if alerts else '<div class="no-changes" style="padding:20px;background:var(--bg-card);border-radius:12px;">🎉 No new evidence detected — everything up to date!</div>'}

    <div class="footer">
        Lupus Research Platform · Evidence Monitor · {curr_id}
    </div>
</div>
</body>
</html>"""

    out_path = Path(__file__).parent / "report.html"
    out_path.write_text(html, encoding="utf-8")
    return str(out_path)


def escape_html(text) -> str:
    """Escape HTML special characters."""
    if not text:
        return ""
    return (
        str(text).replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )
