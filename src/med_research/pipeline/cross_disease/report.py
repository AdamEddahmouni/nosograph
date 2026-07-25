"""
Cross-Disease Drug Repurposing Report Generator — Phase 22

Generates a standalone HTML report with:
  - Disease similarity matrix
  - Shared genes/drugs/pathways analysis
  - Multi-disease drug candidates table
  - Cross-disease repurposing recommendations
  - Interactive radar chart
"""

import json
from datetime import datetime
from pathlib import Path


def generate_html_report(results: dict) -> str:
    """Generate a standalone HTML report and return the path."""

    output_path = Path(__file__).parent / "report.html"

    d_summary = results["disease_summary"]
    disease_ids = sorted(d_summary.keys())
    n_diseases = results["total_diseases"]

    # Summary stats
    n_shared_genes = len(results["shared_genes"]["shared_genes"])
    n_shared_drugs = len(results["shared_drugs"]["shared_drugs"])
    n_shared_pathways = len(results["shared_pathways"]["shared_pathways"])
    mdd = results["multi_disease_drugs"]
    n_tier1 = sum(1 for d in mdd if d["composite_score"] >= 7.5)
    n_tier2 = sum(1 for d in mdd if 6.0 <= d["composite_score"] < 7.5)

    avg_score = sum(d["composite_score"] for d in mdd) / len(mdd) if mdd else 0

    # Top-5 JSON for radar chart
    top5 = mdd[:5]
    colors = ["#818cf8", "#4ade80", "#f59e0b", "#f472b6", "#34d399"]
    top5_json_data = []
    for i, d in enumerate(top5):
        name = d["drug_name"].split("(")[0].strip()[:30]
        top5_json_data.append({
            "name": name,
            "scores": [
                d["disease_coverage"],
                d["target_centrality"],
                d["pathway_breadth"],
                d["mechanistic_transferability"],
                d["novelty"],
            ],
        })
    top5_json = json.dumps(top5_json_data)

    # Build drug rows
    drug_rows_html = ""
    for i, d in enumerate(mdd[:25], 1):
        tier_color = {
            "Tier 1 — Strong Multi-Disease Candidate": "#dc2626",
            "Tier 2 — Promising Cross-Disease Candidate": "#ea580c",
            "Tier 3 — Moderate Cross-Disease Potential": "#ca8a04",
            "Tier 4 — Disease-Specific": "#16a34a",
        }.get(d["tier"], "#6b7280")

        score = d["composite_score"]
        score_color = (
            "#4ade80" if score >= 7.5 else "#fbbf24" if score >= 6.0 else "#f87171" if score < 4.5 else "#fb923c"
        )

        drug_rows_html += f"""
        <tr>
            <td class="rank">{i}</td>
            <td>
                <span class="tier-badge" style="background:{tier_color}20;color:{tier_color};border:1px solid {tier_color}40">
                    {d['tier'].split('—')[0].strip()}
                </span>
            </td>
            <td><strong>{escape_html(d['drug_name'])}</strong></td>
            <td>{d['disease_count']}</td>
            <td><span class="score" style="color:{score_color};font-weight:700;font-size:1.2em;">{score:.1f}</span></td>
            <td class="score-breakdown">
                <span title="Disease Coverage">🌐{d['disease_coverage']:.0f}</span>
                <span title="Target Centrality">🎯{d['target_centrality']:.0f}</span>
                <span title="Pathway Breadth">🛤️{d['pathway_breadth']:.0f}</span>
                <span title="Mechanistic Transferability">🔄{d['mechanistic_transferability']:.0f}</span>
                <span title="Novelty">💡{d['novelty']:.0f}</span>
            </td>
        </tr>"""

    # Build similarity rows
    sim_rows_html = ""
    for pair in results["disease_similarity"][:21]:
        sim_color = (
            "#4ade80" if pair["overall_similarity"] >= 0.3
            else "#fbbf24" if pair["overall_similarity"] >= 0.15
            else "#f87171"
        )
        sim_rows_html += f"""
        <tr>
            <td>{pair['name_a']}</td>
            <td>{pair['name_b']}</td>
            <td><span style="color:{sim_color};font-weight:700;">{pair['overall_similarity']:.3f}</span></td>
            <td>{pair['gene_similarity']:.3f}</td>
            <td>{pair['drug_similarity']:.3f}</td>
            <td>{pair['pathway_similarity']:.3f}</td>
            <td>{pair['shared_gene_count']}</td>
            <td>{pair['shared_drug_count']}</td>
        </tr>"""

    # Build shared gene rows
    sg_rows = ""
    for g in results["shared_genes"]["shared_genes"][:20]:
        sg_rows += f"""
        <tr>
            <td><strong>{escape_html(g['gene_id'])}</strong></td>
            <td class="muted">{escape_html(g['name'][:60])}</td>
            <td><span class="gene-tag">{g['disease_count']}</span></td>
            <td class="muted">{', '.join(g['diseases'])}</td>
        </tr>"""

    # Build shared drug rows
    sd_rows = ""
    for d in results["shared_drugs"]["shared_drugs"][:20]:
        sd_rows += f"""
        <tr>
            <td><strong>{escape_html(d['drug_id'])}</strong></td>
            <td class="muted">{escape_html(d['name'][:60])}</td>
            <td><span class="gene-tag">{d['disease_count']}</span></td>
            <td class="muted">{', '.join(d['diseases'])}</td>
        </tr>"""

    # Build repurposing rows
    rep_rows = ""
    novel_recs = [r for r in results["cross_disease_repurposing"] if not r["already_used_in_target"]][:15]
    for i, r in enumerate(novel_recs, 1):
        rep_rows += f"""
        <tr>
            <td class="rank">{i}</td>
            <td><strong>{escape_html(r['drug_name'][:50])}</strong></td>
            <td>{r['source_disease_name']} → {r['target_disease_name']}</td>
            <td><span class="gene-tag">{escape_html(r['drug_target'])}</span></td>
            <td><span class="gene-tag">{', '.join(r['matched_genes'])}</span></td>
            <td><span style="font-weight:700;color:#4ade80;">{r['confidence']:.0f}/10</span></td>
        </tr>"""

    # Disease summary cards
    disease_cards_html = ""
    emoji_map = {"sle": "🦋", "ra": "🦴", "ms": "🧠", "ss": "💧",
                 "ssc": "🖐️", "t1d": "🩸", "ibd": "🫃"}
    for did in disease_ids:
        info = d_summary[did]
        emoji = emoji_map.get(did, "🔬")
        disease_cards_html += f"""
        <div class="stat-card">
            <div style="font-size:1.5rem;margin-bottom:4px;">{emoji}</div>
            <div class="stat-value" style="font-size:1rem;color:#818cf8;">{info['name']}</div>
            <div class="stat-label">
                {info['gene_count']} genes · {info['drug_count']} drugs · {info['pathway_count']} pathways
            </div>
        </div>"""

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Cross-Disease Drug Repurposing Report</title>
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
            background: linear-gradient(135deg, #0f1729, #1a1025, #102920);
            border: 1px solid #252535;
            border-radius: 16px;
            padding: 40px;
            margin-bottom: 32px;
            text-align: center;
        }}
        .hero h1 {{
            font-size: 2.2rem; font-weight: 800;
            background: linear-gradient(135deg, #4ade80, #22d3ee, #818cf8, #c084fc);
            -webkit-background-clip: text; background-clip: text;
            -webkit-text-fill-color: transparent;
            margin-bottom: 8px;
        }}
        .hero .subtitle {{ color: #787890; font-size: 1rem; }}
        .hero .date {{ color: #787890; font-size: 0.8rem; margin-top: 8px; }}

        /* Stats grid */
        .stats-grid {{
            display: grid; grid-template-columns: repeat(auto-fit, minmax(170px, 1fr)); gap: 16px;
            margin-bottom: 32px;
        }}
        .stat-card {{
            background: #13131a; border: 1px solid #252535;
            border-radius: 12px; padding: 22px 18px; text-align: center;
        }}
        .stat-card .stat-value {{
            font-size: 1.9rem; font-weight: 800; margin-bottom: 4px;
        }}
        .stat-card .stat-label {{ color: #787890; font-size: 0.80rem; }}

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
        .muted {{ color: #787890; font-size: 0.78rem; }}
        .score-breakdown span {{
            display: inline-block; margin-right: 6px; font-size: 0.78rem;
            font-weight: 600; cursor: help;
        }}

        /* Footer */
        footer {{ text-align: center; padding: 40px; color: #787890; font-size: 0.78rem; }}
        footer a {{ color: #818cf8; }}

        /* Methodology */
        .method-card {{
            background: #13131a; border: 1px solid #252535; border-radius: 12px;
            padding: 24px; margin-bottom: 32px; max-width: 100%;
        }}
        .method-card ul {{ margin-left: 20px; color: #787890; font-size: 0.88rem; }}
        .method-card li {{ margin-bottom: 6px; }}

        @media (max-width: 768px) {{
            .stats-grid {{ grid-template-columns: repeat(2, 1fr); }}
            .hero {{ padding: 24px; }}
            .hero h1 {{ font-size: 1.4rem; }}
        }}
    </style>
</head>
<body>
    <div class="container">

        <!-- Hero -->
        <div class="hero">
            <h1>Cross-Disease Drug Repurposing Report</h1>
            <p class="subtitle">Multi-Disease Analysis of {n_diseases} Autoimmune Diseases — Identifying Shared Biology and Therapeutic Opportunities</p>
            <p class="date">Generated: {datetime.now().strftime('%B %d, %Y at %H:%M')} | {n_diseases} Diseases · {len(mdd)} Drugs Analyzed</p>
        </div>

        <!-- Disease Summary -->
        <h2 class="section-title">🩺 Disease Profiles</h2>
        <div class="stats-grid">
            {disease_cards_html}
        </div>

        <!-- Stats -->
        <h2 class="section-title">📊 Cross-Disease Summary</h2>
        <div class="stats-grid">
            <div class="stat-card">
                <div class="stat-value" style="color:#4ade80;">{n_shared_genes}</div>
                <div class="stat-label">Shared Genes (≥2 diseases)</div>
            </div>
            <div class="stat-card">
                <div class="stat-value" style="color:#818cf8;">{n_shared_drugs}</div>
                <div class="stat-label">Shared Drugs (≥2 diseases)</div>
            </div>
            <div class="stat-card">
                <div class="stat-value" style="color:#f59e0b;">{n_shared_pathways}</div>
                <div class="stat-label">Shared Pathways</div>
            </div>
            <div class="stat-card">
                <div class="stat-value" style="color:#f472b6;">{n_tier1}</div>
                <div class="stat-label">Tier 1 Multi-Disease Drugs</div>
            </div>
            <div class="stat-card">
                <div class="stat-value" style="color:#c084fc;">{n_tier2}</div>
                <div class="stat-label">Tier 2 Cross-Disease Drugs</div>
            </div>
            <div class="stat-card">
                <div class="stat-value" style="color:#22d3ee;">{avg_score:.1f}</div>
                <div class="stat-label">Avg Multi-Disease Score</div>
            </div>
        </div>

        <!-- Disease Similarity -->
        <h2 class="section-title">🔗 Disease Similarity Matrix</h2>
        <div class="table-container">
            <table>
                <thead>
                    <tr>
                        <th>Disease A</th>
                        <th>Disease B</th>
                        <th>Similarity</th>
                        <th>Gene Sim</th>
                        <th>Drug Sim</th>
                        <th>Pathway Sim</th>
                        <th>Shared Genes</th>
                        <th>Shared Drugs</th>
                    </tr>
                </thead>
                <tbody>
                    {sim_rows_html}
                </tbody>
            </table>
        </div>

        <!-- Radar Chart -->
        <h2 class="section-title">🎯 Score Dimension Radar — Top 5 Multi-Disease Drugs</h2>
        <div class="radar-container" style="max-width:700px;margin:0 auto 32px;">
            <canvas id="radarChart" style="max-height:500px;"></canvas>
        </div>

        <!-- Top Multi-Disease Drugs -->
        <h2 class="section-title">💊 Top Multi-Disease Drug Candidates</h2>
        <div class="table-container">
            <table>
                <thead>
                    <tr>
                        <th>#</th>
                        <th>Tier</th>
                        <th>Drug</th>
                        <th>Diseases</th>
                        <th>Score</th>
                        <th>Score Dimensions</th>
                    </tr>
                </thead>
                <tbody>
                    {drug_rows_html}
                </tbody>
            </table>
        </div>

        <!-- Shared Genes -->
        <h2 class="section-title">🧬 Shared Risk Genes (≥2 Diseases)</h2>
        <div class="table-container">
            <table>
                <thead>
                    <tr>
                        <th>Gene</th>
                        <th>Name</th>
                        <th>Diseases</th>
                        <th>Disease List</th>
                    </tr>
                </thead>
                <tbody>
                    {sg_rows}
                </tbody>
            </table>
        </div>

        <!-- Shared Drugs -->
        <h2 class="section-title">💊 Shared Approved & Investigational Drugs</h2>
        <div class="table-container">
            <table>
                <thead>
                    <tr>
                        <th>Drug ID</th>
                        <th>Name</th>
                        <th>Diseases</th>
                        <th>Disease List</th>
                    </tr>
                </thead>
                <tbody>
                    {sd_rows}
                </tbody>
            </table>
        </div>

        <!-- Repurposing Recommendations -->
        <h2 class="section-title">🔀 Cross-Disease Repurposing Opportunities</h2>
        <p style="color:#787890;margin-bottom:12px;font-size:0.88rem;">
            Drugs from one disease's knowledge graph that target risk genes in another disease — novel repurposing hypotheses.
        </p>
        <div class="table-container">
            <table>
                <thead>
                    <tr>
                        <th>#</th>
                        <th>Drug</th>
                        <th>Source → Target</th>
                        <th>Drug Target</th>
                        <th>Matched Genes</th>
                        <th>Confidence</th>
                    </tr>
                </thead>
                <tbody>
                    {rep_rows}
                </tbody>
            </table>
        </div>

        <!-- Methodology -->
        <h2 class="section-title">📐 Methodology</h2>
        <div class="method-card">
            <p style="color:#e0e0e8;font-weight:600;margin-bottom:12px;">Multi-Disease Drug Scoring (each 0–10, weighted):</p>
            <ul>
                <li><strong style="color:#e0e0e8;">Disease Coverage (30%)</strong> — Across how many of the {n_diseases} autoimmune diseases is this drug relevant? Higher = broader utility.</li>
                <li><strong style="color:#e0e0e8;">Target Centrality (25%)</strong> — Are the drug's molecular targets shared across multiple diseases? Reflects conserved disease biology.</li>
                <li><strong style="color:#e0e0e8;">Pathway Breadth (20%)</strong> — How many distinct biological pathways does this drug affect across diseases?</li>
                <li><strong style="color:#e0e0e8;">Mechanistic Transferability (15%)</strong> — How transferable is the drug's mechanism from one disease to others?</li>
                <li><strong style="color:#e0e0e8;">Novelty (10%)</strong> — How novel is this cross-disease application? Drugs used in few diseases get a bonus.</li>
            </ul>
            <p style="margin-top:16px;"><strong>Disease Similarity</strong> computed via Jaccard similarity on shared genes (40%), drugs (35%), and pathways (25%).</p>
            <p style="margin-top:16px;color:#787890;font-size:0.82rem;">
                <strong>Disclaimer:</strong> All analyses are computational predictions requiring experimental and clinical validation.
                This report is a research tool and does not constitute medical advice.
            </p>
        </div>

        <footer>
            <p>Cross-Disease Drug Repurposing Engine · Phase 22 · {n_diseases} Autoimmune Diseases Analyzed</p>
            <p><a href="../index.html">Platform Dashboard</a> · <a href="../knowledge_graph/web/index.html">Knowledge Graph</a></p>
        </footer>
    </div>
    <script>
(function() {{
    const top5 = {top5_json};
    const labels = ['Disease Coverage', 'Target Centrality', 'Pathway Breadth', 'Mechanistic Transferability', 'Novelty'];
    const colors = ['#818cf8', '#4ade80', '#f59e0b', '#f472b6', '#34d399'];
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
