"""
Lupus Drug Repurposing Engine

Multi-modal scoring system that evaluates drug repurposing candidates
for the 13 untargeted lupus genes identified by the knowledge graph.

Scoring Dimensions (each 0-10, weighted):
  1. Target Similarity: How closely related is the drug's known target to the gene?
  2. Pathway Proximity: Network distance in the knowledge graph.
  3. Mechanistic Rationale: Does the drug's mechanism make biological sense?
  4. Clinical Evidence: Literature/trial support level.
  5. Safety Profile: Known safety from approved indications.
  6. Novelty Bonus: How novel is this repurposing application? (0-5)

Usage:
    python engine.py              # Full analysis
    python engine.py --top 10     # Top 10 candidates only
    python engine.py --gene BTK   # Candidates for a specific gene
"""

import json
import sys
import os
import argparse
import networkx as nx
from pathlib import Path
from collections import defaultdict

# Add parent to path for knowledge_graph import
sys.path.insert(0, str(Path(__file__).parent.parent))

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

DATA_DIR = Path(__file__).parent / "data"
KG_DATA_DIR = Path(__file__).parent.parent / "knowledge_graph" / "data"


def load_json(path: Path) -> dict:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def load_knowledge_graph():
    """Load the knowledge graph using the existing build_graph module."""
    from knowledge_graph.build_graph import build_graph
    return build_graph()


def load_genes():
    """Load gene data indexed by gene ID."""
    data = load_json(KG_DATA_DIR / "genes.json")
    return {g["id"]: g for g in data["genes"]}


def load_drugs():
    """Load drug data indexed by drug ID."""
    data = load_json(KG_DATA_DIR / "drugs.json")
    return {d["id"]: d for d in data["drugs"]}


def load_pathways():
    """Load pathway data indexed by pathway ID."""
    data = load_json(KG_DATA_DIR / "pathways.json")
    return {p["id"]: p for p in data["pathways"]}


def compute_pathway_proximity(G, gene_id: str, candidate: dict) -> float:
    """
    Compute pathway proximity score using shortest path in the knowledge graph.

    We look at the distance between the gene node and the drug's target nodes
    (if the drug exists in the graph), or pathway-level proximity.
    """
    gene_label = G.nodes[gene_id].get("label", gene_id)

    # If the drug is in our knowledge graph, use network distance
    drug_nodes = [
        n
        for n, d in G.nodes(data=True)
        if d.get("type") == "drug"
        and candidate["drug_name"].lower().split("(")[0].strip()
        in d.get("label", "").lower()
    ]

    if drug_nodes and gene_id in G:
        try:
            distances = []
            for dn in drug_nodes:
                dist = nx.shortest_path_length(G, source=dn, target=gene_id)
                distances.append(dist)
            min_dist = min(distances) if distances else 5
            # Convert distance to score (closer = higher score)
            # Distance 1-2 = score 10, distance 3 = 8, 4 = 6, 5 = 4, >5 = 2
            if min_dist <= 1:
                return 10.0
            elif min_dist == 2:
                return 9.0
            elif min_dist == 3:
                return 7.0
            elif min_dist == 4:
                return 5.0
            else:
                return max(2.0, 10.0 - min_dist * 1.5)
        except (nx.NetworkXNoPath, nx.NodeNotFound):
            pass

    # If drug is not in graph, score based on the candidate's curated score
    return candidate.get("pathway_proximity_score", 5.0)


def identify_untargeted_genes(G) -> list:
    """Identify lupus-associated genes with no direct drug targeting them."""
    targeted_genes = set()
    for u, v, d in G.edges(data=True):
        if d.get("type") == "TARGETS" and G.nodes[v].get("type") == "gene":
            targeted_genes.add(v)

    untargeted = []
    for node, data in G.nodes(data=True):
        if data.get("type") == "gene" and node not in targeted_genes:
            untargeted.append(
                {
                    "id": node,
                    "name": data.get("label", node),
                    "function": data.get("description", ""),
                    "lupus_evidence": data.get("lupus_evidence", ""),
                    "odds_ratio": data.get("odds_ratio"),
                    "category": data.get("category", ""),
                    "chromosome": data.get("chromosome", ""),
                }
            )

    # Filter out drug-target genes (CD20, IMPDH, Calcineurin, Glucocorticoid Receptor)
    # These aren't lupus risk genes - they're drug targets we added
    drug_target_genes = {"CD20", "IMPDH", "Calcineurin", "Glucocorticoid Receptor"}
    untargeted = [g for g in untargeted if g["id"] not in drug_target_genes]

    return untargeted


