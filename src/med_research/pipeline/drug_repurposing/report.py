"""
Lupus Drug Repurposing Report Generator

Generates a beautiful standalone HTML report with:
  - Executive summary and statistics
  - Priority-ranked repurposing candidates table
  - Per-gene analysis cards
  - Clinical trial status indicators
  - Interactive score breakdowns
"""

from datetime import datetime
from pathlib import Path


def generate_html_report(
    scored_candidates: list, untargeted_genes: list, genes: dict, G
) -> str:
    """Generate a standalone HTML report and return the path."""

    output_path = Path(__file__).parent / "report.html"

    # Build gene->candidates mapping
    gene_candidates = {}
    for c in scored_candidates:
        gene_candidates.setdefault(c["gene_id"], []).append(c)

    # Sort genes by best candidate score
    gene_rankings = []
    for gene in untargeted_genes:
        gid = gene["id"]
        cands = gene_candidates.get(gid, [])
        best = max(c["composite_score"] for c in cands) if cands else 0
        gene_rankings.append({"gene": gene, "candidates": cands, "best_score": best, "count": len(cands)})
    gene_rankings.sort(key=lambda x: x["best_score"], reverse=True)

    # Build top-5 JSON for radar chart
    import json
    top5_items = []
    for c in scored_candidates[:5]:
        name = c['drug_name'].split('(')[0].strip()[:25]
        top5_items.append({
            "name": name,
            "scores": [
                c.get('target_similarity_score', 5),
                c.get('final_proximity', 5),
                c.get('mechanistic_rationale_score', 5),
                c.get('clinical_evidence_score', 5),
                c.get('adverse_event_score', c.get('safety_score', 5)),
                c.get('novelty_score', 5) * 2,  # Scale 0-5 to 0-10 for chart
            ],
        })
    top5_json = json.dumps(top5_items)

    # Build candidate rows
    rows_html = ""
    for i, c in enumerate(scored_candidates[:25], 1):
        tier_color = {
            "🔴 Tier 1 — Highest Priority": "#dc2626",
            "🟠 Tier 2 — High Priority": "#ea580c",
            "🟡 Tier 3 — Medium Priority": "#ca8a04",
            "🟢 Tier 4 — Lower Priority": "#16a34a",
        }.get(c["tier"], "#6b7280")

        score = c["composite_score"]
        score_color = (
            "#4ade80" if score >= 8 else "#fbbf24" if score >= 7 else "#f87171" if score < 6 else "#fb923c"
        )

        rows_html += f"""
        <tr>
            <td class="rank">{i}</td>
            <td>
                <span class="tier-badge" style="background:{tier_color}20;color:{tier_color};border:1px solid {tier_color}40">
                    {c['tier'].split('—')[0].strip()}
                </span>
            </td>
            <td><strong>{escape_html(c['drug_name'])}</strong><br><span class="muted">{c['drug_category']}</span></td>
            <td><span class="gene-tag">{c['gene_name']}</span><br><span class="muted">{c['gene_category']}</span></td>
            <td><span class="score" style="color:{score_color};font-weight:700;font-size:1.2em;">{score:.1f}</span></td>
            <td class="score-breakdown">
                <span title="Target Similarity">🎯{c['target_similarity_score']}</span>
                <span title="Pathway Proximity">🛤️{c['final_proximity']:.0f}</span>
                <span title="Mechanistic Rationale">🧬{c['mechanistic_rationale_score']}</span>
                <span title="Clinical Evidence">📋{c['clinical_evidence_score']}</span>
                <span title="Adverse Event Profile">🛡️{c.get('adverse_event_score', c.get('safety_score', 'N/A'))}</span>
            </td>
            <td>{c['evidence_level']}</td>
            <td><span class="status-tag">{c['status']}</span></td>
        </tr>"""

    # Build gene cards
    gene_cards_html = ""

    for gr in gene_rankings:
        gene = gr["gene"]
        cands = gr["candidates"]
        gid = gene["id"]

        cand_html = ""
        for c in cands:
            cand_html += f"""
            <div class="gene-candidate">
                <div class="gc-header">
                    <span class="gc-drug">{escape_html(c['drug_name'])}</span>
                    <span class="gc-score" style="color: {'#4ade80' if c['composite_score'] >= 8 else '#fbbf24' if c['composite_score'] >= 7 else '#f87171'}">{c['composite_score']:.1f}</span>
                </div>
                <div class="gc-mechanism">{escape_html(c['mechanism'][:200])}</div>
                <div class="gc-rationale">{escape_html(c['rationale'][:250])}</div>
                <div class="gc-meta">
                    <span>📋 {c['evidence_level']}</span>
                    <span>🚦 {c['status']}</span>
                </div>
            </div>"""

        gene_cards_html += f"""
        <div class="gene-card" id="gene-{gid}">
            <div class="gene-card-header">
                <div>
                    <h3>{escape_html(gene['name'])} <code>{gid}</code></h3>
                    <span class="gene-category">{escape_html(gene.get('category', ''))}</span>
                </div>
                <div class="gene-card-score">
                    <span class="best-label">Best</span>
                    <span class="best-value">{gr['best_score']:.1f}</span>
                </div>
            </div>
            <div class="gene-card-body">
                <p class="gene-function"><strong>Function:</strong> {escape_html(gene.get('function', ''))}</p>
                <p class="gene-evidence"><strong>Lupus Evidence:</strong> {escape_html(gene.get('lupus_evidence', ''))}</p>
                <p class="gene-odds"><strong>Odds Ratio:</strong> {gene.get('odds_ratio', 'N/A')} | <strong>Chr:</strong> {gene.get('chromosome', 'N/A')}</p>
            </div>
            <div class="gene-card-candidates">
                <h4>{len(cands)} Repurposing Candidate{'s' if len(cands) != 1 else ''}</h4>
                {cand_html}
            </div>
        </div>"""

    # Summary stats
    n_tier1 = sum(1 for c in scored_candidates if c["composite_score"] >= 8.0)
    n_tier2 = sum(1 for c in scored_candidates if 7.0 <= c["composite_score"] < 8.0)
    avg_score = sum(c["composite_score"] for c in scored_candidates) / len(scored_candidates) if scored_candidates else 0

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Lupus Drug Repurposing Report</title>
    <link rel="preconnect" href="https://fonts.googleapis.com">
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap" rel="stylesheet">
    <script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.7/dist/chart.umd.min.js"></script>
    <style>
        * {{ margin: 0; padding: 0; box-sizing: border-box; }}
        body {{
            font-family: 'Inter', system-ui, -apple-system, sans-serif;
            background: #0a0a0f; color: #e0e0e8; line-height: 1.6;
        }}
        .container {{ max-width: 1200px; margin: 0 auto; padding: 20px; }}

        /* Hero */
        .hero {{
            background: linear-gradient(135deg, #1a1025, #0f1729, #1a1025);
            border: 1px solid #252535;
            border-radius: 16px;
            padding: 40px;
            margin-bottom: 32px;
            text-align: center;
        }}
        .hero h1 {{
            font-size: 2.2rem; font-weight: 800;
            background: linear-gradient(135deg, #818cf8, #c084fc, #f472b6);
            -webkit-background-clip: text; background-clip: text;
            -webkit-text-fill-color: transparent;
            margin-bottom: 8px;
        }}
        .hero .subtitle {{ color: #787890; font-size: 1rem; }}
        .hero .date {{ color: #787890; font-size: 0.8rem; margin-top: 8px; }}

        /* Stats grid */
        .stats-grid {{
            display: grid; grid-template-columns: repeat(4, 1fr); gap: 16px;
            margin-bottom: 32px;
        }}
        .stat-card {{
            background: #13131a; border: 1px solid #252535;
            border-radius: 12px; padding: 24px; text-align: center;
        }}
        .stat-card .stat-value {{
            font-size: 2rem; font-weight: 800; margin-bottom: 4px;
        }}
        .stat-card .stat-label {{ color: #787890; font-size: 0.82rem; }}

        /* Tables */
        .section-title {{
            font-size: 1.3rem; font-weight: 700; margin: 32px 0 16px;
            padding-bottom: 8px; border-bottom: 1px solid #252535;
        }}
        .table-container {{
            overflow-x: auto; background: #13131a;
            border: 1px solid #252535; border-radius: 12px;
            margin-bottom: 32px;
        }}
        table {{ width: 100%; border-collapse: collapse; font-size: 0.88rem; }}
        th {{
            text-align: left; padding: 14px 16px; background: #1a1a24;
            color: #787890; font-weight: 600; font-size: 0.75rem;
            text-transform: uppercase; letter-spacing: 0.05em;
            border-bottom: 1px solid #252535;
        }}
        td {{ padding: 12px 16px; border-bottom: 1px solid #1a1a24; vertical-align: top; }}
        tr:hover td {{ background: rgba(129, 140, 248, 0.03); }}
        .rank {{ font-weight: 700; color: #787890; font-size: 1.1rem; min-width: 30px; }}

        /* Badges & tags */
        .tier-badge {{
            display: inline-block; padding: 3px 10px; border-radius: 20px;
            font-size: 0.7rem; font-weight: 600; white-space: nowrap;
        }}
        .gene-tag {{ color: #4ade80; font-weight: 600; }}
        .status-tag {{
            display: inline-block; padding: 2px 8px; border-radius: 12px;
            font-size: 0.7rem; font-weight: 500; background: rgba(129,140,248,0.1);
            color: #a5b4fc;
        }}
        .muted {{ color: #787890; font-size: 0.78rem; }}
        .score-breakdown span {{
            display: inline-block; margin-right: 6px; font-size: 0.78rem;
            font-weight: 600; cursor: help;
        }}

        /* Gene cards */
        .gene-cards {{ display: grid; grid-template-columns: repeat(auto-fill, minmax(380px, 1fr)); gap: 20px; margin-bottom: 32px; }}
        .gene-card {{
            background: #13131a; border: 1px solid #252535; border-radius: 12px;
            overflow: hidden; transition: border-color 0.2s;
        }}
        .gene-card:hover {{ border-color: #4b5563; }}
        .gene-card-header {{
            display: flex; justify-content: space-between; align-items: flex-start;
            padding: 20px; background: #1a1a24; border-bottom: 1px solid #252535;
        }}
        .gene-card-header h3 {{ font-size: 1rem; margin-bottom: 4px; }}
        .gene-card-header code {{ color: #818cf8; font-size: 0.75rem; margin-left: 6px; }}
        .gene-category {{ font-size: 0.75rem; color: #787890; }}
        .gene-card-score {{ text-align: center; }}
        .best-label {{ display: block; font-size: 0.65rem; color: #787890; text-transform: uppercase; }}
        .best-value {{ font-size: 1.5rem; font-weight: 800; color: #fbbf24; }}
        .gene-card-body {{ padding: 16px 20px; font-size: 0.82rem; }}
        .gene-card-body p {{ margin-bottom: 8px; }}
        .gene-function {{ color: #a5b4fc; }}
        .gene-evidence {{ color: #c084fc; }}
        .gene-odds {{ color: #787890; font-size: 0.78rem; }}
        .gene-card-candidates {{ padding: 0 20px 20px; }}
        .gene-card-candidates h4 {{ font-size: 0.78rem; color: #787890; text-transform: uppercase; margin-bottom: 10px; letter-spacing: 0.05em; }}
        .gene-candidate {{
            background: #0a0a0f; border: 1px solid #1a1a24;
            border-radius: 8px; padding: 12px; margin-bottom: 8px;
        }}
        .gc-header {{ display: flex; justify-content: space-between; margin-bottom: 6px; }}
        .gc-drug {{ font-weight: 600; font-size: 0.85rem; }}
        .gc-score {{ font-weight: 700; font-size: 0.9rem; }}
        .gc-mechanism {{ font-size: 0.78rem; color: #a5b4fc; margin-bottom: 4px; }}
        .gc-rationale {{ font-size: 0.76rem; color: #787890; margin-bottom: 6px; }}
        .gc-meta {{ font-size: 0.72rem; color: #6b7280; display: flex; gap: 16px; }}

        /* Footer */
        footer {{ text-align: center; padding: 40px; color: #787890; font-size: 0.78rem; }}
        footer a {{ color: #818cf8; }}

        @media (max-width: 768px) {{
            .stats-grid {{ grid-template-columns: repeat(2, 1fr); }}
            .gene-cards {{ grid-template-columns: 1fr; }}
            .hero {{ padding: 24px; }}
            .hero h1 {{ font-size: 1.4rem; }}
        }}
    </style>
</head>
<body>
    <div class="container">

        <!-- Hero -->
        <div class="hero">
            <h1>🧬 Lupus Drug Repurposing Report</h1>
            <p class="subtitle">AI-Driven Analysis of {len(scored_candidates)} Repurposing Candidates Across {len(untargeted_genes)} Untargeted Lupus Genes</p>
            <p class="date">Generated: {datetime.now().strftime('%B %d, %Y at %H:%M')} | Knowledge Graph: {G.number_of_nodes()} nodes · {G.number_of_edges()} edges</p>
        </div>

        <!-- Stats -->
        <div class="stats-grid">
            <div class="stat-card">
                <div class="stat-value" style="color:#4ade80;">{n_tier1}</div>
                <div class="stat-label">Tier 1 Candidates (≥8.0)</div>
            </div>
            <div class="stat-card">
                <div class="stat-value" style="color:#fbbf24;">{n_tier2}</div>
                <div class="stat-label">Tier 2 Candidates (7.0–7.9)</div>
            </div>
            <div class="stat-card">
                <div class="stat-value" style="color:#818cf8;">{avg_score:.1f}</div>
                <div class="stat-label">Average Composite Score</div>
            </div>
            <div class="stat-card">
                <div class="stat-value" style="color:#c084fc;">{len(untargeted_genes)}</div>
                <div class="stat-label">Untargeted Lupus Genes</div>
            </div>
        </div>

        <!-- Radar Chart -->
        <h2 class="section-title">🎯 Score Dimension Radar — Top 5 Candidates</h2>
        <div class="radar-container" style="max-width:700px;margin:0 auto 32px;">
            <canvas id="radarChart" style="max-height:500px;"></canvas>
        </div>

        <!-- Top Candidates Table -->
        <h2 class="section-title">🏆 Top Repurposing Candidates</h2>
        <div class="table-container">
            <table>
                <thead>
                    <tr>
                        <th>#</th>
                        <th>Tier</th>
                        <th>Drug</th>
                        <th>Target Gene</th>
                        <th>Score</th>
                        <th>Dimensions</th>
                        <th>Evidence</th>
                        <th>Status</th>
                    </tr>
                </thead>
                <tbody>
                    {rows_html}
                </tbody>
            </table>
        </div>

        <!-- Gene Cards -->
        <h2 class="section-title">🧬 Per-Gene Analysis</h2>
        <div class="gene-cards">
            {gene_cards_html}
        </div>

        <!-- Methodology -->
        <h2 class="section-title">📐 Methodology</h2>
        <div class="gene-card" style="max-width:100%;">
            <div class="gene-card-body">
                <p><strong>Scoring Dimensions (each 0-10, weighted):</strong></p>
                <ul style="margin-left:20px; color:#787890; font-size:0.88rem;">
                    <li><strong style="color:#e0e0e8;">Target Similarity (25%)</strong> — How closely related is the drug's known target to the gene?</li>
                    <li><strong style="color:#e0e0e8;">Pathway Proximity (15%)</strong> — Network distance in the lupus knowledge graph.</li>
                    <li><strong style="color:#e0e0e8;">Mechanistic Rationale (25%)</strong> — Does the drug's mechanism make biological sense?</li>
                    <li><strong style="color:#e0e0e8;">Clinical Evidence (20%)</strong> — Published literature, trial data, and case series support.</li>
                    <li><strong style="color:#e0e0e8;">Safety Profile (10%)</strong> — Known safety from approved indications.</li>
                    <li><strong style="color:#e0e0e8;">Novelty Bonus (5%)</strong> — How novel is this repurposing application?</li>
                </ul>
                <p style="margin-top:16px; color:#787890; font-size:0.82rem;">
                    <strong>Disclaimer:</strong> All candidates are computational predictions requiring experimental and clinical validation.
                    This report is a research tool and does not constitute medical advice.
                </p>
            </div>
        </div>

        <footer>
            <p>Lupus Drug Repurposing Engine · Generated by AI analysis of untargeted genes from the Lupus Knowledge Graph</p>
            <p><a href="../knowledge_graph/web/index.html">View Knowledge Graph</a></p>
        </footer>
    </div>
    <script>
(function() {{
    const top5 = {top5_json};
    const labels = ['Target Similarity', 'Pathway Proximity', 'Mechanistic Rationale', 'Clinical Evidence', 'Adverse Event Profile', 'Novelty'];
    const colors = ['#818cf8', '#4ade80', '#f59e0b', '#f472b6', '#34d399', '#c084fc'];
    const datasets = top5.map((c, i) => ({{
        label: c.name,
        data: c.scores,
        borderColor: colors[i],
        backgroundColor: colors[i] + '18',
        borderWidth: 2,
        pointBackgroundColor: colors[i],
        pointRadius: 4,
    }}));
    new Chart(document.getElementById('radarChart'), {{
        type: 'radar',
        data: {{ labels, datasets }},
        options: {{
            responsive: true,
            maintainAspectRatio: true,
            scales: {{ r: {{ beginAtZero: true, max: 10, ticks: {{ backdropColor: 'transparent', color: '#787890', font: {{ size: 10 }} }}, grid: {{ color: '#252535' }}, pointLabels: {{ color: '#c0c0d0', font: {{ size: 11 }} }}, angleLines: {{ color: '#252535' }} }} }},
            plugins: {{ legend: {{ position: 'bottom', labels: {{ color: '#c0c0d0', font: {{ size: 12 }}, padding: 16, usePointStyle: true }} }} }}
        }}
    }});
}})();
</script>
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
