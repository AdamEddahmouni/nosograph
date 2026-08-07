"""
Lupus Drug Repurposing Report Generator

Generates a beautiful standalone HTML report with:
  - Executive summary and statistics
  - Priority-ranked repurposing candidates table
  - Per-gene analysis cards
  - Clinical trial status indicators
  - Interactive score breakdowns
"""

from datetime import datetime
from pathlib import Path

from med_research.pipeline.reporting import (
    apply_disease_labels,
    disease_context,
    provenance_footer_html,
)


def generate_html_report(
    scored_candidates: list,
    untargeted_genes: list,
    genes: dict,
    G,
    disease_id: str = "sle",
    *,
    provenance: dict | None = None,
) -> str:
    """Generate a standalone report for the requested disease."""

    output_path = Path(__file__).parent / "report.html"
    context = disease_context(disease_id)

    # Build gene->candidates mapping
    gene_candidates = {}
    for c in scored_candidates:
        gene_candidates.setdefault(c["gene_id"], []).append(c)

    # Sort genes by best candidate score
    gene_rankings = []
    for gene in untargeted_genes:
        gid = gene["id"]
        cands = gene_candidates.get(gid, [])
        best = max(c["composite_score"] for c in cands) if cands else 0
        gene_rankings.append({"gene": gene, "candidates": cands, "best_score": best, "count": len(cands)})
    gene_rankings.sort(key=lambda x: x["best_score"], reverse=True)

    # Build top-5 JSON for radar chart
    import json
    top5_items = []
    for c in scored_candidates[:5]:
        name = c['drug_name'].split('(')[0].strip()[:25]
        top5_items.append({
            "name": name,
            "scores": [
                c.get('target_similarity_score', 5),
                c.get('final_proximity', 5),
                c.get('mechanistic_rationale_score', 5),
                c.get('clinical_evidence_score', 5),
                c.get('adverse_event_score', c.get('safety_score', 5)),
                c.get('novelty_score', 5) * 2,  # Scale 0-5 to 0-10 for chart
            ],
        })
    top5_json = json.dumps(top5_items)

    # Build candidate rows
    rows_html = ""
    for i, c in enumerate(scored_candidates[:25], 1):
        tier_color = {
            "🔴 Tier 1 — Highest Priority": "#dc2626",
            "🟠 Tier 2 — High Priority": "#ea580c",
            "🟡 Tier 3 — Medium Priority": "#ca8a04",
            "🟢 Tier 4 — Lower Priority": "#16a34a",
        }.get(c["tier"], "#6b7280")

        score = c["composite_score"]
        score_color = (
            "#4ade80" if score >= 8 else "#fbbf24" if score >= 7 else "#f87171" if score < 6 else "#fb923c"
        )

        rows_html += f"""
        <tr>
            <td class="rank">{i}</td>
            <td>
                <span class="tier-badge" style="background:{tier_color}20;color:{tier_color};border:1px solid {tier_color}40">
                    {c['tier'].split('—')[0].strip()}
                </span>
            </td>
            <td><strong>{escape_html(c['drug_name'])}</strong><br><span class="muted">{c['drug_category']}</span></td>
            <td><span class="gene-tag">{c['gene_name']}</span><br><span class="muted">{c['gene_category']}</span></td>
            <td><span class="score" style="color:{score_color};font-weight:700;font-size:1.2em;">{score:.1f}</span></td>
            <td class="score-breakdown">
                <span title="Target Similarity">🎯{c['target_similarity_score']}</span>
                <span title="Pathway Proximity">🛤️{c['final_proximity']:.0f}</span>
                <span title="Mechanistic Rationale">🧬{c['mechanistic_rationale_score']}</span>
                <span title="Clinical Evidence">📋{c['clinical_evidence_score']}</span>
                <span title="Adverse Event Profile">🛡️{c.get('adverse_event_score', c.get('safety_score', 'N/A'))}</span>
            </td>
            <td>{c['evidence_level']}</td>
            <td><span class="status-tag">{c['status']}</span></td>
        </tr>"""

    # Build gene cards
    gene_cards_html = ""

    for gr in gene_rankings:
        gene = gr["gene"]
        cands = gr["candidates"]
        gid = gene["id"]

        cand_html = ""
        for c in cands:
            cand_html += f"""
            <div class="gene-candidate">
                <div class="gc-header">
                    <span class="gc-drug">{escape_html(c['drug_name'])}</span>
                    <span class="gc-score" style="color: {'#4ade80' if c['composite_score'] >= 8 else '#fbbf24' if c['composite_score'] >= 7 else '#f87171'}">{c['composite_score']:.1f}</span>
                </div>
                <div class="gc-mechanism">{escape_html(c['mechanism'][:200])}</div>
                <div class="gc-rationale">{escape_html(c['rationale'][:250])}</div>
                <div class="gc-meta">
                    <span>📋 {c['evidence_level']}</span>
                    <span>🚦 {c['status']}</span>
                </div>
            </div>"""

        gene_cards_html += f"""
        <div class="gene-card" id="gene-{gid}">
            <div class="gene-card-header">
                <div>
                    <h3>{escape_html(gene['name'])} <code>{gid}</code></h3>
                    <span class="gene-category">{escape_html(gene.get('category', ''))}</span>
                </div>
                <div class="gene-card-score">
                    <span class="best-label">Best</span>
                    <span class="best-value">{gr['best_score']:.1f}</span>
                </div>
            </div>
            <div class="gene-card-body">
                <p class="gene-function"><strong>Function:</strong> {escape_html(gene.get('function', ''))}</p>
                <p class="gene-evidence"><strong>{escape_html(context["name"])} Evidence:</strong> {escape_html(gene.get('disease_evidence') or gene.get('lupus_evidence', ''))}</p>
                <p class="gene-odds"><strong>Odds Ratio:</strong> {gene.get('odds_ratio', 'N/A')} | <strong>Chr:</strong> {gene.get('chromosome', 'N/A')}</p>
            </div>
            <div class="gene-card-candidates">
                <h4>{len(cands)} Repurposing Candidate{'s' if len(cands) != 1 else ''}</h4>
                {cand_html}
            </div>
        </div>"""

    # Summary stats
    n_tier1 = sum(1 for c in scored_candidates if c["composite_score"] >= 8.0)
    n_tier2 = sum(1 for c in scored_candidates if 7.0 <= c["composite_score"] < 8.0)
    avg_score = sum(c["composite_score"] for c in scored_candidates) / len(scored_candidates) if scored_candidates else 0

    # ── Build template context ─────────────────────────────────────────
    from med_research.templates import env as template_env

    def _tier_name(c):
        """Extract 'Tier N' from full tier label like '🔴 Tier 1 — Highest Priority'."""
        tier = c.get("tier", "")
        if "—" in tier:
            return tier.split("—")[0].strip().split()[-2] + " " + tier.split("—")[0].strip().split()[-1]
        return tier

    def _adapter(c):
        return {
            **c,
            "tier_name": _tier_name(c),
            "safety_indicator": c.get("adverse_event_score", c.get("safety_score", "N/A")),
        }

    adapted_candidates = [_adapter(c) for c in scored_candidates[:25]]
    adapted_gene_rankings = [
        {
            "gene": gr["gene"],
            "candidates": [_adapter(c) for c in gr["candidates"]],
            "best_score": gr["best_score"],
        }
        for gr in gene_rankings
    ]

    html = template_env.get_template("reports/repurposing.html").render(
        ctx_disease=context["name"],
        ctx_disease_id=context["id"],
        n_candidates=len(scored_candidates),
        n_genes=len(untargeted_genes),
        n_tier1=n_tier1,
        n_tier2=n_tier2,
        avg_score=avg_score,
        top5_json=top5_json,
        candidates=adapted_candidates,
        gene_rankings=adapted_gene_rankings,
        generated_at=datetime.now().strftime("%B %d, %Y at %H:%M"),
        disease_id=context["name"],
    )
    html = apply_disease_labels(html, disease_id)
    footer = provenance_footer_html(provenance)
    if footer:
        html = html.replace("</body>", f"{footer}\n</body>", 1)

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