def compute_composite_score(candidate: dict) -> float:
    """
    Compute weighted composite score from all dimensions.

    Weights:
        Target Similarity: 25%
        Pathway Proximity: 15%
        Mechanistic Rationale: 25%
        Clinical Evidence: 20%
        Safety Profile: 10%
        Novelty Bonus: 5%
    """
    weights = {
        "target_similarity_score": 0.25,
        "pathway_proximity_score": 0.15,
        "mechanistic_rationale_score": 0.25,
        "clinical_evidence_score": 0.20,
        "safety_score": 0.10,
        "novelty_score": 0.05,
    }

    composite = 0.0
    for key, weight in weights.items():
        score = candidate.get(key, 5)
        composite += score * weight

    return round(composite, 2)


def score_candidates(G, candidates: list, genes: dict) -> list:
    """Score all repurposing candidates and compute composite scores."""
    scored = []

    for candidate in candidates:
        gene_id = candidate["gene_id"]
        gene_info = genes.get(gene_id, {})

        # Compute pathway proximity from the knowledge graph
        try:
            kg_proximity = compute_pathway_proximity(G, gene_id, candidate)
        except (nx.NetworkXNoPath, nx.NodeNotFound, KeyError, ValueError):
            kg_proximity = candidate.get("pathway_proximity_score", 5.0)

        # Use the higher of curated score and computed proximity
        curated_proximity = candidate.get("pathway_proximity_score", 5.0)
        final_proximity = max(kg_proximity, curated_proximity)

        composite = compute_composite_score(candidate)

        scored.append(
            {
                **candidate,
                "kg_pathway_proximity": round(kg_proximity, 1),
                "final_proximity": round(final_proximity, 1),
                "composite_score": composite,
                "gene_name": gene_info.get("name", gene_id),
                "gene_category": gene_info.get("category", ""),
                "gene_function": gene_info.get("function", ""),
                "gene_lupus_evidence": gene_info.get("lupus_evidence", ""),
                "gene_odds_ratio": gene_info.get("odds_ratio"),
            }
        )

    # Sort by composite score descending
    scored.sort(key=lambda x: x["composite_score"], reverse=True)

    # Assign priority tiers
    for c in scored:
        if c["composite_score"] >= 8.0:
            c["tier"] = "🔴 Tier 1 — Highest Priority"
        elif c["composite_score"] >= 7.0:
            c["tier"] = "🟠 Tier 2 — High Priority"
        elif c["composite_score"] >= 6.0:
            c["tier"] = "🟡 Tier 3 — Medium Priority"
        else:
            c["tier"] = "🟢 Tier 4 — Lower Priority"

    return scored


def analyze(scored_candidates: list):
    """Print statistical summary of scored candidates."""
    print("\n" + "=" * 75)
    print("📊 REPURPOSING ANALYSIS SUMMARY")
    print("=" * 75)

    # By tier
    tier_counts = defaultdict(int)
    for c in scored_candidates:
        tier_counts[c["tier"]] += 1

    print(f"\n  Total candidates evaluated: {len(scored_candidates)}")
    print(f"  Score range: {min(c['composite_score'] for c in scored_candidates):.2f} - {max(c['composite_score'] for c in scored_candidates):.2f}")
    print(f"\n  Distribution by priority tier:")
    for tier in ["🔴 Tier 1 — Highest Priority", "🟠 Tier 2 — High Priority", "🟡 Tier 3 — Medium Priority", "🟢 Tier 4 — Lower Priority"]:
        count = tier_counts[tier]
        if count > 0:
            print(f"    {tier}: {count} candidates")

    # By gene
    gene_counts = defaultdict(int)
    gene_scores = defaultdict(list)
    for c in scored_candidates:
        gene_counts[c["gene_name"]] += 1
        gene_scores[c["gene_name"]].append(c["composite_score"])

    print(f"\n  Genes with most repurposing candidates:")
    for gene_name, count in sorted(gene_counts.items(), key=lambda x: x[1], reverse=True):
        avg = sum(gene_scores[gene_name]) / len(gene_scores[gene_name])
        print(f"    {gene_name}: {count} candidates (avg score: {avg:.2f})")

    # Top unique drugs
    drug_scores = defaultdict(list)
    for c in scored_candidates:
        drug_scores[c["drug_name"]].append(c["composite_score"])

    print(f"\n  Most promising drugs (across multiple genes):")
    multi_gene_drugs = [
        (drug, scores)
        for drug, scores in drug_scores.items()
        if len(scores) >= 2
    ]
    multi_gene_drugs.sort(key=lambda x: sum(x[1]) / len(x[1]), reverse=True)
    for drug, scores in multi_gene_drugs[:8]:
        print(f"    {drug}: targets {len(scores)} genes (avg: {sum(scores)/len(scores):.2f})")


