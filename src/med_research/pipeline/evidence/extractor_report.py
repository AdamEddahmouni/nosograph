"""
HTML report generator for LLM Evidence Extractor results.
"""

from datetime import datetime
from pathlib import Path


def generate_html_report(results: dict) -> str:
    """Generate a standalone HTML report from LLM extraction results.

    Args:
        results: Output dict from extract_all().

    Returns:
        Path to the generated HTML file.
    """
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

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>LLM Evidence Extraction — {query[:50]}</title>
<style>
:root {{
    --bg: #0f172a;
    --bg-card: #1e293b;
    --bg-row: #162032;
    --text: #e2e8f0;
    --text-muted: #94a3b8;
    --accent: #8b5cf6;
    --accent2: #a78bfa;
    --border: #334155;
    --green: #4ade80;
    --yellow: #fbbf24;
    --red: #f87171;
    --blue: #818cf8;
}}
*, *::before, *::after {{ box-sizing: border-box; margin: 0; padding: 0; }}
body {{
    font-family: 'Segoe UI', system-ui, -apple-system, sans-serif;
    background: var(--bg);
    color: var(--text);
    line-height: 1.6;
    min-height: 100vh;
}}
.container {{ max-width: 1400px; margin: 0 auto; padding: 24px 32px; }}

/* ── Hero ──────────────────────────────── */
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
    margin-bottom: 8px;
}}
.hero .subtitle {{ color: var(--text-muted); font-size: 1.05rem; }}
.hero .date {{ color: var(--text-muted); font-size: 0.82rem; margin-top: 6px; }}

/* ── Stats Grid ────────────────────────── */
.stats-grid {{
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(170px, 1fr));
    gap: 16px;
    margin-bottom: 40px;
}}
.stat-card {{
    background: var(--bg-card);
    border: 1px solid var(--border);
    border-radius: 12px;
    padding: 20px 16px;
    text-align: center;
    transition: transform 0.15s, box-shadow 0.15s;
}}
.stat-card:hover {{ transform: translateY(-2px); box-shadow: 0 4px 20px rgba(139, 92, 246, 0.15); }}
.stat-value {{ font-size: 2rem; font-weight: 700; }}
.stat-label {{ color: var(--text-muted); font-size: 0.8rem; margin-top: 4px; text-transform: uppercase; letter-spacing: 0.5px; }}

/* ── Charts Section ─────────────────────── */
.charts-section {{
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(400px, 1fr));
    gap: 24px;
    margin-bottom: 40px;
}}
.chart-card {{
    background: var(--bg-card);
    border: 1px solid var(--border);
    border-radius: 12px;
    padding: 24px;
}}
.chart-card h3 {{
    font-size: 1.1rem;
    margin-bottom: 16px;
    color: var(--accent2);
}}
.chart-bar-row {{
    display: flex;
    align-items: center;
    margin-bottom: 10px;
    gap: 10px;
}}
.chart-bar-label {{
    width: 140px;
    font-size: 0.78rem;
    color: var(--text-muted);
    text-align: right;
    flex-shrink: 0;
}}
.chart-bar-track {{
    flex: 1;
    height: 22px;
    background: var(--bg);
    border-radius: 4px;
    overflow: hidden;
}}
.chart-bar-fill {{
    height: 100%;
    border-radius: 4px;
    transition: width 0.3s;
}}
.chart-bar-value {{
    width: 36px;
    font-size: 0.78rem;
    font-weight: 600;
    text-align: left;
    flex-shrink: 0;
}}

/* ── Table ──────────────────────────────── */
.section-title {{
    font-size: 1.3rem;
    margin-bottom: 16px;
    color: var(--accent2);
    border-bottom: 1px solid var(--border);
    padding-bottom: 8px;
}}
.table-wrapper {{
    overflow-x: auto;
    border-radius: 12px;
    border: 1px solid var(--border);
    margin-bottom: 40px;
}}
table {{
    width: 100%;
    border-collapse: collapse;
    font-size: 0.85rem;
}}
thead {{ background: var(--bg-card); }}
th {{
    padding: 12px 10px;
    text-align: left;
    font-weight: 600;
    color: var(--text-muted);
    font-size: 0.75rem;
    text-transform: uppercase;
    letter-spacing: 0.5px;
    border-bottom: 1px solid var(--border);
    white-space: nowrap;
}}
td {{ padding: 10px; border-bottom: 1px solid rgba(51, 65, 85, 0.4); vertical-align: top; }}
tr:hover {{ background: rgba(139, 92, 246, 0.05); }}

