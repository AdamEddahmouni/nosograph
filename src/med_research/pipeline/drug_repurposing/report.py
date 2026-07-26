"""
Lupus Drug Repurposing Report Generator

Generates a beautiful standalone HTML report with:
  - Executive summary and statistics
  - Priority-ranked repurposing candidates table
  - Per-gene analysis cards
  - Clinical trial status indicators
  - Interactive score breakdowns
"""

import json
from datetime import datetime
from pathlib import Path

from med_research.templates import env


def generate_html_report(
    scored_candidates: list, untargeted_genes: list, genes: dict, G
) -> str:
    """Generate a standalone HTML report and return the path."""

    output_path = Path(__file__).parent / "report.html"

    gene_candidates = {}
    for c in scored_candidates:
        gene_candidates.setdefault(c["gene_id"], []).append(c)

    gene_rankings = []
    for gene in untargeted_genes:
        gid = gene["id"]
        cands = gene_candidates.get(gid, [])
        best = max(c["composite_score"] for c in cands) if cands else 0
        gene_rankings.append(
            {
                "gene": gene,
                "candidates": cands,
                "best_score": best,
            }
        )
    gene_rankings.sort(key=lambda x: x["best_score"], reverse=True)

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
                    c.get("novelty_score", 5) * 2,
                ],
            }
        )

    n_tier1 = sum(1 for c in scored_candidates if c["composite_score"] >= 8.0)
    n_tier2 = sum(1 for c in scored_candidates if 7.0 <= c["composite_score"] < 8.0)
    avg_score = (
        sum(c["composite_score"] for c in scored_candidates) / len(scored_candidates)
        if scored_candidates
        else 0
    )

    candidates_display = []
    for c in scored_candidates[:25]:
        tier_parts = c["tier"].split("\u2014")
        candidates_display.append(
            {
                "drug_name": c["drug_name"],
                "drug_category": c["drug_category"],
                "gene_name": c["gene_name"],
                "gene_category": c["gene_category"],
                "composite_score": c["composite_score"],
                "target_similarity_score": c["target_similarity_score"],
                "final_proximity": c["final_proximity"],
                "mechanistic_rationale_score": c["mechanistic_rationale_score"],
                "clinical_evidence_score": c["clinical_evidence_score"],
                "safety_indicator": c.get("adverse_event_score", c.get("safety_score", "N/A")),
                "evidence_level": c["evidence_level"],
                "status": c["status"],
                "tier_name": tier_parts[0].strip() if tier_parts else c["tier"],
            }
        )

    gene_rankings_display = []
    for gr in gene_rankings:
        gene = gr["gene"]
        gene_rankings_display.append(
            {
                "gene": {
                    "id": gene["id"],
                    "name": gene["name"],
                    "category": gene.get("category", ""),
                    "function": gene.get("function", ""),
                    "lupus_evidence": gene.get("lupus_evidence", ""),
                    "odds_ratio": gene.get("odds_ratio", "N/A"),
                    "chromosome": gene.get("chromosome", "N/A"),
                },
                "best_score": gr["best_score"],
                "candidates": [
                    {
                        "drug_name": c["drug_name"],
                        "composite_score": c["composite_score"],
                        "mechanism": c.get("mechanism", ""),
                        "rationale": c.get("rationale", ""),
                        "evidence_level": c["evidence_level"],
                        "status": c["status"],
                    }
                    for c in gr["candidates"]
                ],
            }
        )

    context = {
        "generated_at": datetime.now().strftime("%B %d, %Y at %H:%M"),
        "n_candidates": len(scored_candidates),
        "n_genes": len(untargeted_genes),
        "n_tier1": n_tier1,
        "n_tier2": n_tier2,
        "avg_score": avg_score,
        "candidates": candidates_display,
        "gene_rankings": gene_rankings_display,
        "top5_json": json.dumps(top5_items),
    }

    template = env.get_template("reports/repurposing.html")
    html = template.render(**context)

    with open(output_path, "w", encoding="utf-8") as f:
        f.write(html)

    return str(output_path)


def escape_html(text: str) -> str:
    """Escape HTML special characters (kept for backward compatibility tests)."""
    if not text:
        return ""
    return (
        text.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )
