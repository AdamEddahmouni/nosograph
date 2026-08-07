"""Gene Expression Correlation HTML Report Generator."""

import json
from datetime import datetime
from pathlib import Path

from med_research.pipeline.reporting import (
    apply_disease_labels,
    disease_context,
    provenance_footer_html,
)
from med_research.templates import env as template_env


def escape_html(value):
    """Escape HTML special characters."""
    if value is None:
        return ""
    return str(value).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;")


def generate_html_report(
    results: list,
    signature_source: str = "curated_literature",
    num_studies: int = 0,
    tissue: str = "",
    disease_id: str = "sle",
    *,
    provenance: dict | None = None,
) -> str:
    """Generate an HTML report for gene expression correlation results.

    Args:
        results: List of scored drug dicts from correlator.py.
        signature_source: Source label of the expression signature used.
        num_studies: Number of GEO studies used (0 for curated).
        tissue: Tissue category filter used.

    Returns:
        Path to the generated HTML file.
    """
    now = datetime.now().strftime("%B %d, %Y at %H:%M")
    scored = sorted(results, key=lambda x: x["composite_score"], reverse=True)
    n = len(scored)

    # Stats
    scores = [r["composite_score"] for r in scored]
    avg_score = sum(scores) / len(scores) if scores else 0
    tier1 = sum(1 for r in scored if r["composite_score"] >= 7.5)
    tier2 = sum(1 for r in scored if 6.0 <= r["composite_score"] < 7.5)
    tier3 = sum(1 for r in scored if 4.5 <= r["composite_score"] < 6.0)

    # Build top-5 JSON for radar chart
    top5_items = []
    for r in scored[:5]:
        name = r['drug_name'].split('(')[0].strip()[:25]
        top5_items.append({
            "name": name,
            "scores": [
                r.get('signature_reversal', 0),
                r.get('target_disease_overlap', 0),
                r.get('cell_type_specificity', 0),
                r.get('expression_evidence', 0),
                r.get('directionality', 0),
            ],
        })
    top5_json = json.dumps(top5_items)

    # Build highlights grid (top 8 safest/most correlated)
    highlights_rows = ""
    for i, r in enumerate(scored[:8], 1):
        highlights_rows += f"""
            <div class="highlight-card">
                <div class="highlight-rank">#{i}</div>
                <div class="highlight-drug">{escape_html(r['drug_name'])}</div>
                <div class="highlight-score" style="color: #4ade80;">{r['composite_score']:.1f}</div>
                <div class="highlight-meta">{escape_html(r.get('category', ''))}</div>
            </div>"""

    # Build ranked table
    table_rows = ""
    for i, r in enumerate(scored, 1):
        tier_icon = r["tier"].split("—")[0].strip()
        tier_color = {"🔴": "#f87171", "🟠": "#fb923c", "🟡": "#fbbf24", "🟢": "#4ade80"}.get(
            tier_icon[0] if tier_icon else "", "#9ca3af")
        table_rows += f"""
            <tr>
                <td class="col-rank">{i}</td>
                <td class="col-drug">{escape_html(r['drug_name'])}</td>
                <td class="col-score" style="color:{tier_color}">{r['composite_score']:.2f}</td>
                <td class="col-sign">{r.get('signature_reversal', '-')}</td>
                <td class="col-overlap">{r.get('target_disease_overlap', '-')}</td>
                <td class="col-cell">{r.get('cell_type_specificity', '-')}</td>
                <td class="col-evid">{r.get('expression_evidence', '-')}</td>
                <td class="col-dir">{r.get('directionality', '-')}</td>
                <td class="col-tier" style="color:{tier_color}">{r['tier']}</td>
            </tr>"""

    html = template_env.get_template("reports/gene_expression.html").render(
        ctx_0=now,
        ctx_1=n,
        ctx_2=avg_score,
        ctx_3=tier1,
        ctx_4=tier2,
        ctx_5=tier3,
        ctx_6=signature_source,
        ctx_7=num_studies,
        ctx_8=tissue or 'broad / multi-tissue',
        ctx_9=highlights_rows,
        ctx_10=table_rows,
        ctx_11=top5_json,
        ctx_disease=disease_context(disease_id)["name"],
        ctx_disease_id=disease_id,
    )
    html = apply_disease_labels(html, disease_id)
    footer = provenance_footer_html(provenance)
    if footer:
        html = html.replace("</body>", f"{footer}\n</body>", 1)

    report_path = Path(__file__).parent / "report.html"
    report_path.write_text(html, encoding="utf-8")
    return str(report_path)