.col-rank {{ width: 40px; color: var(--text-muted); text-align: center; }}
.col-title {{ min-width: 220px; }}
.ext-title {{ font-weight: 500; margin-bottom: 2px; }}
.ext-meta {{ font-size: 0.7rem; color: var(--text-muted); }}
.col-level {{ width: 120px; }}
.col-system {{ width: 90px; }}
.col-drugs {{ width: 120px; font-size: 0.78rem; }}
.col-findings {{ min-width: 180px; font-size: 0.82rem; color: var(--text-muted); }}
.col-confidence {{ width: 60px; text-align: center; font-weight: 600; }}
.col-relevance {{ width: 80px; text-align: center; font-size: 0.78rem; }}

/* ── Badges ─────────────────────────────── */
.badge {{
    display: inline-block;
    padding: 3px 10px;
    border-radius: 20px;
    font-size: 0.72rem;
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 0.3px;
}}
.badge-meta-analysis {{ background: rgba(139, 92, 246, 0.2); color: #a78bfa; }}
.badge-systematic-review {{ background: rgba(139, 92, 246, 0.15); color: #c4b5fd; }}
.badge-rct {{ background: rgba(74, 222, 128, 0.15); color: #4ade80; }}
.badge-observational-cohort {{ background: rgba(251, 191, 36, 0.15); color: #fbbf24; }}
.badge-observational-case-control {{ background: rgba(251, 191, 36, 0.1); color: #fcd34d; }}
.badge-case-series {{ background: rgba(248, 113, 113, 0.15); color: #f87171; }}
.badge-case-report {{ background: rgba(248, 113, 113, 0.1); color: #fca5a5; }}
.badge-preclinical {{ background: rgba(129, 140, 248, 0.15); color: #818cf8; }}
.badge-review {{ background: rgba(148, 163, 184, 0.15); color: #94a3b8; }}
.badge-unknown {{ background: rgba(148, 163, 184, 0.1); color: #64748b; }}

/* ── Mini bar ───────────────────────────── */
.mini-bar {{ width: 100%; height: 4px; background: var(--border); border-radius: 2px; margin-bottom: 3px; }}
.mini-bar-fill {{ height: 100%; border-radius: 2px; }}

/* ── Study Design / Drugs ───────────────── */
.info-grid {{
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(300px, 1fr));
    gap: 24px;
    margin-bottom: 40px;
}}
.info-card {{
    background: var(--bg-card);
    border: 1px solid var(--border);
    border-radius: 12px;
    padding: 20px;
}}
.info-card h3 {{
    font-size: 1rem;
    margin-bottom: 12px;
    color: var(--accent2);
}}
.stat-row {{
    display: flex;
    justify-content: space-between;
    padding: 6px 0;
    border-bottom: 1px solid rgba(51, 65, 85, 0.3);
    font-size: 0.82rem;
}}
.stat-key {{ color: var(--text-muted); }}
.stat-val {{ font-weight: 600; }}

.drug-list {{ display: flex; flex-wrap: wrap; gap: 8px; margin-top: 8px; }}
.drug-tag {{
    background: rgba(139, 92, 246, 0.15);
    color: var(--accent2);
    padding: 4px 12px;
    border-radius: 20px;
    font-size: 0.78rem;
    font-weight: 500;
}}

/* ── Footer ─────────────────────────────── */
.footer {{
    text-align: center;
    padding: 24px 0;
    color: var(--text-muted);
    font-size: 0.78rem;
    border-top: 1px solid var(--border);
}}
</style>
</head>
<body>
<div class="container">
    <div class="hero">
        <h1>🤖 LLM Evidence Extraction</h1>
        <p class="subtitle">Structured Data Extraction · Evidence Levels · Drug Mentions · Key Findings</p>
        <p class="date">Generated: {gen_time}</p>
    </div>

    <div class="stats-grid">
        <div class="stat-card">
            <div class="stat-value" style="color:var(--accent2);">{total}</div>
            <div class="stat-label">Articles Extracted</div>
        </div>
        <div class="stat-card">
            <div class="stat-value" style="color:var(--green);">{successful}</div>
            <div class="stat-label">Successful LLM Extractions</div>
        </div>
        <div class="stat-card">
            <div class="stat-value" style="color:var(--blue);">{model}</div>
            <div class="stat-label">LLM Model</div>
        </div>
        <div class="stat-card">
            <div class="stat-value" style="color:var(--yellow);">{elapsed}s</div>
            <div class="stat-label">Extraction Time</div>
        </div>
        <div class="stat-card">
            <div class="stat-value" style="color:#c084fc;">{stats.get("avg_confidence", 0):.0f}%</div>
            <div class="stat-label">Avg Confidence</div>
        </div>
        <div class="stat-card">
            <div class="stat-value" style="color:#34d399;">{stats.get("n_unique_drugs", 0)}</div>
            <div class="stat-label">Unique Drugs Found</div>
        </div>
    </div>

    <div class="charts-section">
        <div class="chart-card">
            <h3>📊 Evidence Level Distribution</h3>
            {''.join(
                f'<div class="chart-bar-row"><span class="chart-bar-label">{label}</span><div class="chart-bar-track"><div class="chart-bar-fill" style="width:{v/max(ev_values)*100 if ev_values else 0}%;background:{["#a78bfa","#c4b5fd","#4ade80","#fbbf24","#fcd34d","#f87171","#fca5a5","#818cf8","#94a3b8"][i%9] if i < 9 else "#94a3b8"};"></div></div><span class="chart-bar-value">{v}</span></div>'
                for i, (label, v) in enumerate(zip(ev_labels, ev_values, strict=True))
            ) if ev_labels else '<p style="color:var(--text-muted);">No data</p>'}
        </div>
        <div class="chart-card">
            <h3>🧬 Model System Distribution</h3>
            {''.join(
                f'<div class="chart-bar-row"><span class="chart-bar-label">{label}</span><div class="chart-bar-track"><div class="chart-bar-fill" style="width:{v/max(ms_values)*100 if ms_values else 0}%;background:{["#818cf8","#4ade80","#fbbf24","#f87171","#c084fc","#fb923c","#34d399"][i%7] if i < 7 else "#94a3b8"};"></div></div><span class="chart-bar-value">{v}</span></div>'
                for i, (label, v) in enumerate(zip(ms_labels, ms_values, strict=True))
            ) if ms_labels else '<p style="color:var(--text-muted);">No data</p>'}
        </div>
    </div>

    <div class="info-grid">
        <div class="info-card">
            <h3>📋 Study Designs</h3>
            {sd_html or '<p style="color:var(--text-muted);">No data</p>'}
        </div>
        <div class="info-card">
            <h3>💊 Drugs Mentioned ({stats.get("n_unique_drugs", 0)})</h3>
            {drugs_html or '<p style="color:var(--text-muted);">No drug mentions found</p>'}
        </div>
    </div>

    <h2 class="section-title">🔬 Detailed Extractions</h2>
    <div class="table-wrapper">
        <table>
            <thead>
                <tr>
                    <th>#</th>
                    <th>Title / Source</th>
                    <th>Evidence Level</th>
                    <th>Model System</th>
                    <th>Drugs</th>
                    <th>Key Findings</th>
                    <th>Conf</th>
                    <th>Relevance</th>
                </tr>
            </thead>
            <tbody>
                {rows_html}
            </tbody>
        </table>
    </div>

    <div class="footer">
        Lupus Research Platform · LLM Evidence Extractor · Query: "{query}"
    </div>
</div>
</body>
</html>"""

    out_path = Path(__file__).parent / "report.html"
    out_path.write_text(html, encoding="utf-8")
    return str(out_path)
