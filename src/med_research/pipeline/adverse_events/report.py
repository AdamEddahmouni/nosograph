"""
Adverse Event Profiling Report Generator

Generates a standalone HTML report with:
  - Safety score distribution and heatmap
  - Ranked drug safety table
  - Per-drug adverse event profiles
  - Black box warning summary

Rendered via the shared Jinja2 template infrastructure (templates/reports/).
"""

from datetime import datetime
from pathlib import Path

from med_research.pipeline.reporting import disease_context, render_report


def generate_html_report(
    safety_results: list, disease_id: str = "sle", *, provenance: dict | None = None
) -> str:
    """Generate a standalone HTML report for the active disease.

    Empty or blocked result sets are not rendered as successful reports.
    """
    if not safety_results:
        raise ValueError("Cannot generate a safety report without scored results")

    output_path = Path(__file__).parent / "report.html"
    context = disease_context(disease_id)

    if safety_results and safety_results[0].get("status") == "blocked":
        raise ValueError("Cannot generate a safety report for a blocked analysis")

    n_bbw = sum(1 for r in safety_results if r.get("black_box_warnings"))
    n_disease_risk = sum(1 for r in safety_results if r["disease_specific_risk_score"] < 10.0)
    avg = sum(r["composite_safety_score"] for r in safety_results) / len(safety_results) if safety_results else 0
    metadata = safety_results[0] if safety_results else {}

    # Top-10 safety highlights
    highlight_html = ""
    for i, r in enumerate(safety_results[:10], 1):
        score = r["composite_safety_score"]
        color = "#4ade80" if score >= 7 else "#fbbf24" if score >= 5 else "#f87171"
        highlight_html += f"""        <div class="highlight-card">
            <div class="hl-rank">#{i}</div>
            <div class="hl-drug">{escape_html(r['drug_name'])}</div>
            <div class="hl-score" style="color:{color};">{score:.1f}</div>
            <div class="hl-dims">
                <span class="hl-dim">Disease Overlap: {r['disease_symptom_overlap_score']}</span>
                <span class="hl-dim">Severity: {r['severity_burden_score']}</span>
                <span class="hl-dim">Chronic: {r['chronic_use_safety_score']}</span>
                <span class="hl-dim">Disease Risk: {r['disease_specific_risk_score']}</span>
            </div>
        </div>"""

    # Full table
    rows_html = ""
    for i, r in enumerate(safety_results, 1):
        score = r["composite_safety_score"]
        color = "#4ade80" if score >= 7 else "#fbbf24" if score >= 5 else "#f87171"
        bbw = r.get("black_box_warnings", [])
        bbw_badge = f"<span class='bbw-badge'>BBW: {len(bbw)}</span>" if bbw else ""
        rows_html += f"""        <tr>
            <td class="rank">{i}</td>
            <td><strong>{escape_html(r['drug_name'])}</strong></td>
            <td><span style="color:{color};font-weight:700;font-size:1.1em;">{score:.1f}</span></td>
            <td>{r['disease_symptom_overlap_score']}/10</td>
            <td>{r['severity_burden_score']}/10</td>
            <td>{r['chronic_use_safety_score']}/10</td>
            <td>{r['disease_specific_risk_score']}/10</td>
            <td>{r['n_disease_overlap_ae']}</td>
            <td>{bbw_badge}</td>
        </tr>"""

    html = render_report(
        "reports/adverse_events.html",
        {
            "ctx_0": len(safety_results),
            "ctx_disease": context["name"],
            "ctx_disease_id": context["id"],
            "ctx_1": datetime.now().strftime("%B %d, %Y at %H:%M"),
            "ctx_2": avg,
            "ctx_3": n_bbw,
            "ctx_4": n_disease_risk,
            "ctx_5": highlight_html,
            "ctx_6": rows_html,
            "ctx_profile_source": metadata.get("profile_source", ""),
            "ctx_limitations": metadata.get("limitations", []),
        },
        disease_id,
        provenance=provenance,
    )

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
