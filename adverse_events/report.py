"""
Adverse Event Profiling Report Generator

Generates a standalone HTML report with:
  - Safety score distribution and heatmap
  - Ranked drug safety table
  - Per-drug adverse event profiles
  - Black box warning summary
"""

from datetime import datetime
from pathlib import Path


def generate_html_report(safety_results: list) -> str:
    """Generate a standalone HTML report and return the path."""

    output_path = Path(__file__).parent / "report.html"

    n_bbw = sum(1 for r in safety_results if r.get("black_box_warnings"))
    n_dil = sum(1 for r in safety_results if r["dil_risk_score"] < 10.0)
    avg = sum(r["composite_safety_score"] for r in safety_results) / len(safety_results) if safety_results else 0

    # Top-10 safety highlights
    highlight_html = ""
    for i, r in enumerate(safety_results[:10], 1):
        score = r["composite_safety_score"]
        color = "#4ade80" if score >= 7 else "#fbbf24" if score >= 5 else "#f87171"
        highlight_html += f"""        <div class="highlight-card">
            <div class="hl-rank">#{i}</div>
            <div class="hl-drug">{escape_html(r['drug_name'])}</div>
            <div class="hl-score" style="color:{color};">{score:.1f}</div>
            <div class="hl-dims">
                <span class="hl-dim">Lupus Overlap: {r['lupus_symptom_overlap_score']}</span>
                <span class="hl-dim">Severity: {r['severity_burden_score']}</span>
                <span class="hl-dim">Chronic: {r['chronic_use_safety_score']}</span>
                <span class="hl-dim">DIL: {r['dil_risk_score']}</span>
            </div>
        </div>"""

    # Full table
    rows_html = ""
    for i, r in enumerate(safety_results, 1):
        score = r["composite_safety_score"]
        color = "#4ade80" if score >= 7 else "#fbbf24" if score >= 5 else "#f87171"
        bbw = r.get("black_box_warnings", [])
        bbw_badge = f"<span class='bbw-badge'>BBW: {len(bbw)}</span>" if bbw else ""
        rows_html += f"""        <tr>
            <td class="rank">{i}</td>
            <td><strong>{escape_html(r['drug_name'])}</strong></td>
            <td><span style="color:{color};font-weight:700;font-size:1.1em;">{score:.1f}</span></td>
            <td>{r['lupus_symptom_overlap_score']}/10</td>
            <td>{r['severity_burden_score']}/10</td>
            <td>{r['chronic_use_safety_score']}/10</td>
            <td>{r['dil_risk_score']}/10</td>
            <td>{r['n_lupus_overlap_ae']}</td>
            <td>{bbw_badge}</td>
        </tr>"""

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Adverse Event Profiling Report</title>
    <link rel="preconnect" href="https://fonts.googleapis.com">
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap" rel="stylesheet">
    <style>
        * {{ margin: 0; padding: 0; box-sizing: border-box; }}
        body {{
            font-family: 'Inter', system-ui, -apple-system, sans-serif;
            background: #0a0a0f; color: #e0e0e8; line-height: 1.6;
        }}
        .container {{ max-width: 1200px; margin: 0 auto; padding: 20px; }}

        .hero {{
            background: linear-gradient(135deg, #0f1729, #1a0f18, #0f1729);
            border: 1px solid #252535; border-radius: 16px;
            padding: 40px; margin-bottom: 32px; text-align: center;
        }}
        .hero h1 {{
            font-size: 2.2rem; font-weight: 800;
            background: linear-gradient(135deg, #4ade80, #22d3ee, #818cf8);
            -webkit-background-clip: text; background-clip: text;
            -webkit-text-fill-color: transparent; margin-bottom: 8px;
        }}
        .hero .subtitle {{ color: #787890; font-size: 1rem; }}
        .hero .date {{ color: #787890; font-size: 0.8rem; margin-top: 8px; }}

        .stats-grid {{
            display: grid; grid-template-columns: repeat(4, 1fr); gap: 14px;
            margin-bottom: 32px;
        }}
        .stat-card {{
            background: #13131a; border: 1px solid #252535;
            border-radius: 12px; padding: 22px; text-align: center;
        }}
        .stat-card .stat-value {{ font-size: 1.8rem; font-weight: 800; margin-bottom: 4px; }}
        .stat-card .stat-label {{ color: #787890; font-size: 0.78rem; }}

        .section-title {{
            font-size: 1.3rem; font-weight: 700; margin: 32px 0 16px;
            padding-bottom: 8px; border-bottom: 1px solid #252535;
        }}

        .highlights-grid {{
            display: grid; grid-template-columns: repeat(auto-fill, minmax(300px, 1fr));
            gap: 12px; margin-bottom: 28px;
        }}
        .highlight-card {{
            background: #13131a; border: 1px solid #252535;
            border-radius: 10px; padding: 16px;
            transition: border-color 0.2s, transform 0.2s;
        }}
        .highlight-card:hover {{ border-color: #4b5563; transform: translateY(-2px); }}
        .hl-rank {{ font-size: 0.65rem; font-weight: 700; color: #787890; margin-bottom: 4px; }}
        .hl-drug {{ font-weight: 600; font-size: 0.85rem; margin-bottom: 6px; }}
        .hl-score {{ font-size: 1.3rem; font-weight: 800; margin-bottom: 8px; }}
        .hl-dims {{ display: flex; gap: 4px; flex-wrap: wrap; font-size: 0.7rem; }}
        .hl-dim {{
            background: #0a0a0f; border-radius: 5px; padding: 2px 7px;
            font-weight: 600; color: #787890;
        }}

        .table-container {{
            overflow-x: auto; background: #13131a;
            border: 1px solid #252535; border-radius: 12px; margin-bottom: 32px;
        }}
        table {{ width: 100%; border-collapse: collapse; font-size: 0.86rem; }}
        th {{
            text-align: left; padding: 14px 16px; background: #1a1a24;
            color: #787890; font-weight: 600; font-size: 0.73rem;
            text-transform: uppercase; letter-spacing: 0.05em;
            border-bottom: 1px solid #252535;
        }}
        td {{ padding: 11px 16px; border-bottom: 1px solid #1a1a24; }}
        tr:hover td {{ background: rgba(74,222,128,0.02); }}
        .rank {{ font-weight: 700; color: #787890; font-size: 1rem; min-width: 28px; }}
        .bbw-badge {{
            display: inline-block; padding: 2px 8px; border-radius: 12px;
            font-size: 0.68rem; font-weight: 600; background: rgba(248,113,113,0.12);
            color: #f87171; border: 1px solid rgba(248,113,113,0.2);
        }}

        .methodology {{
            background: #13131a; border: 1px solid #252535;
            border-radius: 12px; padding: 24px; margin-bottom: 32px;
        }}
        .methodology h3 {{ font-size: 1rem; margin-bottom: 12px; }}
        .methodology ul {{ margin-left: 20px; color: #787890; font-size: 0.86rem; }}
        .methodology li {{ margin-bottom: 6px; }}
        .methodology strong {{ color: #e0e0e8; }}

        footer {{ text-align: center; padding: 40px; color: #787890; font-size: 0.78rem; }}
        footer a {{ color: #818cf8; }}

        @media (max-width: 768px) {{
            .stats-grid {{ grid-template-columns: repeat(2, 1fr); }}
            .highlights-grid {{ grid-template-columns: 1fr; }}
            .hero {{ padding: 24px; }}
            .hero h1 {{ font-size: 1.4rem; }}
        }}
    </style>
</head>
<body>
    <div class="container">

        <div class="hero">
            <h1>\U0001f6e1\ufe0f Adverse Event Profiling Report</h1>
            <p class="subtitle">Safety Analysis of {len(safety_results)} Drugs from the Lupus Knowledge Graph &mdash; 4-Dimensional Safety Scoring</p>
            <p class="date">Generated: {datetime.now().strftime('%B %d, %Y at %H:%M')} | Lupus-Specific Safety Assessment</p>
        </div>

        <div class="stats-grid">
            <div class="stat-card">
                <div class="stat-value" style="color:#4ade80;">{avg:.1f}</div>
                <div class="stat-label">Average Safety Score</div>
            </div>
            <div class="stat-card">
                <div class="stat-value" style="color:#f87171;">{n_bbw}</div>
                <div class="stat-label">Drugs with Black Box Warnings</div>
            </div>
            <div class="stat-card">
                <div class="stat-value" style="color:#fbbf24;">{n_dil}</div>
                <div class="stat-label">Drugs with DIL Risk</div>
            </div>
            <div class="stat-card">
                <div class="stat-value" style="color:#818cf8;">{len(safety_results)}</div>
                <div class="stat-label">Total Drugs Profiled</div>
            </div>
        </div>

        <h2 class="section-title">\U0001f3c6 Top 10 Safest Drugs</h2>
        <div class="highlights-grid">
            {highlight_html}
        </div>

        <h2 class="section-title">\U0001f4ca Complete Safety Rankings</h2>
        <div class="table-container">
            <table>
                <thead>
                    <tr>
                        <th>#</th>
                        <th>Drug</th>
                        <th>Safety Score</th>
                        <th>Lupus Overlap</th>
                        <th>Severity</th>
                        <th>Chronic Use</th>
                        <th>DIL Risk</th>
                        <th>Overlap AEs</th>
                        <th>BBW</th>
                    </tr>
                </thead>
                <tbody>
                    {rows_html}
                </tbody>
            </table>
        </div>

        <div class="methodology">
            <h3>\U0001f4d0 Methodology &mdash; 4-Dimensional Safety Scoring</h3>
            <ul>
                <li><strong>Lupus Symptom Overlap (35%)</strong> &mdash; Do adverse events mimic lupus symptoms? Higher overlap = lower score.</li>
                <li><strong>Severity Burden (30%)</strong> &mdash; How severe are the most common adverse events? Weighted by clinical impact.</li>
                <li><strong>Chronic Use Safety (25%)</strong> &mdash; Is the drug safe for long-term use? Based on known toxicity profiles.</li>
                <li><strong>Drug-Induced Lupus Risk (10%)</strong> &mdash; Does the drug carry a risk of triggering drug-induced lupus?</li>
            </ul>
            <p style="margin-top:16px; color:#787890; font-size:0.82rem;">
                <strong>Disclaimer:</strong> All safety profiles are based on publicly available FDA label information and published literature.
                Individual patient risk-benefit assessment requires clinical judgment. Not medical advice.
            </p>
        </div>

        <footer>
            <p>Adverse Event Profiler &middot; Part of the Lupus Research Platform</p>
            <p><a href="../drug_repurposing/report.html">Drug Repurposing Report</a> &middot; <a href="../knowledge_graph/web/index.html">Knowledge Graph</a></p>
        </footer>
    </div>
</body>
</html>"""

    with open(output_path, "w", encoding="utf-8") as f:
        f.write(html)

    return str(output_path)


def escape_html(text: str) -> str:
    """Escape HTML special characters."""
    if not text:
        return ""
    return (
        text.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )
