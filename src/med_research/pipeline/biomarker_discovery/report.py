"""Biomarker Discovery HTML Report Generator."""

import json
from datetime import datetime
from pathlib import Path


def escape_html(value):
    if value is None:
        return ""
    return str(value).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;")


def generate_html_report(results: list) -> str:
    """Generate integrated biomarker discovery report."""
    now = datetime.now().strftime("%B %d, %Y at %H:%M")
    scored = sorted(results, key=lambda x: x["composite_score"], reverse=True)
    n = len(scored)

    scores = [r["composite_score"] for r in scored]
    avg_score = sum(scores) / len(scores) if scores else 0
    tier1 = sum(1 for r in scored if r["composite_score"] >= 8.0)
    tier2 = sum(1 for r in scored if 6.5 <= r["composite_score"] < 8.0)
    tier3 = sum(1 for r in scored if 5.0 <= r["composite_score"] < 6.5)

    # Radar chart top-5
    top5_items = []
    for r in scored[:5]:
        top5_items.append({
            "name": r.get("gene_name", "")[:25],
            "scores": [
                r.get("cross_module_consistency", 0),
                r.get("expression_predictiveness", 0),
                r.get("cart_alignment", 0),
                r.get("druggability", 0),
                r.get("biomarker_novelty", 0),
            ],
        })
    top5_json = json.dumps(top5_items)

    # Highlights
    highlights_rows = ""
    for i, r in enumerate(scored[:8], 1):
        highlights_rows += f"""
            <div class="highlight-card">
                <div class="highlight-rank">#{i}</div>
                <div class="highlight-drug">{escape_html(r.get('gene_name', ''))}</div>
                <div class="highlight-score" style="color: #a78bfa;">{r['composite_score']:.1f}</div>
                <div class="highlight-meta">Best: {escape_html(r.get('best_modality', ''))}</div>
            </div>"""

    # Table
    table_rows = ""
    for i, r in enumerate(scored, 1):
        tier_icon = r["tier"].split("—")[0].strip()
        tier_color = {"🔴": "#f87171", "🟠": "#fb923c", "🟡": "#fbbf24", "🟢": "#4ade80"}.get(
            tier_icon[0] if tier_icon else "", "#9ca3af")
        table_rows += f"""
            <tr>
                <td class="col-rank">{i}</td>
                <td class="col-drug">{escape_html(r.get('gene_name', ''))}</td>
                <td class="col-score" style="color:{tier_color}">{r['composite_score']:.2f}</td>
                <td class="col-sign">{r.get('cross_module_consistency', '-')}</td>
                <td class="col-overlap">{r.get('expression_predictiveness', '-')}</td>
                <td class="col-cell">{r.get('cart_alignment', '-')}</td>
                <td class="col-evid">{r.get('druggability', '-')}</td>
                <td class="col-dir">{r.get('best_modality', '-')}</td>
                <td class="col-tier" style="color:{tier_color}">{r['tier']}</td>
            </tr>"""

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Biomarker Discovery Report</title>
    <script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.7/dist/chart.umd.min.js"></script>
    <style>
        *, *::before, *::after {{ box-sizing: border-box; margin: 0; padding: 0; }}
        body {{ font-family: 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; background: #0a0a1a; color: #e2e8f0; line-height: 1.6; min-height: 100vh; }}
        .container {{ max-width: 1200px; margin: 0 auto; padding: 24px; }}
        .hero {{ text-align: center; padding: 48px 24px 32px; background: linear-gradient(135deg, rgba(147,51,234,0.15), rgba(59,130,246,0.1), rgba(220,38,38,0.08)); border-radius: 16px; margin-bottom: 32px; }}
        .hero h1 {{ font-size: 2.2rem; font-weight: 800; margin-bottom: 8px; }}
        .hero .subtitle {{ color: #94a3b8; font-size: 1rem; }}
        .hero .date {{ color: #64748b; font-size: 0.82rem; margin-top: 8px; }}
        .stats-grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(180px, 1fr)); gap: 16px; margin-bottom: 32px; }}
        .stat-card {{ background: rgba(30,30,50,0.8); border: 1px solid rgba(100,100,150,0.2); border-radius: 12px; padding: 20px; text-align: center; }}
        .stat-value {{ font-size: 2rem; font-weight: 800; }}
        .stat-label {{ color: #94a3b8; font-size: 0.8rem; margin-top: 4px; }}
        .section-title {{ font-size: 1.4rem; font-weight: 700; margin: 32px 0 16px; padding-bottom: 8px; border-bottom: 1px solid rgba(100,100,150,0.2); }}
        .highlights-grid {{ display: grid; grid-template-columns: repeat(auto-fill, minmax(240px, 1fr)); gap: 12px; margin-bottom: 32px; }}
        .highlight-card {{ background: rgba(30,30,50,0.8); border: 1px solid rgba(100,100,150,0.2); border-radius: 10px; padding: 16px; text-align: center; transition: border-color 0.2s; }}
        .highlight-card:hover {{ border-color: rgba(147,51,234,0.4); }}
        .highlight-rank {{ font-size: 0.8rem; color: #64748b; }}
        .highlight-drug {{ font-size: 0.9rem; font-weight: 600; margin: 4px 0; }}
        .highlight-score {{ font-size: 1.4rem; font-weight: 700; }}
        .highlight-meta {{ font-size: 0.75rem; color: #64748b; }}
        table {{ width: 100%; border-collapse: collapse; font-size: 0.85rem; background: rgba(30,30,50,0.6); border-radius: 12px; overflow: hidden; }}
        th {{ background: rgba(50,50,70,0.8); padding: 12px 10px; text-align: left; font-weight: 600; color: #94a3b8; font-size: 0.78rem; text-transform: uppercase; letter-spacing: 0.05em; }}
        td {{ padding: 10px; border-bottom: 1px solid rgba(100,100,150,0.1); }}
        tr:hover {{ background: rgba(100,100,150,0.08); }}
        .col-rank {{ width: 40px; color: #64748b; text-align: center; }}
        .col-drug {{ font-weight: 600; }}
        .col-score {{ font-weight: 700; font-size: 1rem; text-align: center; }}
        .col-sign, .col-overlap, .col-cell, .col-evid, .col-dir {{ text-align: center; }}
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
            <h1>🧬 Biomarker Discovery Report</h1>
            <p class="subtitle">Cross-Module Integration — Correlating Gene Signatures Across 5 Scoring Platforms</p>
            <p class="date">Generated: {now}</p>
        </div>

        <div class="stats-grid">
            <div class="stat-card"><div class="stat-value" style="color:#a78bfa;">{n}</div><div class="stat-label">Genes Analyzed</div></div>
            <div class="stat-card"><div class="stat-value" style="color:#4ade80;">{avg_score:.2f}</div><div class="stat-label">Average Score</div></div>
            <div class="stat-card"><div class="stat-value" style="color:#f87171;">{tier1}</div><div class="stat-label">Strong Biomarkers</div></div>
            <div class="stat-card"><div class="stat-value" style="color:#fb923c;">{tier2}</div><div class="stat-label">Promising Biomarkers</div></div>
            <div class="stat-card"><div class="stat-value" style="color:#fbbf24;">{tier3}</div><div class="stat-label">Emergent Biomarkers</div></div>
            <div class="stat-card"><div class="stat-value" style="color:#818cf8;">5</div><div class="stat-label">Platforms Integrated</div></div>
        </div>

        <h2 class="section-title">🎯 Score Dimension Radar — Top 5 Biomarkers</h2>
        <div class="radar-container" style="max-width:700px;margin:0 auto 28px;"><canvas id="radarChart" style="max-height:500px;"></canvas></div>

        <h2 class="section-title">🌟 Top Biomarker Candidates</h2>
        <div class="highlights-grid">{highlights_rows}</div>

        <h2 class="section-title">📋 Complete Biomarker Rankings</h2>
        <table><thead><tr><th>#</th><th>Gene</th><th>Score</th><th>Consistency</th><th>Expression</th><th>CAR-T</th><th>Druggable</th><th>Best Modality</th><th>Tier</th></tr></thead><tbody>{table_rows}</tbody></table>

        <div class="methodology">
            <h3>🔬 Methodology</h3>
            <p style="color:#94a3b8;margin-bottom:12px;">The Biomarker Discovery engine integrates results from <strong style="color:#e2e8f0;">5 scoring platforms</strong> to identify genes with the strongest cross-module signal:</p>
            <ul>
                <li><strong style="color:#a78bfa;">Cross-Module Consistency (30%)</strong> — Does the gene score consistently across all platforms?</li>
                <li><strong style="color:#60a5fa;">Expression Predictiveness (25%)</strong> — Does the gene expression signature predict drug response?</li>
                <li><strong style="color:#f87171;">CAR-T Alignment (20%)</strong> — Is the gene B-cell-dependent for immune reset therapy?</li>
                <li><strong style="color:#4ade80;">Druggability (15%)</strong> — Are there existing or repurposable drugs targeting this gene?</li>
                <li><strong style="color:#fbbf24;">Biomarker Novelty (10%)</strong> — How novel is this biomarker in the lupus field?</li>
            </ul>
            <p style="color:#94a3b8;margin-top:12px;font-size:0.82rem;">Platforms integrated: Drug Repurposing · Gene Expression Correlation · CAR-T Response Predictor · Drug Synergy · Adverse Event Profiling</p>
        </div>

        <footer><p>Lupus Research Platform · Biomarker Discovery Module</p><p>⚠️ Computational predictions requiring clinical validation. Not medical advice.</p></footer>
    </div>
    <script>
(function() {{
    const top5 = {top5_json};
    const labels = ['Cross-Module Consistency', 'Expression Predictiveness', 'CAR-T Alignment', 'Druggability', 'Biomarker Novelty'];
    const colors = ['#a78bfa', '#60a5fa', '#f87171', '#4ade80', '#fbbf24'];
    const datasets = top5.map((c, i) => ({{ label: c.name, data: c.scores, borderColor: colors[i], backgroundColor: colors[i] + '18', borderWidth: 2, pointBackgroundColor: colors[i], pointRadius: 4 }}));
    new Chart(document.getElementById('radarChart'), {{ type: 'radar', data: {{ labels, datasets }}, options: {{ responsive: true, maintainAspectRatio: true, scales: {{ r: {{ beginAtZero: true, max: 10, ticks: {{ backdropColor: 'transparent', color: '#787890', font: {{ size: 10 }} }}, grid: {{ color: 'rgba(100,100,150,0.2)' }}, pointLabels: {{ color: '#c0c0d0', font: {{ size: 10 }} }}, angleLines: {{ color: 'rgba(100,100,150,0.2)' }} }} }}, plugins: {{ legend: {{ position: 'bottom', labels: {{ color: '#c0c0d0', font: {{ size: 11 }}, padding: 14, usePointStyle: true }} }} }} }} }});
}})();
</script>
</body>
</html>"""

    report_path = Path(__file__).parent / "report.html"
    report_path.write_text(html, encoding="utf-8")
    return str(report_path)
