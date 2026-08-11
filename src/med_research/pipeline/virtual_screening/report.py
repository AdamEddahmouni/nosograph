"""Disease-aware virtual screening HTML report generator.

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
from typing import Any, Mapping

from med_research.pipeline.reporting import disease_context, render_report

try:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import numpy as np
    MPL_AVAILABLE = True
except ImportError:
    MPL_AVAILABLE = False
    np: Any = None  # type: ignore[no-redef]


def generate_screening_report(
    results: Mapping[str, Any], disease_id: str = "sle", *, provenance: dict | None = None
) -> str:
    """Generate an HTML report from virtual screening results."""

    output_path = Path(__file__).parent / "screening_report.html"
    context = disease_context(disease_id)
    stats = results["stats"]
    coverage = results.get("coverage", {})
    if results.get("status") == "blocked":
        output_path.write_text(
            "<!doctype html><html><head><meta charset='utf-8'><title>Virtual screening blocked</title></head>"
            "<body><h1>Virtual screening blocked</h1>"
            f"<p>{escape_html('; '.join(coverage.get('limitations', ['Disease-specific strategy unavailable.'])))}</p>"
            f"<p>Coverage: {escape_html(coverage.get('level', 'unsupported'))} / "
            f"{escape_html(coverage.get('status', 'blocked'))}</p></body></html>",
            encoding="utf-8",
        )
        return str(output_path)
    strategy_id = results.get("strategy_id", "")
    strategy_fingerprint = results.get("strategy_fingerprint", "")
    strategy_limitations = results.get("strategy_limitations", [])
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
            '<span class="docking-badge docking-real">🧬 Real</span>'
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

    # ── Assemble via template ──────────────────────────────────────
    html = render_report(
        "reports/virtual_screening.html",
        {
            "ctx_disease": context["name"],
            "ctx_disease_id": context["id"],
            "ctx_0": stats["total_pairings"],
            "ctx_1": stats["targets_screened"],
            "ctx_2": stats["compounds_screened"],
            "ctx_3": f"· {vina_docked_count} Real Docking Scores" if has_real_docking else "",
            "ctx_4": datetime.now().strftime("%B %d, %Y at %H:%M"),
            "ctx_5": stats["vina_status"],
            "ctx_6": "available" if stats["rdkit_available"] else "not available",
            "ctx_7": stats["targets_screened"],
            "ctx_8": stats["compounds_screened"],
            "ctx_9": stats["tier1_count"],
            "ctx_10": stats["tier2_count"],
            "ctx_11": stats["total_pairings"],
            "ctx_12": vina_docked_count,
            "ctx_13": docking_summary,
            "ctx_14": comparison_section,
            "ctx_15": top_overall_rows,
            "ctx_16": target_sections,
            "ctx_17": target_radars,
            "ctx_18": "Physics-based AutoDock Vina docking score (ΔG) when available; " if has_real_docking else "",
            "ctx_19": stats["vina_status"],
            "ctx_20": (
                "When active, the top 5 property-scored compounds per target are re-scored using physics-based molecular docking with curated PDB structures and defined binding site grids. Vina binding free energy (kcal/mol) is normalized to the 0–10 binding score using a linear mapping: −11 kcal/mol → 10, −5 kcal/mol → 0."
                if has_real_docking
                else (
                    "Curated protein PDB structures for physics-based AutoDock Vina docking "
                    "are not yet available for this disease module. Binding scores use "
                    "property-based estimates (MW, LogP, hydrogen bonding, TPSA) that do "
                    "not require external binaries."
                    if context["id"] != "sle"
                    else "Install AutoDock Vina and provide protein PDB structures in <code>virtual_screening/targets/</code> for physics-based molecular docking. Current screening uses property-based scoring which does not require external binaries."
                )
            ),
            "ctx_21": "Real docking (AutoDock Vina) + " if has_real_docking else "",
            "ctx_22": top5_json,
        },
        disease_id,
        provenance=provenance,
    )
    strategy_note = (
        f"<section class=\"strategy-provenance\"><strong>Screening strategy:</strong> "
        f"{escape_html(strategy_id)} · fingerprint {escape_html(strategy_fingerprint[:16])}… "
        f"<br><span>Coverage: {escape_html(coverage.get('level', 'unknown'))} / "
        f"{escape_html(coverage.get('status', 'unknown'))}</span> "
        f"<br><span>Limitations: {escape_html('; '.join(strategy_limitations))}</span>"
        f"{_docking_scope_note(context['id'], context['name'])}"
        f"</section>"
        if strategy_id else ""
    )
    if strategy_note:
        if provenance:
            html = html.replace(
                '<div class="meta provenance">',
                f"{strategy_note}\n<div class=\"meta provenance\">",
                1,
            )
        else:
            html = html.replace("</body>", f"{strategy_note}\n</body>", 1)

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
    pairs = []
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

    ax.bar(x - width / 2, real_scores, width, label="Real Docking (Vina)",
                   color="#34d399", edgecolor="#252535", linewidth=0.5)
    ax.bar(x + width / 2, prop_scores, width, label="Property-Based Estimate",
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
        from med_research.pipeline.virtual_screening.screening import compute_binding_estimate
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


def _docking_scope_note(disease_id: str, disease_name: str) -> str:
    """Clarify that Vina PDB docking is not available for non-primary target sets."""
    if disease_id == "sle":
        return ""
    return (
        "<br><span><strong>Docking scope:</strong> Physics-based AutoDock Vina docking "
        "requires curated PDB target structures, which are not yet available for "
        f"{escape_html(disease_name)}. Property-based binding estimates are used instead.</span>"
    )


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
