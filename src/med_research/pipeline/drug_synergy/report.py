"""
Drug Combination Synergy Report Generator

Generates a beautiful standalone HTML report with:
  - Executive summary and tier statistics
  - Ranked synergistic drug pairs table
  - Score breakdowns for each dimension
  - Top combinations highlighting
"""

from datetime import datetime
from pathlib import Path

from med_research.pipeline.reporting import apply_disease_labels
from med_research.templates import env as template_env


def generate_html_report(scored_pairs: list, disease_id: str = "sle") -> str:
    """Generate a standalone HTML report and return the path."""

    output_path = Path(__file__).parent / "report.html"

    # Summary stats
    n_tier1 = sum(1 for p in scored_pairs if p["composite_score"] >= 8.0)
    n_tier2 = sum(1 for p in scored_pairs if 7.0 <= p["composite_score"] < 8.0)
    n_tier3 = sum(1 for p in scored_pairs if 6.0 <= p["composite_score"] < 7.0)
    avg_score = (
        sum(p["composite_score"] for p in scored_pairs) / len(scored_pairs)
        if scored_pairs else 0
    )

    # Build rows for top 40 pairs
    rows_html = ""

    # Build top-5 JSON for radar chart
    import json
    top5_items = []
    for p in scored_pairs[:5]:
        name = p['drug_a_name'].split('(')[0].strip()[:15] + ' + ' + p['drug_b_name'].split('(')[0].strip()[:15]
        top5_items.append({
            "name": name,
            "scores": [
                p['target_complementarity'],
                p['pathway_diversity'],
                p['mechanism_orthogonality'],
                p['safety_non_overlap'],
                p['combined_evidence'],
            ],
        })
    top5_json = json.dumps(top5_items)

    # Build rows for top 40 pairs (continued)
    for i, p in enumerate(scored_pairs[:40], 1):
        tier_color = {
            "\U0001f534 Tier 1 \u2014 Strong Synergy Potential": "#dc2626",
            "\U0001f7e0 Tier 2 \u2014 Promising Synergy": "#ea580c",
            "\U0001f7e1 Tier 3 \u2014 Possible Synergy": "#ca8a04",
            "\U0001f7e2 Tier 4 \u2014 Limited Synergy": "#16a34a",
        }.get(p["tier"], "#6b7280")

        score = p["composite_score"]
        score_color = (
            "#4ade80" if score >= 8 else "#fbbf24" if score >= 7 else "#f87171" if score < 6 else "#fb923c"
        )

        tier_display = p['tier'].split('\u2014')[0].strip()

        rows_html += f"""        <tr>
            <td class="rank">{i}</td>
            <td>
                <span class="tier-badge" style="background:{tier_color}20;color:{tier_color};border:1px solid {tier_color}40">
                    {tier_display}
                </span>
            </td>
            <td><strong>{escape_html(p['drug_a_name'])}</strong></td>
            <td><strong>{escape_html(p['drug_b_name'])}</strong></td>
            <td><span class="score" style="color:{score_color};font-weight:700;font-size:1.2em;">{score:.1f}</span></td>
            <td class="score-breakdown">
                <span title="Target Complementarity">\U0001f3af{p['target_complementarity']}</span>
                <span title="Pathway Diversity">\U0001f6e4\ufe0f{p['pathway_diversity']}</span>
                <span title="Mechanism Orthogonality">\u2699\ufe0f{p['mechanism_orthogonality']}</span>
                <span title="Safety Non-overlap">\U0001f6e1\ufe0f{p['safety_non_overlap']}</span>
                <span title="Combined Evidence">\U0001f4cb{p['combined_evidence']}</span>
            </td>
            <td class="muted">{escape_html(p.get('drug_a_category', ''))} + {escape_html(p.get('drug_b_category', ''))}</td>
        </tr>"""

    # Top-10 highlight cards
    highlight_html = ""
    for i, p in enumerate(scored_pairs[:10], 1):
        score = p["composite_score"]
        score_color = "#4ade80" if score >= 8 else "#fbbf24" if score >= 7 else "#f87171"
        highlight_html += f"""        <div class="highlight-card">
            <div class="hl-rank">#{i}</div>
            <div class="hl-body">
                <div class="hl-drugs">
                    <span class="hl-drug-a">{escape_html(p['drug_a_name'])}</span>
                    <span class="hl-plus">+</span>
                    <span class="hl-drug-b">{escape_html(p['drug_b_name'])}</span>
                </div>
                <div class="hl-score" style="color:{score_color};">{p['composite_score']:.1f}</div>
            </div>
            <div class="hl-dims">
                <div class="hl-dim"><span>\U0001f3af Target</span><span>{p['target_complementarity']}</span></div>
                <div class="hl-dim"><span>\U0001f6e4\ufe0f Pathway</span><span>{p['pathway_diversity']}</span></div>
                <div class="hl-dim"><span>\u2699\ufe0f Mech</span><span>{p['mechanism_orthogonality']}</span></div>
                <div class="hl-dim"><span>\U0001f6e1\ufe0f Safety</span><span>{p['safety_non_overlap']}</span></div>
                <div class="hl-dim"><span>\U0001f4cb Evidence</span><span>{p['combined_evidence']}</span></div>
            </div>
        </div>"""

    html = template_env.get_template("reports/drug_synergy.html").render(
        ctx_0=len(scored_pairs),
        ctx_1=datetime.now().strftime('%B %d, %Y at %H:%M'),
        ctx_2=n_tier1,
        ctx_3=n_tier2,
        ctx_4=n_tier3,
        ctx_5=avg_score,
        ctx_6=highlight_html,
        ctx_7=rows_html,
        ctx_8=top5_json,
    )
    html = apply_disease_labels(html, disease_id)

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
