"""
Lupus Virtual Screening Report Generator

Generates a standalone HTML report showing:
  - Screening overview and statistics (incl. real docking counts)
  - Per-target top compound rankings with Vina docking badges
  - Score breakdown with visual bars
  - Real vs property-based binding score comparison
  - AutoDock Vina docking results per target
  - Methodology section (property-based + real docking)
"""

import base64
import io
from datetime import datetime
from pathlib import Path

try:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import numpy as np
    MPL_AVAILABLE = True
except ImportError:
    MPL_AVAILABLE = False
    np = None


def generate_screening_report(results: dict) -> str:
    """Generate an HTML report from virtual screening results."""

    output_path = Path(__file__).parent / "screening_report.html"
    stats = results["stats"]
    vina_docked_count = stats.get("vina_docked_count", 0)
    has_vina = stats.get("vina_available", False)
    has_real_docking = vina_docked_count > 0

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

            # Vina docking badge
            vina_badge = ""
            if c.get("vina_docked"):
                kcal = c.get("vina_best_kcal")
                kcal_str = f"{kcal:.1f} kcal/mol" if kcal is not None else "docked"
                vina_badge = (
                    f'<span class="vina-badge" title="Real AutoDock Vina docking score">'
                    f'🧬 {kcal_str}</span>'
                )

            # Score bars — highlight Binding bar when real docking was used
            dims = [
                ("Binding", c.get("binding_estimate", 0),
                 "#34d399" if c.get("vina_docked") else "#818cf8",
                 c.get("vina_docked", False)),
                ("Drug-Like", c.get("druglikeness", 0), "#4ade80", False),
                ("Target", c.get("target_complementarity", 0), "#f59e0b", False),
                ("Similarity", c.get("similarity_score", 0), "#c084fc", False),
                ("Novelty", c.get("novelty_score", 0), "#34d399", False),
            ]
            bars_html = "".join(
                f'<div class="dim-bar">'
                f'<span class="dim-label{" dim-docked" if is_docked else ""}">{label}</span>'
                f'<div class="dim-fill-wrap">'
                f'<div class="dim-fill{" dim-docked-fill" if is_docked else ""}" '
                f'style="width:{val*10}%;background:{color}"></div></div>'
                f'<span class="dim-val{" dim-val-docked" if is_docked else ""}">{val:.1f}</span>'
                f'</div>'
                for label, val, color, is_docked in dims
            )

            compound_rows += f"""
            <tr>
                <td class="rank">{i}</td>
                <td>
                    <strong>{escape_html(c['name'][:45])}</strong>
                    {vina_badge}
                    <br><span class="muted">{escape_html(c.get('type', ''))} · {escape_html(c.get('category', '')[:35])}</span>
                </td>
                <td>
                    <span class="score-badge" style="background:{score_color}20;color:{score_color};border:1px solid {score_color}40">
                        {tier_icon} {score:.1f}
                    </span>
                </td>
                <td class="dims-cell">{bars_html}</td>
            </tr>"""

        # Vina docking summary per target
        vina_section = ""
        target_docked = [c for c in top if c.get("vina_docked")]
        if target_docked:
            vina_rows = ""
            for c in target_docked:
                kcal = c.get("vina_best_kcal")
                kcal_display = f"{kcal:.1f} kcal/mol" if kcal is not None else "N/A"
                vina_rows += (
                    f'<div class="vina-chip">'
                    f'<strong>{c["name"][:30]}</strong>: {kcal_display}'
                    f'</div>'
                )

            vina_section = f"""
            <div class="vina-box">
                <h4>🧬 Real AutoDock Vina Docking ({len(target_docked)} compounds)</h4>
                <p class="vina-note">These compounds were re-scored using physics-based
                molecular docking. Binding scores reflect actual Vina ΔG predictions
                rather than property-based estimates.</p>
                <div class="vina-chips">{vina_rows}</div>
            </div>"""
        elif has_vina:
            vina_section = """
            <div class="vina-box-empty">
                <span>🔬 No real docking for this target — property-based scores used</span>
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

    # ── Top overall hits radar chart JSON ───────────────────────────────
    import json
    top5 = results.get("all_results", [])[:5]
    top5_items = []
    for c in top5:
        top5_items.append({
            "name": c.get('name', '')[:22],
            "scores": [
                round(c.get('binding_estimate', 0), 1),
                round(c.get('druglikeness', 0), 1),
                round(c.get('target_complementarity', 0), 1),
                round(c.get('similarity_score', 0), 1),
                round(c.get('novelty_score', 0), 1),
            ],
        })
    top5_json = json.dumps(top5_items)

    # ── Per-target radar charts ────────────────────────────────────────
    target_radars = ""
    for gene_id, target_data in sorted(results.get("results_per_target", {}).items()):
        top = target_data["top_compounds"][:5]
        if not top:
            continue
        gene_name = gene_names.get(gene_id, gene_id)
        target_items = []
        for c in top:
            target_items.append({
                "name": c.get('name', '')[:22],
                "scores": [
                    round(c.get('binding_estimate', 0), 1),
                    round(c.get('druglikeness', 0), 1),
                    round(c.get('target_complementarity', 0), 1),
                    round(c.get('similarity_score', 0), 1),
                    round(c.get('novelty_score', 0), 1),
                ],
            })
        target_json = json.dumps(target_items)
        chart_id = f"radar_{gene_id}"
        target_radars += f"""
        <h3 style="color:#c0c0d0;font-size:0.95rem;margin:20px 0 8px;">🧬 {escape_html(gene_name)}</h3>
        <div class="radar-container" style="max-width:600px;margin:0 auto 24px;">
            <canvas id="{chart_id}" style="max-height:400px;"></canvas>
        </div>
        <script>
        (function() {{
            const data = {target_json};
            const labels = ['Binding', 'Drug-Like', 'Target', 'Similarity', 'Novelty'];
            const colors = ['#818cf8', '#4ade80', '#f59e0b', '#f472b6', '#34d399'];
            const datasets = data.map((c, i) => ({{
                label: c.name,
                data: c.scores,
                borderColor: colors[i % colors.length],
                backgroundColor: colors[i % colors.length] + '12',
                borderWidth: 2,
                pointRadius: 3,
            }}));
            new Chart(document.getElementById('{chart_id}'), {{
                type: 'radar',
                data: {{ labels, datasets }},
                options: {{
                    responsive: true, maintainAspectRatio: true,
                    scales: {{ r: {{ beginAtZero: true, max: 10, ticks: {{ backdropColor: 'transparent', color: '#787890', font: {{ size: 9 }} }}, grid: {{ color: '#252535' }}, pointLabels: {{ color: '#c0c0d0', font: {{ size: 10 }} }}, angleLines: {{ color: '#252535' }} }} }},
                    plugins: {{ legend: {{ position: 'bottom', labels: {{ color: '#c0c0d0', font: {{ size: 10 }}, padding: 10, usePointStyle: true }} }} }}
                }}
            }});
        }})();
        </script>"""

    # ── Top overall hits ────────────────────────────────────────────────

    top_overall_rows = ""
    for i, c in enumerate(results.get("all_results", [])[:20], 1):
        score = c["composite_score"]
        score_color = (
            "#4ade80" if score >= 7.5 else "#fbbf24" if score >= 6.5 else "#f87171"
        )
        docking_col = (
            f'<span class="docking-badge docking-real">🧬 Real</span>'
            if c.get("vina_docked")
            else '<span class="docking-badge docking-prop">📐 Property</span>'
        )
        top_overall_rows += f"""
        <tr>
            <td class="rank">{i}</td>
            <td><strong>{escape_html(c['name'][:45])}</strong></td>
            <td><span class="gene-tag">{c.get('gene_name', '')[:25]}</span></td>
            <td><span style="color:{score_color};font-weight:700;font-size:1.1em">{score:.1f}</span></td>
            <td><span class="tier-tag">{c.get('tier', '').split('—')[0].strip()}</span></td>
            <td>{docking_col}</td>
        </tr>"""

    # ── Real vs property comparison chart ────────────────────────────────

    comparison_chart = ""
    if has_real_docking and MPL_AVAILABLE:
        comparison_chart = _generate_comparison_chart(results["all_results"])

    # ── Real docking summary ──────────────────────────────────────────

    docking_summary = ""
    if has_real_docking:
        docked_compounds = [c for c in results.get("all_results", []) if c.get("vina_docked")]
        best_docked = docked_compounds[:3] if docked_compounds else []

        docked_rows = ""
        for c in best_docked:
            kcal = c.get("vina_best_kcal")
            kcal_str = f"{kcal:.1f} kcal/mol" if kcal is not None else "N/A"
            docked_rows += f"""
            <tr>
                <td><strong>{escape_html(c['name'][:40])}</strong></td>
                <td><span class="gene-tag">{c.get('gene_name', '')[:25]}</span></td>
                <td style="color:#34d399;font-weight:700">{kcal_str}</td>
                <td style="color:#818cf8;font-weight:600">{c['composite_score']:.1f}</td>
            </tr>"""

        docking_summary = f"""
        <h2 class="section-title">🧬 Real Docking Summary</h2>
        <p style="color:#787890;font-size:0.82rem;margin-bottom:12px">
            {vina_docked_count} compound-target pairings were re-scored using
            AutoDock Vina molecular docking. Binding scores reflect
            physics-based binding free energy (ΔG) predictions.
        </p>
        <div class="table-container">
            <table>
                <thead>
                    <tr><th>Compound</th><th>Target</th><th>Vina ΔG</th><th>Composite</th></tr>
                </thead>
                <tbody>{docked_rows}</tbody>
            </table>
        </div>
        """

    # ── Assemble HTML ───────────────────────────────────────────────────

    # Determine if comparison chart section should appear
    comparison_section = ""
    if comparison_chart:
        comparison_section = f"""
        <h2 class="section-title">📊 Real vs Property-Based Binding Scores</h2>
        <div class="chart-card" style="margin-bottom:28px">
            <img src="data:image/png;base64,{comparison_chart}" alt="Real vs Property Comparison" style="max-width:100%"/>
        </div>"""

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Lupus Virtual Drug Screening Report</title>
    <script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.7/dist/chart.umd.min.js"></script>
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
            display: grid; grid-template-columns: repeat(auto-fit, minmax(160px, 1fr));
            gap: 14px; margin-bottom: 32px;
        }}
        .stat-card {{
            background: #13131a; border: 1px solid #252535;
            border-radius: 12px; padding: 20px; text-align: center;
            transition: border-color 0.2s, transform 0.2s;
        }}
        .stat-card:hover {{ border-color: #4b5563; transform: translateY(-1px); }}
        .stat-card .stat-value {{ font-size: 1.8rem; font-weight: 800; }}
        .stat-card .stat-label {{ color: #787890; font-size: 0.72rem; margin-top: 4px; }}

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

        /* Vina docking badge */
        .vina-badge {{
            display: inline-block; margin-left: 8px; padding: 1px 8px;
            border-radius: 10px; font-size: 0.65rem; font-weight: 600;
            background: rgba(52,211,153,0.12); color: #34d399;
            border: 1px solid rgba(52,211,153,0.2);
            white-space: nowrap; vertical-align: middle;
        }}
        .docking-badge {{
            display: inline-block; padding: 2px 8px; border-radius: 10px;
            font-size: 0.65rem; font-weight: 600;
        }}
        .docking-real {{
            background: rgba(52,211,153,0.12); color: #34d399;
            border: 1px solid rgba(52,211,153,0.2);
        }}
        .docking-prop {{
            background: rgba(129,140,248,0.08); color: #818cf8;
            border: 1px solid rgba(129,140,248,0.15);
        }}

        /* Dimension bars */
        .dim-bar {{
            display: flex; align-items: center; gap: 6px; margin-bottom: 2px;
        }}
        .dim-label {{ font-size: 0.65rem; color: #787890; width: 55px; text-align: right; }}
        .dim-label.dim-docked {{ color: #34d399; font-weight: 600; }}
        .dim-fill-wrap {{
            flex: 1; height: 6px; background: #1a1a24; border-radius: 3px;
            overflow: hidden;
        }}
        .dim-fill {{ height: 100%; border-radius: 3px; min-width: 2px; transition: width 0.3s; }}
        .dim-fill.dim-docked-fill {{ box-shadow: 0 0 4px rgba(52,211,153,0.3); }}
        .dim-val {{ font-size: 0.65rem; color: #a0a0b0; width: 28px; text-align: right; font-weight: 600; }}
        .dim-val.dim-val-docked {{ color: #34d399; }}
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

        /* Vina docking box */
        .vina-box {{
            padding: 16px 24px; border-top: 1px solid #252535;
            background: rgba(52,211,153,0.03);
        }}
        .vina-box h4 {{ font-size: 0.82rem; color: #34d399; margin-bottom: 6px; }}
        .vina-note {{
            font-size: 0.72rem; color: #6b7280; margin-bottom: 10px;
        }}
        .vina-chips {{ display: flex; flex-wrap: wrap; gap: 8px; }}
        .vina-chip {{
            background: rgba(52,211,153,0.08); border: 1px solid rgba(52,211,153,0.2);
            border-radius: 8px; padding: 6px 12px; font-size: 0.75rem; color: #a0a0b0;
        }}
        .vina-chip strong {{ color: #34d399; }}
        .vina-box-empty {{
            padding: 12px 24px; border-top: 1px solid #252535;
            background: rgba(129,140,248,0.02); color: #6b7280; font-size: 0.75rem;
        }}

        /* Chart card */
        .chart-card {{
            background: #13131a; border: 1px solid #252535;
            border-radius: 12px; padding: 20px; text-align: center;
        }}

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
                {f"· {vina_docked_count} Real Docking Scores" if has_real_docking else ""}
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
                <div class="stat-value" style="color:#34d399">{vina_docked_count}</div>
                <div class="stat-label">🧬 Real Docking Scores</div>
            </div>
        </div>

        <h2 class="section-title">🎯 Score Dimension Radar — Top 5 Overall Hits</h2>
        <div class="radar-container" style="max-width:700px;margin:0 auto 28px;">
            <canvas id="radarChart" style="max-height:500px;"></canvas>
        </div>

        {docking_summary}

        {comparison_section}

        <h2 class="section-title">🏆 Top 20 Overall Virtual Screening Hits</h2>
        <div class="table-container">
            <table>
                <thead>
                    <tr><th>#</th><th>Compound</th><th>Target Gene</th><th>Score</th><th>Tier</th><th>Docking</th></tr>
                </thead>
                <tbody>{top_overall_rows}</tbody>
            </table>
        </div>

        <h2 class="section-title">🧬 Per-Target Screening Results</h2>
        {target_sections}

        <h2 class="section-title">🎯 Per-Target Radar Charts</h2>
        {target_radars}

        <h2 class="section-title">📐 Methodology</h2>
        <div class="method-card">
            <h3>Scoring Dimensions (each 0–10, weighted)</h3>
            <ul>
                <li><strong>Binding Affinity Estimate (30%)</strong> — {'Physics-based AutoDock Vina docking score (ΔG) when available; ' if has_real_docking else ''}Otherwise, molecular property-based pseudo-binding score using MW, LogP, hydrogen bonding, and TPSA.</li>
                <li><strong>Drug-Likeness (20%)</strong> — Lipinski Rule of 5 compliance. Biologics scored separately.</li>
                <li><strong>Target Complementarity (25%)</strong> — How well the compound's mechanism and category match the target gene's biology and pathway.</li>
                <li><strong>Similarity to Known SLE Drugs (15%)</strong> — Molecular property similarity and category overlap with existing drug repurposing candidates for the same gene.</li>
                <li><strong>Novelty (10%)</strong> — How novel is this compound-target pairing? Investigational compounds score higher than approved SLE therapies.</li>
            </ul>
            <p style="margin-top:16px;color:#787890;font-size:0.82rem;">
                <strong>AutoDock Vina:</strong> {stats['vina_status']}.
                {'When active, the top 5 property-scored compounds per target are re-scored using physics-based molecular docking with curated PDB structures and defined binding site grids. Vina binding free energy (kcal/mol) is normalized to the 0–10 binding score using a linear mapping: −11 kcal/mol → 10, −5 kcal/mol → 0.' if has_real_docking else 'Install AutoDock Vina and provide protein PDB structures in <code>virtual_screening/targets/</code> for physics-based molecular docking. Current screening uses property-based scoring which does not require external binaries.'}
            </p>
        </div>

        <footer>
            <p>Lupus Virtual Drug Screening Engine · {'Real docking (AutoDock Vina) + ' if has_real_docking else ''}Property-based scoring</p>
            <p>Compound library derived from the <a href="../knowledge_graph/web/index.html">Lupus Knowledge Graph</a></p>
            <p style="margin-top:8px;color:#6b7280;">
                Disclaimer: Virtual screening results are computational predictions. All hits require experimental validation.
            </p>
        </footer>
    </div>
    <script>
(function() {{
    const top5 = {top5_json};
    const labels = ['Binding', 'Drug-Like', 'Target', 'Similarity', 'Novelty'];
    const colors = ['#818cf8', '#4ade80', '#f59e0b', '#f472b6', '#34d399'];
    const datasets = top5.map((c, i) => ({{
        label: c.name,
        data: c.scores,
        borderColor: colors[i % colors.length],
        backgroundColor: colors[i % colors.length] + '15',
        borderWidth: 2,
        pointBackgroundColor: colors[i % colors.length],
        pointRadius: 3,
    }}));
    new Chart(document.getElementById('radarChart'), {{
        type: 'radar',
        data: {{ labels, datasets }},
        options: {{
            responsive: true, maintainAspectRatio: true,
            scales: {{ r: {{ beginAtZero: true, max: 10, ticks: {{ backdropColor: 'transparent', color: '#787890', font: {{ size: 10 }} }}, grid: {{ color: '#252535' }}, pointLabels: {{ color: '#c0c0d0', font: {{ size: 11 }} }}, angleLines: {{ color: '#252535' }} }} }},
            plugins: {{ legend: {{ position: 'bottom', labels: {{ color: '#c0c0d0', font: {{ size: 11 }}, padding: 14, usePointStyle: true }} }} }}
        }}
    }});
}})();
</script>
</body>
</html>"""

    with open(output_path, "w", encoding="utf-8") as f:
        f.write(html)

    return str(output_path)


