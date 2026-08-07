"""
Cross-Disease Drug Repurposing Report Generator — Phase 22

Generates a standalone HTML report with:
  - Disease similarity matrix
  - Shared genes/drugs/pathways analysis
  - Multi-disease drug candidates table
  - Cross-disease repurposing recommendations
  - Interactive radar chart
"""

import json
from datetime import datetime
from pathlib import Path

from med_research.templates import env as template_env


def generate_html_report(results: dict) -> str:
    """Generate a standalone HTML report and return the path."""

    output_path = Path(__file__).parent / "report.html"

    d_summary = results["disease_summary"]
    disease_ids = sorted(d_summary.keys())
    n_diseases = results["total_diseases"]

    # Summary stats
    n_shared_genes = len(results["shared_genes"]["shared_genes"])
    n_shared_drugs = len(results["shared_drugs"]["shared_drugs"])
    n_shared_pathways = len(results["shared_pathways"]["shared_pathways"])
    mdd = results["multi_disease_drugs"]
    n_tier1 = sum(1 for d in mdd if d["composite_score"] >= 7.5)
    n_tier2 = sum(1 for d in mdd if 6.0 <= d["composite_score"] < 7.5)

    avg_score = sum(d["composite_score"] for d in mdd) / len(mdd) if mdd else 0

    # Top-5 JSON for radar chart
    top5 = mdd[:5]
    colors = ["#818cf8", "#4ade80", "#f59e0b", "#f472b6", "#34d399"]
    top5_json_data = []
    for i, d in enumerate(top5):
        name = d["drug_name"].split("(")[0].strip()[:30]
        top5_json_data.append({
            "name": name,
            "scores": [
                d["disease_coverage"],
                d["target_centrality"],
                d["pathway_breadth"],
                d["mechanistic_transferability"],
                d["novelty"],
            ],
        })
    top5_json = json.dumps(top5_json_data)

    # Build drug rows
    drug_rows_html = ""
    for i, d in enumerate(mdd[:25], 1):
        tier_color = {
            "Tier 1 — Strong Multi-Disease Candidate": "#dc2626",
            "Tier 2 — Promising Cross-Disease Candidate": "#ea580c",
            "Tier 3 — Moderate Cross-Disease Potential": "#ca8a04",
            "Tier 4 — Disease-Specific": "#16a34a",
        }.get(d["tier"], "#6b7280")

        score = d["composite_score"]
        score_color = (
            "#4ade80" if score >= 7.5 else "#fbbf24" if score >= 6.0 else "#f87171" if score < 4.5 else "#fb923c"
        )

        drug_rows_html += f"""
        <tr>
            <td class="rank">{i}</td>
            <td>
                <span class="tier-badge" style="background:{tier_color}20;color:{tier_color};border:1px solid {tier_color}40">
                    {d['tier'].split('—')[0].strip()}
                </span>
            </td>
            <td><strong>{escape_html(d['drug_name'])}</strong></td>
            <td>{d['disease_count']}</td>
            <td><span class="score" style="color:{score_color};font-weight:700;font-size:1.2em;">{score:.1f}</span></td>
            <td class="score-breakdown">
                <span title="Disease Coverage">🌐{d['disease_coverage']:.0f}</span>
                <span title="Target Centrality">🎯{d['target_centrality']:.0f}</span>
                <span title="Pathway Breadth">🛤️{d['pathway_breadth']:.0f}</span>
                <span title="Mechanistic Transferability">🔄{d['mechanistic_transferability']:.0f}</span>
                <span title="Novelty">💡{d['novelty']:.0f}</span>
            </td>
        </tr>"""

    # Build similarity rows
    sim_rows_html = ""
    for pair in results["disease_similarity"][:21]:
        sim_color = (
            "#4ade80" if pair["overall_similarity"] >= 0.3
            else "#fbbf24" if pair["overall_similarity"] >= 0.15
            else "#f87171"
        )
        sim_rows_html += f"""
        <tr>
            <td>{pair['name_a']}</td>
            <td>{pair['name_b']}</td>
            <td><span style="color:{sim_color};font-weight:700;">{pair['overall_similarity']:.3f}</span></td>
            <td>{pair['gene_similarity']:.3f}</td>
            <td>{pair['drug_similarity']:.3f}</td>
            <td>{pair['pathway_similarity']:.3f}</td>
            <td>{pair['shared_gene_count']}</td>
            <td>{pair['shared_drug_count']}</td>
        </tr>"""

    # Build shared gene rows
    sg_rows = ""
    for g in results["shared_genes"]["shared_genes"][:20]:
        sg_rows += f"""
        <tr>
            <td><strong>{escape_html(g['gene_id'])}</strong></td>
            <td class="muted">{escape_html(g['name'][:60])}</td>
            <td><span class="gene-tag">{g['disease_count']}</span></td>
            <td class="muted">{', '.join(g['diseases'])}</td>
        </tr>"""

    # Build shared drug rows
    sd_rows = ""
    for d in results["shared_drugs"]["shared_drugs"][:20]:
        sd_rows += f"""
        <tr>
            <td><strong>{escape_html(d['drug_id'])}</strong></td>
            <td class="muted">{escape_html(d['name'][:60])}</td>
            <td><span class="gene-tag">{d['disease_count']}</span></td>
            <td class="muted">{', '.join(d['diseases'])}</td>
        </tr>"""

    # Build repurposing rows
    rep_rows = ""
    novel_recs = [r for r in results["cross_disease_repurposing"] if not r["already_used_in_target"]][:15]
    for i, r in enumerate(novel_recs, 1):
        rep_rows += f"""
        <tr>
            <td class="rank">{i}</td>
            <td><strong>{escape_html(r['drug_name'][:50])}</strong></td>
            <td>{r['source_disease_name']} → {r['target_disease_name']}</td>
            <td><span class="gene-tag">{escape_html(r['drug_target'])}</span></td>
            <td><span class="gene-tag">{', '.join(r['matched_genes'])}</span></td>
            <td><span style="font-weight:700;color:#4ade80;">{r['confidence']:.0f}/10</span></td>
        </tr>"""

    # Disease summary cards
    disease_cards_html = ""
    emoji_map = {"sle": "🦋", "ra": "🦴", "ms": "🧠", "ss": "💧",
                 "ssc": "🖐️", "t1d": "🩸", "ibd": "🫃"}
    for did in disease_ids:
        info = d_summary[did]
        emoji = emoji_map.get(did, "🔬")
        disease_cards_html += f"""
        <div class="stat-card">
            <div style="font-size:1.5rem;margin-bottom:4px;">{emoji}</div>
            <div class="stat-value" style="font-size:1rem;color:#818cf8;">{info['name']}</div>
            <div class="stat-label">
                {info['gene_count']} genes · {info['drug_count']} drugs · {info['pathway_count']} pathways
            </div>
        </div>"""

    html = template_env.get_template("reports/cross_disease.html").render(
        ctx_0=n_diseases,
        ctx_1=datetime.now().strftime('%B %d, %Y at %H:%M'),
        ctx_2=len(mdd),
        ctx_3=disease_cards_html,
        ctx_4=n_shared_genes,
        ctx_5=n_shared_drugs,
        ctx_6=n_shared_pathways,
        ctx_7=n_tier1,
        ctx_8=n_tier2,
        ctx_9=avg_score,
        ctx_10=sim_rows_html,
        ctx_11=drug_rows_html,
        ctx_12=sg_rows,
        ctx_13=sd_rows,
        ctx_14=rep_rows,
        ctx_15=top5_json,
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
