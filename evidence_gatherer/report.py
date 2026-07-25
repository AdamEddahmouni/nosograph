"""Evidence Gatherer HTML Report Generator."""

from datetime import datetime
from pathlib import Path


def escape_html(value):
    if value is None:
        return ""
    return str(value).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;")


def generate_html_report(gathered: dict) -> str:
    """Generate multi-source evidence gathering report."""
    now = datetime.now().strftime("%B %d, %Y at %H:%M")
    results = gathered["all_results"]

    source_icons = {
        "pubmed": "📄", "preprints": "🧪", "patents": "💡",
        "clinical_trials": "🏥", "fda_labels": "💊",
    }
    source_colors = {
        "pubmed": "#60a5fa", "preprints": "#a78bfa", "patents": "#fbbf24",
        "clinical_trials": "#4ade80", "fda_labels": "#f87171",
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
                <div class="highlight-source" style="color:{color}">{icon} {src.replace('_',' ').title()}</div>
                <div class="highlight-title">{title}</div>
                <div class="highlight-year">{r.get('year','?')}</div>
            </div>"""

    # Source breakdown cards
    source_cards = ""
    for src, count in gathered["results_by_source"].items():
        icon = source_icons.get(src, "📌")
        color = source_colors.get(src, "#9ca3af")
        source_cards += f"""
            <div class="stat-card">
                <div class="stat-value" style="color:{color};">{count}</div>
                <div class="stat-label">{icon} {src.replace('_',' ').title()}</div>
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
            crossref_items += f"<li>{a} ↔ {b}: <strong>{p['overlap_count']}</strong> overlapping results</li>"
        crossref_html = f"""
        <h2 class="section-title">🔗 Cross-Source Overlaps</h2>
        <div class="methodology"><ul>{crossref_items}</ul></div>"""

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Evidence Gatherer Report</title>
    <style>
        *, *::before, *::after {{ box-sizing: border-box; margin: 0; padding: 0; }}
        body {{ font-family: 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; background: #0a0a1a; color: #e2e8f0; line-height: 1.6; min-height: 100vh; }}
        .container {{ max-width: 1200px; margin: 0 auto; padding: 24px; }}
        .hero {{ text-align: center; padding: 48px 24px 32px; background: linear-gradient(135deg, rgba(59,130,246,0.15), rgba(16,185,129,0.1), rgba(245,158,11,0.08)); border-radius: 16px; margin-bottom: 32px; }}
        .hero h1 {{ font-size: 2.2rem; font-weight: 800; margin-bottom: 8px; }}
        .hero .subtitle {{ color: #94a3b8; font-size: 1rem; }}
        .hero .date {{ color: #64748b; font-size: 0.82rem; margin-top: 8px; }}
        .hero .query-box {{ margin-top: 16px; padding: 12px 20px; background: rgba(59,130,246,0.15); border: 1px solid rgba(59,130,246,0.3); border-radius: 8px; display: inline-block; font-family: monospace; font-size: 0.9rem; color: #60a5fa; }}
        .stats-grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(160px, 1fr)); gap: 16px; margin-bottom: 32px; }}
        .stat-card {{ background: rgba(30,30,50,0.8); border: 1px solid rgba(100,100,150,0.2); border-radius: 12px; padding: 20px; text-align: center; }}
        .stat-value {{ font-size: 2rem; font-weight: 800; }}
        .stat-label {{ color: #94a3b8; font-size: 0.8rem; margin-top: 4px; text-transform: uppercase; letter-spacing: 0.05em; }}
        .section-title {{ font-size: 1.4rem; font-weight: 700; margin: 32px 0 16px; padding-bottom: 8px; border-bottom: 1px solid rgba(100,100,150,0.2); }}
        .highlights-grid {{ display: grid; grid-template-columns: repeat(auto-fill, minmax(280px, 1fr)); gap: 12px; margin-bottom: 32px; }}
        .highlight-card {{ background: rgba(30,30,50,0.8); border: 1px solid rgba(100,100,150,0.2); border-radius: 10px; padding: 16px; transition: border-color 0.2s; }}
        .highlight-card:hover {{ border-color: rgba(59,130,246,0.4); }}
        .highlight-rank {{ font-size: 0.8rem; color: #64748b; }}
        .highlight-source {{ font-size: 0.78rem; font-weight: 600; }}
        .highlight-title {{ font-size: 0.85rem; margin: 6px 0; line-height: 1.4; }}
        .highlight-year {{ font-size: 0.75rem; color: #64748b; }}
        table {{ width: 100%; border-collapse: collapse; font-size: 0.84rem; background: rgba(30,30,50,0.6); border-radius: 12px; overflow: hidden; }}
        th {{ background: rgba(50,50,70,0.8); padding: 12px 10px; text-align: left; font-weight: 600; color: #94a3b8; font-size: 0.76rem; text-transform: uppercase; letter-spacing: 0.05em; }}
        td {{ padding: 10px; border-bottom: 1px solid rgba(100,100,150,0.1); vertical-align: top; }}
        tr:hover {{ background: rgba(100,100,150,0.08); }}
        .col-rank {{ width: 40px; color: #64748b; text-align: center; }}
        .col-source {{ width: 110px; font-weight: 600; font-size: 0.78rem; }}
        .col-title {{ line-height: 1.5; }}
        .col-year {{ width: 60px; text-align: center; color: #64748b; }}
        .snippet {{ color: #94a3b8; font-size: 0.78rem; }}
        .methodology {{ background: rgba(30,30,50,0.6); border: 1px solid rgba(100,100,150,0.2); border-radius: 12px; padding: 24px; margin: 32px 0; }}
        .methodology h3 {{ margin-bottom: 12px; }}
        .methodology ul {{ padding-left: 20px; color: #94a3b8; }}
        .methodology li {{ margin-bottom: 6px; }}
        footer {{ text-align: center; padding: 32px 0; color: #64748b; font-size: 0.8rem; border-top: 1px solid rgba(100,100,150,0.1); margin-top: 32px; }}
    </style>
</head>
<body>
    <div class="container">
        <div class="hero">
            <h1>🌐 Web-Scale Evidence Gatherer</h1>
            <p class="subtitle">Multi-Source Biomedical Evidence Aggregation — PubMed · Preprints · Clinical Trials · FDA Labels · Patents</p>
            <div class="query-box">🔍 &ldquo;{escape_html(gathered['query'])}&rdquo;</div>
            <p class="date">Generated: {now} · {gathered['elapsed_seconds']}s across {n_sources} sources</p>
        </div>

        <div class="stats-grid">
            <div class="stat-card"><div class="stat-value" style="color:#60a5fa;">{n}</div><div class="stat-label">Total Results</div></div>
            <div class="stat-card"><div class="stat-value" style="color:#a78bfa;">{n_sources}</div><div class="stat-label">Sources Searched</div></div>
            <div class="stat-card"><div class="stat-value" style="color:#60a5fa;">{n_pubmed}</div><div class="stat-label">📄 PubMed</div></div>
            <div class="stat-card"><div class="stat-value" style="color:#4ade80;">{n_trials}</div><div class="stat-label">🏥 Clinical Trials</div></div>
        </div>

        <div class="stats-grid">{source_cards}</div>

        {crossref_html}

        <h2 class="section-title">🌟 Top Evidence Highlights</h2>
        <div class="highlights-grid">{highlights_rows}</div>

        <h2 class="section-title">📋 All Gathered Evidence</h2>
        <table><thead><tr><th>#</th><th>Source</th><th>Title / Snippet</th><th>Year</th></tr></thead><tbody>{table_rows}</tbody></table>

        <div class="methodology">
            <h3>🔬 Methodology</h3>
            <p style="color:#94a3b8;margin-bottom:12px;">The Evidence Gatherer searches <strong style="color:#e2e8f0;">5 biomedical sources</strong> simultaneously:</p>
            <ul>
                <li><strong style="color:#60a5fa;">PubMed (via Europe PMC)</strong> — Peer-reviewed biomedical literature</li>
                <li><strong style="color:#a78bfa;">Preprints (bioRxiv / medRxiv)</strong> — Cutting-edge findings not yet peer-reviewed</li>
                <li><strong style="color:#4ade80;">ClinicalTrials.gov</strong> — Active and recruiting clinical studies</li>
                <li><strong style="color:#f87171;">FDA Labels (DailyMed)</strong> — Approved drug prescribing information</li>
                <li><strong style="color:#fbbf24;">Patents (Europe PMC)</strong> — Intellectual property filings</li>
            </ul>
            <p style="color:#94a3b8;margin-top:12px;font-size:0.82rem;">Results are cross-referenced across sources to identify converging evidence. ⚠️ Computational tool — verify findings with primary sources.</p>
        </div>

        <footer><p>Lupus Research Platform · Evidence Gatherer Module</p><p>⚠️ For research purposes only. Not medical advice.</p></footer>
    </div>
</body>
</html>"""

    report_path = Path(__file__).parent / "report.html"
    report_path.write_text(html, encoding="utf-8")
    return str(report_path)
