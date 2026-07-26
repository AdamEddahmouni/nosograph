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

from med_research.templates import env


def generate_ml_report(results: dict) -> str:
    """Generate an HTML report from ML prediction results."""
    output_path = Path(__file__).parent / "ml_report.html"

    metrics = results.get("model_metrics", {})
    top = results.get("top_untargeted", [])
    importance = results.get("feature_importance", {})
    shap = results.get("shap_summary", [])

    importance_chart = _generate_importance_chart(importance) if MPL_AVAILABLE else ""
    shap_chart = _generate_shap_chart(shap) if MPL_AVAILABLE and shap else ""

    top_display = []
    for p in top:
        or_val = p.get("odds_ratio", "")
        or_display = f"{or_val:.1f}" if or_val else "\u2014"
        top_display.append(
            {
                "gene_name": p["gene_name"],
                "category": p.get("category", ""),
                "druggability_score": p["druggability_score"],
                "odds_ratio_display": or_display,
                "degree": p.get("degree", 0),
            }
        )

    feat_display = []
    for feat, imp in list(importance.items())[:15]:
        feat_display.append({"name": feat, "importance": imp})

    context = {
        "generated_at": datetime.now().strftime("%B %d, %Y at %H:%M"),
        "n_genes": metrics.get("n_genes", 0),
        "n_targeted": metrics.get("n_targeted", 0),
        "n_untargeted": metrics.get("n_untargeted", 0),
        "cv_roc_auc": metrics.get("cv_roc_auc_mean", 0),
        "n_features": len(importance),
        "top_predictions": top_display,
        "feature_importance": feat_display,
        "importance_chart": importance_chart,
        "shap_chart": shap_chart,
    }

    template = env.get_template("reports/ml_predictor.html")
    html = template.render(**context)

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
    colors = (
        plt.cm.viridis(np.linspace(0.2, 0.9, len(labels)))
        if np
        else ["#818cf8"] * len(labels)
    )

    bars = ax.barh(
        labels[::-1],
        values[::-1],
        color=colors[::-1],
        edgecolor="#252535",
        linewidth=0.5,
        height=0.6,
    )
    for bar, val in zip(bars, values[::-1]):
        ax.text(
            bar.get_width() + 0.002,
            bar.get_y() + bar.get_height() / 2,
            f"{val:.4f}",
            ha="left",
            va="center",
            fontsize=8,
            color="#e0e0e8",
        )

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
    labels = [
        i["feature"].replace("cat_", "").replace("_", " ")[:30] for i in items
    ]
    values = [i["mean_abs_shap"] for i in items]
    colors = (
        plt.cm.plasma(np.linspace(0.2, 0.9, len(labels)))
        if np
        else ["#f472b6"] * len(labels)
    )

    bars = ax.barh(
        labels[::-1],
        values[::-1],
        color=colors[::-1],
        edgecolor="#252535",
        linewidth=0.5,
        height=0.6,
    )
    for bar, val in zip(bars, values[::-1]):
        ax.text(
            bar.get_width() + 0.0005,
            bar.get_y() + bar.get_height() / 2,
            f"{val:.4f}",
            ha="left",
            va="center",
            fontsize=8,
            color="#e0e0e8",
        )

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
