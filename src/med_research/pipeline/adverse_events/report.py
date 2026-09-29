"""
Adverse Event Profiling Report Generator

Generates a standalone HTML report with:
  - Safety score distribution and heatmap
  - Ranked drug safety table
  - Per-drug adverse event profiles
  - Black box warning summary

Rendered via the shared Jinja2 template infrastructure (templates/reports/).
"""

from collections.abc import Mapping
from datetime import datetime
from pathlib import Path
from typing import Any

from med_research.pipeline.provenance import ProvenanceMetadata
from med_research.pipeline.reporting import disease_context, render_report, report_output_dir


def generate_html_report(
    safety_results: list,
    disease_id: str = "sle",
    *,
    provenance: ProvenanceMetadata | Mapping[str, Any] | None = None,
) -> str:
    """Generate a standalone HTML report for the active disease.

    Empty or blocked result sets are not rendered as successful reports.
    """
    if not safety_results:
        raise ValueError("Cannot generate a safety report without results")

    if safety_results[0].get("status") == "blocked":
        raise ValueError("Cannot generate a safety report for a blocked analysis")

    scored_results = sorted(
        (
            result
            for result in safety_results
            if result.get("score_status", "scored") == "scored"
            and result.get("composite_safety_score") is not None
        ),
        key=lambda result: float(result["composite_safety_score"]),
        reverse=True,
    )
    unscored_results = [
        result
        for result in safety_results
        if result.get("score_status", "scored") != "scored"
        or result.get("composite_safety_score") is None
    ]
    unscored_count = len(unscored_results)
    n_bbw = sum(1 for result in safety_results if result.get("black_box_warnings"))
    n_disease_risk = sum(
        1
        for result in scored_results
        if result.get("disease_specific_risk_score") is not None
        and result["disease_specific_risk_score"] < 10.0
    )
    avg = (
        sum(result["composite_safety_score"] for result in scored_results) / len(scored_results)
        if scored_results
        else None
    )
    metadata = safety_results[0]

    # Top-10 safety highlights include only numerically scored drugs.
    highlight_html = ""
    for index, result in enumerate(scored_results[:10], 1):
        score = result["composite_safety_score"]
        color = "#4ade80" if score >= 7 else "#fbbf24" if score >= 5 else "#f87171"
        highlight_html += f"""        <div class="highlight-card">
            <div class="hl-rank">#{index}</div>
            <div class="hl-drug">{escape_html(result["drug_name"])}</div>
            <div class="hl-score" style="color:{color};">{score:.1f}</div>
            <div class="hl-dims">
                <span class="hl-dim">Disease Overlap: {result["disease_symptom_overlap_score"]}</span>
                <span class="hl-dim">Severity: {result["severity_burden_score"]}</span>
                <span class="hl-dim">Chronic: {result["chronic_use_safety_score"]}</span>
                <span class="hl-dim">Disease Risk: {result["disease_specific_risk_score"]}</span>
            </div>
        </div>"""

    # Keep every drug visible; rank and score only records with numeric results.
    rows_html = ""
    scored_rank = 0
    for result in [*scored_results, *unscored_results]:
        scored = (
            result.get("score_status", "scored") == "scored"
            and result.get("composite_safety_score") is not None
        )
        if scored:
            scored_rank += 1
        if scored:
            score = result["composite_safety_score"]
            color = "#4ade80" if score >= 7 else "#fbbf24" if score >= 5 else "#f87171"
            score_cell = (
                f'<span style="color:{color};font-weight:700;font-size:1.1em;">{score:.1f}</span>'
            )
            dimension_cells = "".join(
                f"<td>{result[field]}/10</td>"
                for field in (
                    "disease_symptom_overlap_score",
                    "severity_burden_score",
                    "chronic_use_safety_score",
                    "disease_specific_risk_score",
                )
            )
            overlap_count = result.get("n_disease_overlap_ae", 0)
        else:
            score_cell = '<span class="insufficient-evidence">Insufficient evidence.</span>'
            dimension_cells = (
                '<td colspan="4" class="insufficient-evidence">Insufficient evidence.</td>'
            )
            overlap_count = "—"
        warnings = result.get("black_box_warnings", [])
        warning_badge = f"<span class='bbw-badge'>BBW: {len(warnings)}</span>" if warnings else ""
        rank = scored_rank if scored else "—"
        rows_html += f"""        <tr>
            <td class="rank">{rank}</td>
            <td><strong>{escape_html(result["drug_name"])}</strong></td>
            <td>{score_cell}</td>
            {dimension_cells}
            <td>{overlap_count}</td>
            <td>{warning_badge}</td>
        </tr>"""

    context = disease_context(disease_id)
    output_path = report_output_dir(Path(__file__).parent) / "report.html"
    html = render_report(
        "reports/adverse_events.html",
        {
            "ctx_0": len(safety_results),
            "ctx_scored": len(scored_results),
            "ctx_unscored": unscored_count,
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

    with open(output_path, "w", encoding="utf-8") as output_file:
        output_file.write(html)

    return str(output_path)


def escape_html(text: str) -> str:
    """Escape HTML special characters."""
    if not text:
        return ""
    return (
        text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;")
    )