def _generate_comparison_chart(all_results: list) -> str:
    """Generate a bar chart comparing real docking vs property-based binding scores."""
    if not MPL_AVAILABLE:
        return ""

    docked = [c for c in all_results if c.get("vina_docked")]
    if len(docked) == 0:
        return ""

    # Collect pairs for docked compounds (showing all with a cap at 15)
    display_n = min(len(docked), 15)
    for c in docked[:display_n]:
        pairs.append((
            c["name"][:20],
            c.get("binding_estimate", 0),
            # Get original property score — approximate from other dimensions
            # Since we replaced binding_estimate with real score, we estimate
            # the property score from compound properties
            _estimate_property_score(c),
        ))

    labels = [p[0] for p in pairs]
    real_scores = [p[1] for p in pairs]
    prop_scores = [p[2] for p in pairs]

    fig, ax = plt.subplots(figsize=(10, 5))
    fig.patch.set_facecolor("#13131a")
    ax.set_facecolor("#13131a")

    x = np.arange(len(labels))
    width = 0.35

    bars1 = ax.bar(x - width / 2, real_scores, width, label="Real Docking (Vina)",
                   color="#34d399", edgecolor="#252535", linewidth=0.5)
    bars2 = ax.bar(x + width / 2, prop_scores, width, label="Property-Based Estimate",
                   color="#818cf8", edgecolor="#252535", linewidth=0.5)

    ax.set_ylabel("Binding Score (0-10)", color="#787890", fontsize=9)
    ax.set_xticks(x)
    ax.set_xticklabels(labels, rotation=45, ha="right", fontsize=7, color="#e0e0e8")
    ax.tick_params(colors="#e0e0e8", labelsize=7)
    ax.legend(fontsize=8, facecolor="#13131a", edgecolor="#252535",
              labelcolor="#e0e0e8")
    ax.set_ylim(0, 11)
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.spines["bottom"].set_color("#252535")
    ax.spines["left"].set_color("#252535")

    plt.tight_layout()
    buf = io.BytesIO()
    plt.savefig(buf, format="png", dpi=120, facecolor="#13131a", bbox_inches="tight")
    plt.close()
    return base64.b64encode(buf.getvalue()).decode()


def _estimate_property_score(compound: dict) -> float:
    """Reconstruct what the property-based binding score would have been.

    Delegates to compute_binding_estimate() from screening.py.
    That function only uses compound properties (MW, LogP, HBD, HBA, TPSA)
    and ignores the gene_info parameter, so passing an empty dict is safe.
    """
    try:
        from virtual_screening.screening import compute_binding_estimate
        return compute_binding_estimate(compound, {})
    except ImportError:
        # Fallback if screening module not available
        mw = compound.get("mw", 400)
        logp = compound.get("logp", 2.0)
        hbd = compound.get("hbd", 2)
        hba = compound.get("hba", 5)
        tpsa = compound.get("tpsa", 100)
        if mw > 50000:
            return 3.0
        score = 5.0
        if 200 <= mw <= 600:
            score += 2.0
        elif 100 <= mw <= 800:
            score += 1.0
        elif mw > 800:
            score -= 1.0
        if 1 <= logp <= 4:
            score += 1.5
        elif 0 <= logp <= 5:
            score += 0.5
        if 1 <= hbd <= 4 and 2 <= hba <= 8:
            score += 1.5
        if tpsa < 140:
            score += 1.0
        return round(max(0.0, min(10.0, score)), 1)


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
