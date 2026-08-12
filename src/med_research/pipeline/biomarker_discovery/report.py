"""Biomarker Discovery HTML Report Generator."""

import json
from datetime import datetime
from pathlib import Path

from med_research.pipeline.reporting import disease_context, render_report


def escape_html(value):
    if value is None:
        return ""
    return (
        str(value)
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )


def generate_html_report(
    results: list, disease_id: str = "sle", *, provenance: dict | None = None
) -> str:
    """Generate integrated biomarker discovery report."""
    now = datetime.now().strftime("%B %d, %Y at %H:%M")
    context = disease_context(disease_id)
    scored = sorted(results, key=lambda x: x["composite_score"], reverse=True)
    n = len(scored)

    scores = [r["composite_score"] for r in scored]
    avg_score = sum(scores) / len(scores) if scores else 0
    tier1 = sum(1 for r in scored if r["composite_score"] >= 8.0)
    tier2 = sum(1 for r in scored if 6.5 <= r["composite_score"] < 8.0)
    tier3 = sum(1 for r in scored if 5.0 <= r["composite_score"] < 6.5)

    # Radar chart top-5
    top5_items = []
    for r in scored[:5]:
        top5_items.append(
            {
                "name": r.get("gene_name", "")[:25],
                "scores": [
                    r.get("cross_module_consistency", 0),
                    r.get("expression_predictiveness", 0),
                    r.get("cart_alignment", 0),
                    r.get("druggability", 0),
                    r.get("biomarker_novelty", 0),
                ],
            }
        )
    top5_json = json.dumps(top5_items)

    # Highlights
    highlights_rows = ""
    for i, r in enumerate(scored[:8], 1):
        highlights_rows += f"""
            <div class="highlight-card">
                <div class="highlight-rank">#{i}</div>
                <div class="highlight-drug">{escape_html(r.get("gene_name", ""))}</div>
                <div class="highlight-score" style="color: #a78bfa;">{r["composite_score"]:.1f}</div>
                <div class="highlight-meta">Best: {escape_html(r.get("best_modality", ""))}</div>
            </div>"""

    # Table
    table_rows = ""
    for i, r in enumerate(scored, 1):
        tier_icon = r["tier"].split("—")[0].strip()
        tier_color = {"🔴": "#f87171", "🟠": "#fb923c", "🟡": "#fbbf24", "🟢": "#4ade80"}.get(
            tier_icon[0] if tier_icon else "", "#9ca3af"
        )
        table_rows += f"""
            <tr>
                <td class="col-rank">{i}</td>
                <td class="col-drug">{escape_html(r.get("gene_name", ""))}</td>
                <td class="col-score" style="color:{tier_color}">{r["composite_score"]:.2f}</td>
                <td class="col-sign">{r.get("cross_module_consistency", "-")}</td>
                <td class="col-overlap">{r.get("expression_predictiveness", "-")}</td>
                <td class="col-cell">{r.get("cart_alignment", "-")}</td>
                <td class="col-evid">{r.get("druggability", "-")}</td>
                <td class="col-dir">{r.get("best_modality", "-")}</td>
                <td class="col-tier" style="color:{tier_color}">{r["tier"]}</td>
            </tr>"""

    html = render_report(
        "reports/biomarker_discovery.html",
        {
            "ctx_0": now,
            "ctx_1": n,
            "ctx_2": avg_score,
            "ctx_3": tier1,
            "ctx_4": tier2,
            "ctx_5": tier3,
            "ctx_6": highlights_rows,
            "ctx_7": table_rows,
            "ctx_8": top5_json,
            "ctx_disease": context["name"],
            "ctx_disease_id": context["id"],
        },
        disease_id,
        provenance=provenance,
    )

    report_path = Path(__file__).parent / "report.html"
    report_path.write_text(html, encoding="utf-8")
    return str(report_path)
