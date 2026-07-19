"""
Lupus Virtual Screening Report Generator

Generates a standalone HTML report showing:
  - Screening overview and statistics
  - Per-target top compound rankings
  - Score breakdown with visual bars
  - Optional AutoDock Vina docking results
  - Methodology section
"""

from datetime import datetime
from pathlib import Path


def generate_screening_report(results: dict) -> str:
    """Generate an HTML report from virtual screening results."""

    output_path = Path(__file__).parent / "screening_report.html"
    stats = results["stats"]
    gene_names = {}
    for gene_id, target_data in results.get("results_per_target", {}).items():
        gene_names[gene_id] = target_data["gene_info"].get("name", gene_id)

    # ── Target sections ─────────────────────────────────────────────────

    target_sections = ""
    for gene_id, target_data in sorted(results.get("results_per_target", {}).items()):
        gene_info = target_data["gene_info"]
        top = target_data["top_compounds"]

        compound_rows = ""
        for i, c in enumerate(top, 1):
            score = c["composite_score"]
            score_color = (
                "#4ade80" if score >= 7.5 else
                "#fbbf24" if score >= 6.5 else
                "#f87171" if score < 5.0 else
                "#fb923c"
            )

            tier_icon = c["tier"].split(" ")[0] if c["tier"] else ""

            # Score bars
            dims = [
                ("Binding", c.get("binding_estimate", 0), "#818cf8"),
                ("Drug-Like", c.get("druglikeness", 0), "#4ade80"),
                ("Target", c.get("target_complementarity", 0), "#f59e0b"),
                ("Similarity", c.get("similarity_score", 0), "#c084fc"),
                ("Novelty", c.get("novelty_score", 0), "#34d399"),
            ]
            bars_html = "".join(
                f'<div class="dim-bar"><span class="dim-label">{label}</span>'
                f'<div class="dim-fill-wrap"><div class="dim-fill" style="width:{val*10}%;background:{color}"></div></div>'
                f'<span class="dim-val">{val:.1f}</span></div>'
                for label, val, color in dims
            )

            compound_rows += f"""
            <tr>
                <td class="rank">{i}</td>
                <td>
                    <strong>{escape_html(c['name'][:45])}</strong>
                    <br><span class="muted">{c.get('type', '')} · {c.get('category', '')[:35]}</span>
                </td>
                <td>
                    <span class="score-badge" style="background:{score_color}20;color:{score_color};border:1px solid {score_color}40">
                        {tier_icon} {score:.1f}
                    </span>
                </td>
                <td class="dims-cell">{bars_html}</td>
            </tr>"""

        vina_section = ""
        vina = target_data.get("vina_results", {})
        if vina:
            vina_rows = ""
            for cid, vina_data in vina.items():
                best = vina_data.get("best_score")
                modes = vina_data.get("modes_found", 0)
                vina_rows += (
                    f'<div class="vina-chip">'
                    f'<strong>{cid}</strong>: {best:.1f} kcal/mol ({modes} modes)'
                    f'</div>'
                )
            vina_section = f"""
            <div class="vina-box">
                <h4>🧬 AutoDock Vina Docking Results</h4>
                <div class="vina-chips">{vina_rows}</div>
            </div>"""

        target_sections += f"""
        <div class="target-section" id="target-{gene_id}">
            <div class="target-header">
                <div>
                    <h3>{escape_html(gene_info.get('name', gene_id))} <code>{gene_id}</code></h3>
                    <span class="target-category">{escape_html(gene_info.get('category', ''))}</span>
                    <span class="target-mean">Mean score: {target_data['mean_score']}</span>
                </div>
                <div class="target-count">{target_data['total_screened']} compounds screened</div>
            </div>
            <div class="table-container">
                <table>
                    <thead>
                        <tr>
                            <th>#</th>
                            <th>Compound</th>
                            <th>Score</th>
                            <th>Dimension Breakdown</th>
                        </tr>
                    </thead>
                    <tbody>{compound_rows}</tbody>
                </table>
            </div>
            {vina_section}
        </div>"""

    # ── Top overall hits ────────────────────────────────────────────────

    top_overall_rows = ""
    for i, c in enumerate(results.get("all_results", [])[:20], 1):
        score = c["composite_score"]
        score_color = (
            "#4ade80" if score >= 7.5 else "#fbbf24" if score >= 6.5 else "#f87171"
        )
        top_overall_rows += f"""
        <tr>
            <td class="rank">{i}</td>
            <td><strong>{escape_html(c['name'][:45])}</strong></td>
            <td><span class="gene-tag">{c.get('gene_name', '')[:25]}</span></td>
            <td><span style="color:{score_color};font-weight:700;font-size:1.1em">{score:.1f}</span></td>
            <td><span class="tier-tag">{c.get('tier', '').split('—')[0].strip()}</span></td>
        </tr>"""

    # ── Assemble HTML ───────────────────────────────────────────────────

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Lupus Virtual Drug Screening Report</title>
    <style>
        * {{ margin: 0; padding: 0; box-sizing: border-box; }}
        body {{
            font-family: 'Inter', system-ui, -apple-system, sans-serif;
            background: #0a0a0f; color: #e0e0e8; line-height: 1.6;
        }}
        .container {{ max-width: 1200px; margin: 0 auto; padding: 24px; }}

        .hero {{
            background: linear-gradient(135deg, #0f1729, #1a1025, #0f1729);
            border: 1px solid #252535; border-radius: 16px;
            padding: 40px; margin-bottom: 32px; text-align: center;
        }}
        .hero h1 {{
            font-size: 2rem; font-weight: 800;
            background: linear-gradient(135deg, #818cf8, #34d399, #f472b6);
            -webkit-background-clip: text; background-clip: text;
            -webkit-text-fill-color: transparent; margin-bottom: 8px;
        }}
        .hero .subtitle {{ color: #787890; font-size: 0.95rem; }}

        .stats-grid {{
            display: grid; grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
            gap: 14px; margin-bottom: 32px;
        }}
        .stat-card {{
            background: #13131a; border: 1px solid #252535;
            border-radius: 12px; padding: 20px; text-align: center;
        }}
        .stat-card .stat-value {{ font-size: 1.8rem; font-weight: 800; }}
        .stat-card .stat-label {{ color: #787890; font-size: 0.78rem; margin-top: 4px; }}

        .section-title {{
            font-size: 1.2rem; font-weight: 700; margin: 32px 0 14px;
            padding-bottom: 8px; border-bottom: 1px solid #252535;
        }}

        /* Table */
        .table-container {{
            overflow-x: auto; background: #13131a;
            border: 1px solid #252535; border-radius: 12px; margin-bottom: 28px;
        }}
        table {{ width: 100%; border-collapse: collapse; font-size: 0.85rem; }}
        th {{
            text-align: left; padding: 12px 14px; background: #1a1a24;
            color: #787890; font-weight: 600; font-size: 0.72rem;
            text-transform: uppercase; letter-spacing: 0.04em;
            border-bottom: 1px solid #252535;
        }}
        td {{ padding: 10px 14px; border-bottom: 1px solid #1a1a24; }}
        tr:hover td {{ background: rgba(129,140,248,0.03); }}
        .rank {{ font-weight: 700; color: #787890; min-width: 28px; }}
        .muted {{ color: #787890; font-size: 0.75rem; }}

        .score-badge {{
            display: inline-block; padding: 3px 12px; border-radius: 20px;
            font-size: 0.8rem; font-weight: 700; white-space: nowrap;
        }}
        .gene-tag {{ color: #4ade80; font-weight: 600; }}
        .tier-tag {{
            display: inline-block; padding: 2px 8px; border-radius: 12px;
            font-size: 0.7rem; font-weight: 500; background: rgba(129,140,248,0.1); color: #a5b4fc;
        }}

        /* Dimension bars */
        .dim-bar {{
            display: flex; align-items: center; gap: 6px; margin-bottom: 2px;
        }}
        .dim-label {{ font-size: 0.65rem; color: #787890; width: 55px; text-align: right; }}
        .dim-fill-wrap {{
            flex: 1; height: 6px; background: #1a1a24; border-radius: 3px;
            overflow: hidden;
        }}
        .dim-fill {{ height: 100%; border-radius: 3px; min-width: 2px; transition: width 0.3s; }}
        .dim-val {{ font-size: 0.65rem; color: #a0a0b0; width: 28px; text-align: right; font-weight: 600; }}
        .dims-cell {{ min-width: 280px; }}

        /* Target sections */
        .target-section {{
            background: #13131a; border: 1px solid #252535;
            border-radius: 12px; margin-bottom: 28px; overflow: hidden;
        }}
        .target-header {{
            display: flex; justify-content: space-between; align-items: center;
            padding: 20px 24px; background: #1a1a24; border-bottom: 1px solid #252535;
        }}
        .target-header h3 {{ font-size: 1rem; }}
        .target-header code {{ color: #818cf8; font-size: 0.75rem; margin-left: 4px; }}
        .target-category {{
            display: block; font-size: 0.75rem; color: #787890; margin-top: 2px;
        }}
        .target-mean {{
            font-size: 0.72rem; color: #a0a0b0; margin-top: 4px; display: block;
        }}
        .target-count {{
            font-size: 0.78rem; color: #6b7280; white-space: nowrap;
        }}

        /* Vina */
        .vina-box {{
            padding: 16px 24px; border-top: 1px solid #252535;
            background: rgba(52,211,153,0.03);
        }}
        .vina-box h4 {{ font-size: 0.82rem; color: #34d399; margin-bottom: 10px; }}
        .vina-chips {{ display: flex; flex-wrap: wrap; gap: 8px; }}
        .vina-chip {{
            background: rgba(52,211,153,0.08); border: 1px solid rgba(52,211,153,0.2);
            border-radius: 8px; padding: 6px 12px; font-size: 0.75rem; color: #a0a0b0;
        }}
        .vina-chip strong {{ color: #34d399; }}

        /* Methodology */
        .method-card {{
            background: #13131a; border: 1px solid #252535;
            border-radius: 12px; padding: 24px; margin-bottom: 32px;
        }}
        .method-card h3 {{ font-size: 0.95rem; margin-bottom: 12px; }}
        .method-card ul {{ margin-left: 20px; color: #787890; font-size: 0.85rem; }}
        .method-card li {{ margin-bottom: 6px; }}
        .method-card li strong {{ color: #e0e0e8; }}

        footer {{
            text-align: center; padding: 40px; color: #787890; font-size: 0.75rem;
        }}
        footer a {{ color: #818cf8; }}

        @media (max-width: 768px) {{
            .stats-grid {{ grid-template-columns: repeat(2, 1fr); }}
            .hero {{ padding: 24px; }}
            .hero h1 {{ font-size: 1.3rem; }}
            .target-header {{ flex-direction: column; gap: 8px; }}
        }}
    </style>
</head>
<body>
    <div class="container">
        <div class="hero">
            <h1>🔬 Lupus Virtual Drug Screening Report</h1>
            <p class="subtitle">
                {stats['total_pairings']} Compound-Target Pairings Across {stats['targets_screened']} Genes
                · {stats['compounds_screened']} Compounds Screened
            </p>
            <p class="subtitle" style="font-size:0.78rem;margin-top:8px;">
                Generated: {datetime.now().strftime('%B %d, %Y at %H:%M')}
                · AutoDock Vina: {stats['vina_status']}
                · RDKit: {'available' if stats['rdkit_available'] else 'not available'}
            </p>
        </div>

        <div class="stats-grid">
            <div class="stat-card">
                <div class="stat-value" style="color:#818cf8">{stats['targets_screened']}</div>
                <div class="stat-label">Targets Screened</div>
            </div>
            <div class="stat-card">
                <div class="stat-value" style="color:#4ade80">{stats['compounds_screened']}</div>
                <div class="stat-label">Compounds Screened</div>
            </div>
            <div class="stat-card">
                <div class="stat-value" style="color:#f59e0b">{stats['tier1_count']}</div>
                <div class="stat-label">Tier 1 Hits (≥7.5)</div>
            </div>
            <div class="stat-card">
                <div class="stat-value" style="color:#fbbf24">{stats['tier2_count']}</div>
                <div class="stat-label">Tier 2 Hits (6.5-7.4)</div>
            </div>
            <div class="stat-card">
                <div class="stat-value" style="color:#c084fc">{stats['total_pairings']}</div>
                <div class="stat-label">Total Pairings</div>
            </div>
            <div class="stat-card">
                <div class="stat-value" style="color:#34d399">{stats['vina_status'].split(' ')[0]}</div>
                <div class="stat-label">AutoDock Vina</div>
            </div>
        </div>

        <h2 class="section-title">🏆 Top 20 Overall Virtual Screening Hits</h2>
        <div class="table-container">
            <table>
                <thead>
                    <tr><th>#</th><th>Compound</th><th>Target Gene</th><th>Score</th><th>Tier</th></tr>
                </thead>
                <tbody>{top_overall_rows}</tbody>
            </table>
        </div>

        <h2 class="section-title">🧬 Per-Target Screening Results</h2>
        {target_sections}

        <h2 class="section-title">📐 Methodology</h2>
        <div class="method-card">
            <h3>Scoring Dimensions (each 0-10, weighted)</h3>
            <ul>
                <li><strong>Binding Affinity Estimate (30%)</strong> — Molecular property-based pseudo-binding score considering MW, LogP, hydrogen bonding, and TPSA.</li>
                <li><strong>Drug-Likeness (20%)</strong> — Lipinski Rule of 5 compliance. Biologics scored separately.</li>
                <li><strong>Target Complementarity (25%)</strong> — How well the compound's mechanism and category match the target gene's biology and pathway.</li>
                <li><strong>Similarity to Known SLE Drugs (15%)</strong> — Molecular property similarity and category overlap with existing drug repurposing candidates for the same gene.</li>
                <li><strong>Novelty (10%)</strong> — How novel is this compound-target pairing? Investigational compounds score higher than approved SLE therapies.</li>
            </ul>
            <p style="margin-top:16px;color:#787890;font-size:0.82rem;">
                <strong>AutoDock Vina:</strong> {stats['vina_status']}. Install AutoDock Vina and provide
                protein PDB structures in <code>virtual_screening/targets/</code> for physics-based molecular docking.
                Current screening uses property-based scoring which does not require external binaries.
            </p>
        </div>

        <footer>
            <p>Lupus Virtual Drug Screening Engine · Property-based scoring + optional AutoDock Vina docking</p>
            <p>Compound library derived from the <a href="../knowledge_graph/web/index.html">Lupus Knowledge Graph</a></p>
            <p style="margin-top:8px;color:#6b7280;">
                Disclaimer: Virtual screening results are computational predictions. All hits require experimental validation.
            </p>
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