def print_top_candidates(scored_candidates: list, top_n: int = 10):
    """Print the top N repurposing candidates."""
    print("\n" + "=" * 75)
    print(f"🏆 TOP {top_n} REPURPOSING CANDIDATES")
    print("=" * 75)

    for i, c in enumerate(scored_candidates[:top_n], 1):
        print(f"\n  #{i} | {c['tier']}")
        print(f"  ─────────────────────────────────────────────")
        print(f"  💊 Drug:      {c['drug_name']}")
        print(f"  🧬 Gene:      {c['gene_name']} ({c['gene_id']})")
        print(f"  📂 Category:  {c['gene_category']}")
        print(f"  ⭐ Score:     {c['composite_score']:.2f}/10")
        print(f"     ├─ Target Similarity:     {c['target_similarity_score']}/10")
        print(f"     ├─ Pathway Proximity:     {c['final_proximity']:.1f}/10")
        print(f"     ├─ Mechanistic Rationale: {c['mechanistic_rationale_score']}/10")
        print(f"     ├─ Clinical Evidence:     {c['clinical_evidence_score']}/10")
        print(f"     ├─ Safety Profile:        {c['safety_score']}/10")
        print(f"     └─ Novelty Bonus:         {c['novelty_score']}/5")
        print(f"  📋 Evidence:   {c['evidence_level']}")
        print(f"  🔬 Mechanism:  {c['mechanism'][:150]}...")
        print(f"  💡 Rationale:  {c['rationale'][:180]}...")
        print(f"  🚦 Status:     {c['status']}")


def print_gene_analysis(scored_candidates: list, genes: dict, gene_id: str):
    """Print detailed analysis for a specific gene."""
    gene = genes.get(gene_id, {})
    gene_candidates = [c for c in scored_candidates if c["gene_id"] == gene_id]

    print("\n" + "=" * 75)
    print(f"🧬 GENE-FOCUSED ANALYSIS: {gene.get('name', gene_id)}")
    print("=" * 75)
    print(f"\n  Function:        {gene.get('function', 'N/A')}")
    print(f"  Category:        {gene.get('category', 'N/A')}")
    print(f"  Chromosome:      {gene.get('chromosome', 'N/A')}")
    print(f"  Odds Ratio:      {gene.get('odds_ratio', 'N/A')}")
    print(f"  Lupus Evidence:  {gene.get('lupus_evidence', 'N/A')[:200]}")

    if not gene_candidates:
        print(f"\n  ⚠️  No repurposing candidates found for this gene.")
        return

    print(f"\n  📋 {len(gene_candidates)} repurposing candidates:")
    for i, c in enumerate(gene_candidates, 1):
        print(f"\n    {i}. {c['drug_name']} | Score: {c['composite_score']:.2f} | {c['tier']}")
        print(f"       Mechanism: {c['mechanism'][:120]}...")
        print(f"       Rationale: {c['rationale'][:150]}...")
        print(f"       Evidence:  {c['evidence_level']}")
        print(f"       Status:    {c['status']}")


def main():
    parser = argparse.ArgumentParser(
        description="Lupus Drug Repurposing Engine — Multi-modal scoring for untargeted genes"
    )
    parser.add_argument("--top", type=int, default=15, help="Number of top candidates to display")
    parser.add_argument("--gene", type=str, help="Focus analysis on a specific gene ID")
    parser.add_argument("--export-html", action="store_true", help="Export HTML report")
    args = parser.parse_args()

    print("🔄 Loading knowledge graph...")
    G = load_knowledge_graph()
    print(f"   Graph loaded: {G.number_of_nodes()} nodes, {G.number_of_edges()} edges")

    print("🔄 Loading gene and candidate data...")
    genes = load_genes()
    candidates_data = load_json(DATA_DIR / "candidates.json")
    candidates = candidates_data["repurposing_candidates"]
    print(f"   Loaded {len(genes)} genes, {len(candidates)} repurposing candidates")

    print("🔄 Identifying untargeted lupus genes...")
    untargeted = identify_untargeted_genes(G)
    untargeted_ids = {g["id"] for g in untargeted}
    print(f"   Found {len(untargeted)} untargeted lupus genes:")
    for g in untargeted:
        print(f"     • {g['name']} ({g['id']}) — {g.get('category', '')}")

    print("🔄 Scoring candidates...")
    scored = score_candidates(G, candidates, genes)

    # Filter to only candidates for actually untargeted genes
    scored = [c for c in scored if c["gene_id"] in untargeted_ids]
    print(f"   Scored {len(scored)} candidates across {len(set(c['gene_id'] for c in scored))} genes")

    analyze(scored)

    if args.gene:
        print_gene_analysis(scored, genes, args.gene)
    else:
        print_top_candidates(scored, args.top)

    if args.export_html:
        from drug_repurposing.report import generate_html_report
        generate_html_report(scored, untargeted, genes, G)
        print("\n✅ HTML report generated: drug_repurposing/report.html")

    return scored


if __name__ == "__main__":
    scored = main()
