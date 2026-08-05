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

from med_research.templates import env as template_env

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

    # ── Build template context ─────────────────────────────────────────
    def _or_display(p):
        or_val = p.get("odds_ratio")
        return f"{or_val:.1f}" if or_val else "—"

    top_predictions = [
        {
            "gene_name": p.get("gene_name", ""),
            "gene_id": p.get("gene_id", ""),
            "category": p.get("category", ""),
            "druggability_score": p.get("druggability_score", 0.0),
            "odds_ratio_display": _or_display(p),
            "degree": p.get("degree", 0),
        }
        for p in top
    ]
    feature_importance = [
        {"name": feat, "importance": imp}
        for feat, imp in list(importance.items())[:15]
    ]

    html = template_env.get_template("reports/ml_predictor.html").render(
        n_genes=metrics.get("n_genes", 0),
        n_targeted=metrics.get("n_targeted", 0),
        n_untargeted=metrics.get("n_untargeted", 0),
        cv_roc_auc=metrics.get("cv_roc_auc_mean", 0),
        top_predictions=top_predictions,
        n_features=len(importance),
        importance_chart=importance_chart,
        shap_chart=shap_chart,
        feature_importance=feature_importance,
        generated_at=datetime.now().strftime("%B %d, %Y at %H:%M"),
    )

    with open(output_path, "w", encoding="utf-8") as f:
        f.write(html)

    return str(output_path)

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
    """Private escape helper (kept for internal compatibility)."""
    return escape_html(text)


def escape_html(text) -> str:
    """Escape HTML special characters."""
    if not text:
        return ""
    return (
        str(text).replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )
