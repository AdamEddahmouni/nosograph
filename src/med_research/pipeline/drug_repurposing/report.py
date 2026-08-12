"""Disease-aware drug repurposing HTML report generator.

Generates a beautiful standalone HTML report with:
  - Executive summary and statistics
  - Priority-ranked repurposing candidates table
  - Per-gene analysis cards
  - Clinical trial status indicators
  - Interactive score breakdowns
"""

from datetime import datetime
from pathlib import Path
from typing import Any

from med_research.pipeline.reporting import disease_context, render_report


def generate_html_report(
    scored_candidates: list,
    untargeted_genes: list,
    genes: dict,
    G: Any,
    disease_id: str = "sle",
    *,
    provenance: dict | None = None,
) -> str:
    """Generate a standalone report for the requested disease."""

    output_path = Path(__file__).parent / "report.html"
    context = disease_context(disease_id)

    # Build gene->candidates mapping
    gene_candidates: dict[str, list[Any]] = {}
    for c in scored_candidates:
        gene_candidates.setdefault(c["gene_id"], []).append(c)

    # Sort genes by best candidate score
    gene_rankings = []
    for gene in untargeted_genes:
        gid = gene["id"]
        cands = gene_candidates.get(gid, [])
        best = max(c["composite_score"] for c in cands) if cands else 0
        gene_rankings.append(
            {"gene": gene, "candidates": cands, "best_score": best, "count": len(cands)}
        )
    gene_rankings.sort(key=lambda x: x["best_score"], reverse=True)

    # Build top-5 JSON for radar chart
    import json

    top5_items = []
    for c in scored_candidates[:5]:
        name = c["drug_name"].split("(")[0].strip()[:25]
        top5_items.append(
            {
                "name": name,
                "scores": [
                    c.get("target_similarity_score", 5),
                    c.get("final_proximity", 5),
                    c.get("mechanistic_rationale_score", 5),
                    c.get("clinical_evidence_score", 5),
                    c.get("adverse_event_score", c.get("safety_score", 5)),
                    c.get("novelty_score", 5) * 2,  # Scale 0-5 to 0-10 for chart
                ],
            }
        )
    top5_json = json.dumps(top5_items)

    n_tier1 = sum(1 for c in scored_candidates if c["composite_score"] >= 8.0)
    n_tier2 = sum(1 for c in scored_candidates if 7.0 <= c["composite_score"] < 8.0)
    avg_score = (
        sum(c["composite_score"] for c in scored_candidates) / len(scored_candidates)
        if scored_candidates
        else 0
    )

    def _tier_name(c):
        """Extract 'Tier N' from full tier label like '🔴 Tier 1 — Highest Priority'."""
        tier = c.get("tier", "")
        if "—" in tier:
            parts = tier.split("—")[0].strip().split()
            return f"{parts[-2]} {parts[-1]}"
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

    html = render_report(
        "reports/repurposing.html",
        {
            "ctx_disease": context["name"],
            "ctx_disease_id": context["id"],
            "ctx_report_name": context["report_name"],
            "n_candidates": len(scored_candidates),
            "n_genes": len(untargeted_genes),
            "n_tier1": n_tier1,
            "n_tier2": n_tier2,
            "avg_score": avg_score,
            "top5_json": top5_json,
            "candidates": adapted_candidates,
            "gene_rankings": adapted_gene_rankings,
            "generated_at": datetime.now().strftime("%B %d, %Y at %H:%M"),
            "disease_id": context["name"],
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
        text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;")
    )
