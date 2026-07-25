"""
ML Target Predictor Report Generator

Generates a standalone HTML report with:
  - Model metrics and SHAP feature importance
  - Top predicted druggable targets table
  - SHAP summary plot and feature importance bar chart
"""

import base64
import io
from datetime import datetime
from pathlib import Path

try:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import matplotlib.ticker as ticker
    import numpy as np
    MPL_AVAILABLE = True
except ImportError:
    MPL_AVAILABLE = False
    np = None


def generate_ml_report(results: dict) -> str:
    """Generate an HTML report from ML prediction results."""
    output_path = Path(__file__).parent / "ml_report.html"

    metrics = results.get("model_metrics", {})
    top = results.get("top_untargeted", [])
    importance = results.get("feature_importance", {})
    shap = results.get("shap_summary", [])

    # ── Charts ──────────────────────────────────────────────────
    importance_chart = _generate_importance_chart(importance) if MPL_AVAILABLE else ""
    shap_chart = _generate_shap_chart(shap) if MPL_AVAILABLE and shap else ""

    # ── Stats ────────────────────────────────────────────────────
    stats_html = f"""
    <div class="stats-grid">
        <div class="stat-card">
            <div class="stat-value" style="color:#60a5fa">{metrics.get('n_genes', 0)}</div>
            <div class="stat-label">Genes Analyzed</div>
        </div>
        <div class="stat-card">
            <div class="stat-value" style="color:#4ade80">{metrics.get('n_targeted', 0)}</div>
            <div class="stat-label">Already Targeted</div>
        </div>
        <div class="stat-card">
            <div class="stat-value" style="color:#c084fc">{metrics.get('n_untargeted', 0)}</div>
            <div class="stat-label">Untargeted (Opportunity)</div>
        </div>
        <div class="stat-card">
            <div class="stat-value" style="color:#fbbf24">{metrics.get('cv_roc_auc_mean', 0):.3f}</div>
            <div class="stat-label">CV ROC-AUC</div>
        </div>
        <div class="stat-card">
            <div class="stat-value" style="color:#f472b6">{len(top)}</div>
            <div class="stat-label">Predicted Novel Targets</div>
        </div>
        <div class="stat-card">
            <div class="stat-value" style="color:#34d399">{len(importance)}</div>
            <div class="stat-label">Features</div>
        </div>
    </div>"""

    # ── Top predictions table ────────────────────────────────────
    rows = ""
    for i, p in enumerate(top, 1):
        score = p["druggability_score"]
        score_color = "#4ade80" if score >= 0.8 else "#fbbf24" if score >= 0.6 else "#f87171"
        bar_width = int(score * 150)
        or_val = p.get("odds_ratio", "")
        or_display = f"{or_val:.1f}" if or_val else "—"
        rows += f"""
        <tr>
            <td style="color:#787890">{i}</td>
            <td><strong>{_escape(p['gene_name'][:50])}</strong></td>
            <td><span class="score-badge" style="background:rgba(96,165,250,0.1);color:#60a5fa">{p.get('category', '')}</span></td>
            <td style="color:{score_color};font-weight:700">{score:.3f}</td>
            <td>{or_display}</td>
            <td>{p.get('degree', 0)}</td>
            <td>
                <div class="bar-container">
                    <div class="bar-fill" style="width:{bar_width}px;background:linear-gradient(90deg,{score_color},#34d399)"></div>
                </div>
            </td>
        </tr>"""

    # ── Feature importance table ─────────────────────────────────
    imp_rows = ""
    for i, (feat, imp) in enumerate(list(importance.items())[:15]):
        w = int(imp * 300)
        imp_rows += f"""
        <tr>
            <td>{i+1}</td>
            <td><code>{feat}</code></td>
            <td style="font-weight:600;color:#fbbf24">{imp:.4f}</td>
            <td><div class="bar-fill" style="width:{w}px;background:linear-gradient(90deg,#818cf8,#c084fc)"></div></td>
        </tr>"""

    # ── Assemble HTML ────────────────────────────────────────────
    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>ML Target Predictor Report</title>
    <link rel="preconnect" href="https://fonts.googleapis.com">
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap" rel="stylesheet">
    <style>
        :root {{ --text-muted: #787890; }}
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
            background: linear-gradient(135deg, #818cf8, #c084fc, #f472b6, #fbbf24);
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
        }}
        .stat-card .stat-value {{ font-size: 1.8rem; font-weight: 800; }}
        .stat-card .stat-label {{ color: #787890; font-size: 0.75rem; margin-top: 4px; }}

        .section-title {{
            font-size: 1.2rem; font-weight: 700; margin: 36px 0 16px;
            padding-bottom: 8px; border-bottom: 1px solid #252535;
        }}

        .charts-row {{
            display: grid; grid-template-columns: repeat(auto-fit, minmax(450px, 1fr));
            gap: 20px; margin-bottom: 28px;
        }}
        .chart-card {{
            background: #13131a; border: 1px solid #252535;
            border-radius: 12px; padding: 20px; text-align: center;
        }}
        .chart-card img {{ max-width: 100%; height: auto; border-radius: 6px; }}
        .chart-card h4 {{ font-size: 0.9rem; color: #787890; margin-bottom: 12px; font-weight: 600; }}

        .table-container {{
            overflow-x: auto; background: #13131a;
            border: 1px solid #252535; border-radius: 12px; margin-bottom: 28px;
        }}
        table {{ width: 100%; border-collapse: collapse; font-size: 0.82rem; }}
        th {{
            text-align: left; padding: 12px 14px; background: #1a1a24;
            color: #787890; font-weight: 600; font-size: 0.7rem;
            text-transform: uppercase; letter-spacing: 0.04em;
            border-bottom: 1px solid #252535;
        }}
        td {{ padding: 10px 14px; border-bottom: 1px solid #1a1a24; }}
        tr:hover td {{ background: rgba(129,140,248,0.03); }}

        .bar-container {{ display: flex; align-items: center; gap: 8px; }}
        .bar-fill {{ height: 8px; border-radius: 4px; min-width: 3px; }}

        .score-badge {{
            display: inline-block; padding: 2px 8px; border-radius: 10px;
            font-size: 0.68rem; font-weight: 600;
        }}
        code {{
            font-family: 'SF Mono', monospace; font-size: 0.72rem;
            background: #1a1a24; padding: 2px 6px; border-radius: 4px;
        }}

        footer {{
            text-align: center; padding: 40px 20px;
            color: #787890; font-size: 0.75rem;
            border-top: 1px solid #252535; margin-top: 40px;
        }}
        footer a {{ color: #818cf8; text-decoration: none; }}

        @media (max-width: 768px) {{
            .stats-grid {{ grid-template-columns: repeat(2, 1fr); }}
            .charts-row {{ grid-template-columns: 1fr; }}
        }}
    </style>
</head>
<body>
    <div class="container">
        <div class="hero">
            <h1>ML Target Predictor Report</h1>
            <p class="subtitle">
                XGBoost-Based Druggability Prediction · {metrics.get('n_genes', 0)} Genes ·
                CV ROC-AUC: {metrics.get('cv_roc_auc_mean', 0):.3f}
            </p>
            <p class="subtitle" style="font-size:0.78rem;margin-top:8px;">
                Generated: {datetime.now().strftime('%B %d, %Y at %H:%M')}
            </p>
        </div>

        {stats_html}

        <h2 class="section-title">🎯 Top Predicted Novel Druggable Targets</h2>
        <p style="color:#787890;font-size:0.82rem;margin-bottom:12px">
            Genes currently without direct therapeutic agents, ranked by XGBoost druggability score
        </p>
        <div class="table-container">
            <table>
                <thead><tr>
                    <th>#</th><th>Gene</th><th>Category</th><th>Score</th>
                    <th>OR</th><th>Degree</th><th>Confidence</th>
                </tr></thead>
                <tbody>{rows}</tbody>
            </table>
        </div>

        <h2 class="section-title">📊 Feature Importance & SHAP</h2>
        <div class="charts-row">
            {f'<div class="chart-card"><h4>XGBoost Feature Importance</h4><img src="data:image/png;base64,{importance_chart}" alt="Feature Importance"/></div>' if importance_chart else ''}
            {f'<div class="chart-card"><h4>SHAP Feature Impact</h4><img src="data:image/png;base64,{shap_chart}" alt="SHAP"/></div>' if shap_chart else ''}
        </div>

        <h2 class="section-title">📋 Full Feature Importance</h2>
        <div class="table-container">
            <table>
                <thead><tr><th>#</th><th>Feature</th><th>Importance</th><th></th></tr></thead>
                <tbody>{imp_rows}</tbody>
            </table>
        </div>

        <footer>
            <p>ML Target Predictor · XGBoost + SHAP · Lupus Research Platform</p>
            <p>Traind on <a href="../knowledge_graph/web/index.html">Lupus Knowledge Graph</a> gene features</p>
            <p style="margin-top:8px;color:#6b7280;">
                Disclaimer: Predictions are computational hypotheses. All targets require experimental validation.
            </p>
        </footer>
    </div>
</body>
</html>"""

    with open(output_path, "w", encoding="utf-8") as f:
        f.write(html)

    return str(output_path)


def _generate_importance_chart(importance: dict) -> str:
    """Generate feature importance bar chart."""
    fig, ax = plt.subplots(figsize=(8, 5))
    fig.patch.set_facecolor("#13131a")
    ax.set_facecolor("#13131a")

    items = list(importance.items())[:12]
    labels = [i[0].replace("cat_", "").replace("_", " ")[:30] for i in items]
    values = [i[1] for i in items]
    colors = plt.cm.viridis(np.linspace(0.2, 0.9, len(labels))) if np else ["#818cf8"] * len(labels)

    bars = ax.barh(labels[::-1], values[::-1], color=colors[::-1], edgecolor="#252535",
                   linewidth=0.5, height=0.6)
    for bar, val in zip(bars, values[::-1]):
        ax.text(bar.get_width() + 0.002, bar.get_y() + bar.get_height() / 2,
                f"{val:.4f}", ha="left", va="center", fontsize=8, color="#e0e0e8")

    ax.set_xlabel("Importance", color="#787890", fontsize=9)
    ax.tick_params(colors="#e0e0e8", labelsize=8)
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.spines["bottom"].set_color("#252535")
    ax.spines["left"].set_color("#252535")

    plt.tight_layout()
    buf = io.BytesIO()
    plt.savefig(buf, format="png", dpi=120, facecolor="#13131a", bbox_inches="tight")
    plt.close()
    return base64.b64encode(buf.getvalue()).decode()


def _generate_shap_chart(shap_summary: list) -> str:
    """Generate SHAP feature impact chart."""
    if not shap_summary:
        return ""

    fig, ax = plt.subplots(figsize=(8, 5))
    fig.patch.set_facecolor("#13131a")
    ax.set_facecolor("#13131a")

    items = shap_summary[:12]
    labels = [i["feature"].replace("cat_", "").replace("_", " ")[:30] for i in items]
    values = [i["mean_abs_shap"] for i in items]
    colors = plt.cm.plasma(np.linspace(0.2, 0.9, len(labels))) if np else ["#f472b6"] * len(labels)

    bars = ax.barh(labels[::-1], values[::-1], color=colors[::-1], edgecolor="#252535",
                   linewidth=0.5, height=0.6)
    for bar, val in zip(bars, values[::-1]):
        ax.text(bar.get_width() + 0.0005, bar.get_y() + bar.get_height() / 2,
                f"{val:.4f}", ha="left", va="center", fontsize=8, color="#e0e0e8")

    ax.set_xlabel("Mean |SHAP|", color="#787890", fontsize=9)
    ax.tick_params(colors="#e0e0e8", labelsize=8)
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.spines["bottom"].set_color("#252535")
    ax.spines["left"].set_color("#252535")

    plt.tight_layout()
    buf = io.BytesIO()
    plt.savefig(buf, format="png", dpi=120, facecolor="#13131a", bbox_inches="tight")
    plt.close()
    return base64.b64encode(buf.getvalue()).decode()


def _escape(text: str) -> str:
    if not text:
        return ""
    return (text.replace("&", "&amp;").replace("<", "&lt;")
            .replace(">", "&gt;").replace('"', "&quot;"))
