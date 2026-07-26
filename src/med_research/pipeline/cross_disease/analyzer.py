"""
Cross-Disease Drug Repurposing Analyzer — Phase 22

Loads all 7 autoimmune disease knowledge graphs, identifies shared
genes/pathways/drugs, computes disease similarity, and scores drugs
for multi-disease therapeutic potential.

Scoring Dimensions (each 0-10, weighted):
  1. Disease Coverage (30%): Across how many diseases is this drug relevant?
  2. Target Centrality (25%): Are the drug's targets shared across diseases?
  3. Pathway Breadth (20%): Range of distinct pathways affected across diseases
  4. Mechanistic Transferability (15%): How transferable is the mechanism?
  5. Novelty (10%): How novel is this cross-disease application?

Usage:
    python cross_disease/analyzer.py                        # Full analysis
    python cross_disease/analyzer.py --top 20               # Top 20 results
    python cross_disease/analyzer.py --export-html          # Generate report
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from med_research.logging_config import get_logger
from med_research.pipeline.knowledge_graph.config import (
    list_diseases,
    load_drugs,
    load_genes,
    load_pathways,
    load_relationships,
)

logger = get_logger(__name__)

DATA_DIR = Path(__file__).parent / "data"


# ── Data Loading ──────────────────────────────────────────────────────────


def load_all_disease_data() -> dict[str, Any]:
    """Load genes, drugs, pathways, and relationships for all diseases.

    Returns:
        dict keyed by disease_id with sub-keys "profile", "genes", "drugs",
        "pathways", "relationships", "kg".
    """
    all_diseases = list_diseases()
    data = {}

    for disease_id, meta in all_diseases.items():
        disease_data = {
            "profile": meta["profile"],
            "name": meta["name"],
        }
        try:
            disease_data["genes"] = load_genes(disease_id)
        except (FileNotFoundError, json.JSONDecodeError):
            disease_data["genes"] = {"genes": []}

        try:
            disease_data["drugs"] = load_drugs(disease_id)
        except (FileNotFoundError, json.JSONDecodeError):
            disease_data["drugs"] = {"drugs": []}

        try:
            disease_data["pathways"] = load_pathways(disease_id)
        except (FileNotFoundError, json.JSONDecodeError):
            disease_data["pathways"] = {"pathways": []}

        try:
            disease_data["relationships"] = load_relationships(disease_id)
        except (FileNotFoundError, json.JSONDecodeError):
            disease_data["relationships"] = {"relationships": []}

        data[disease_id] = disease_data

    return data


# ── Gene / Drug / Pathway Analysis ────────────────────────────────────────


def _normalize_gene_id(gene_id: str) -> str:
    """Normalize gene identifiers for cross-disease comparison."""
    return gene_id.upper().strip()


def _normalize_drug_id(drug_id: str) -> str:
    """Normalize drug identifiers for cross-disease comparison."""
    return drug_id.lower().strip()


def compute_shared_genes(data: dict[str, Any]) -> dict[str, Any]:
    """Identify genes shared across diseases and their per-disease details.

    Returns:
        dict with keys: "matrix" (gene -> disease -> details),
        "gene_disease_count" (gene -> number of diseases),
        "shared_genes" (list of genes in 2+ diseases, sorted by disease count)
    """
    gene_disease_map: dict = {}
    gene_details: dict = {}

    for disease_id, d_data in data.items():
        genes_list = d_data["genes"].get("genes", [])
        for g in genes_list:
            gid = _normalize_gene_id(g["id"])
            if gid not in gene_disease_map:
                gene_disease_map[gid] = []
                gene_details[gid] = {"name": g.get("name", gid), "per_disease": {}}
            gene_disease_map[gid].append(disease_id)
            gene_details[gid]["per_disease"][disease_id] = {
                "odds_ratio": g.get("odds_ratio"),
                "category": g.get("category", ""),
                "function": g.get("function", "")[:200],
            }

    shared = [
        {"gene_id": gid, "diseases": sorted(diseases), "disease_count": len(diseases),
         "name": gene_details[gid]["name"], "per_disease": gene_details[gid]["per_disease"]}
        for gid, diseases in gene_disease_map.items()
        if len(diseases) >= 2
    ]
    shared.sort(key=lambda x: x["disease_count"], reverse=True)

    return {
        "matrix": gene_details,
        "gene_disease_count": {g: len(d) for g, d in gene_disease_map.items()},
        "shared_genes": shared,
    }


def compute_shared_drugs(data: dict[str, Any]) -> dict[str, Any]:
    """Identify drugs shared across diseases and their per-disease details.

    Returns:
        dict with keys: "matrix", "drug_disease_count", "shared_drugs".
    """
    drug_disease_map: dict = {}
    drug_details: dict = {}

    for disease_id, d_data in data.items():
        drugs_list = d_data["drugs"].get("drugs", [])
        for d in drugs_list:
            did = _normalize_drug_id(d["id"])
            if did not in drug_disease_map:
                drug_disease_map[did] = []
                drug_details[did] = {"name": d.get("name", did), "per_disease": {}}
            drug_disease_map[did].append(disease_id)
            drug_details[did]["per_disease"][disease_id] = {
                "target": d.get("target", ""),
                "mechanism": d.get("mechanism", "")[:200],
                "category": d.get("category", ""),
                "approval": d.get("approval", ""),
            }

    shared = [
        {"drug_id": did, "diseases": sorted(diseases), "disease_count": len(diseases),
         "name": drug_details[did]["name"], "per_disease": drug_details[did]["per_disease"]}
        for did, diseases in drug_disease_map.items()
        if len(diseases) >= 2
    ]
    shared.sort(key=lambda x: x["disease_count"], reverse=True)

    return {
        "matrix": drug_details,
        "drug_disease_count": {d: len(ds) for d, ds in drug_disease_map.items()},
        "shared_drugs": shared,
    }


def compute_shared_pathways(data: dict[str, Any]) -> dict[str, Any]:
    """Identify pathways shared across diseases."""
    pathway_disease_map: dict = {}
    pathway_details: dict = {}

    for disease_id, d_data in data.items():
        pathways_list = d_data["pathways"].get("pathways", [])
        for p in pathways_list:
            pid = p["id"].lower().strip()
            if pid not in pathway_disease_map:
                pathway_disease_map[pid] = []
                pathway_details[pid] = {"name": p.get("name", pid), "per_disease": {}}
            pathway_disease_map[pid].append(disease_id)
            pathway_details[pid]["per_disease"][disease_id] = {
                "description": p.get("description", "")[:200],
                "key_components": p.get("key_components", []),
            }

    shared = [
        {"pathway_id": pid, "diseases": sorted(diseases), "disease_count": len(diseases),
         "name": pathway_details[pid]["name"], "per_disease": pathway_details[pid]["per_disease"]}
        for pid, diseases in pathway_disease_map.items()
        if len(diseases) >= 2
    ]
    shared.sort(key=lambda x: x["disease_count"], reverse=True)

    return {
        "matrix": pathway_details,
        "pathway_disease_count": {p: len(ds) for p, ds in pathway_disease_map.items()},
        "shared_pathways": shared,
    }


# ── Disease Similarity ────────────────────────────────────────────────────


def _jaccard(set_a: set, set_b: set) -> float:
    """Compute Jaccard similarity between two sets."""
    if not set_a or not set_b:
        return 0.0
    return len(set_a & set_b) / len(set_a | set_b)


def compute_disease_similarity(data: dict[str, Any]) -> dict[str, Any]:
    """Compute pairwise disease similarity based on shared genes, drugs, pathways.

    Returns:
        dict with keys: "matrix" (disease_id -> disease_id -> scores),
        "ranked_pairs" (sorted list of disease pairs by overall similarity).
    """
    disease_ids = sorted(data.keys())

    # Build per-disease gene/drug/pathway sets
    gene_sets = {}
    drug_sets = {}
    pathway_sets = {}

    for did in disease_ids:
        gene_sets[did] = {
            _normalize_gene_id(g["id"])
            for g in data[did]["genes"].get("genes", [])
        }
        drug_sets[did] = {
            _normalize_drug_id(d["id"])
            for d in data[did]["drugs"].get("drugs", [])
        }
        pathway_sets[did] = {
            p["id"].lower().strip()
            for p in data[did]["pathways"].get("pathways", [])
        }

    matrix = {}
    ranked_pairs = []

    for i, did_a in enumerate(disease_ids):
        matrix[did_a] = {}
        for did_b in disease_ids[i + 1:]:
            gene_sim = _jaccard(gene_sets[did_a], gene_sets[did_b])
            drug_sim = _jaccard(drug_sets[did_a], drug_sets[did_b])
            pathway_sim = _jaccard(pathway_sets[did_a], pathway_sets[did_b])

            overall = round(
                gene_sim * 0.40 + drug_sim * 0.35 + pathway_sim * 0.25, 4
            )

            pair_data = {
                "disease_a": did_a,
                "disease_b": did_b,
                "name_a": data[did_a]["name"],
                "name_b": data[did_b]["name"],
                "gene_similarity": round(gene_sim, 4),
                "drug_similarity": round(drug_sim, 4),
                "pathway_similarity": round(pathway_sim, 4),
                "overall_similarity": overall,
                "shared_gene_count": len(gene_sets[did_a] & gene_sets[did_b]),
                "shared_drug_count": len(drug_sets[did_a] & drug_sets[did_b]),
                "shared_pathway_count": len(pathway_sets[did_a] & pathway_sets[did_b]),
            }
            matrix[did_a][did_b] = pair_data
            ranked_pairs.append(pair_data)

    ranked_pairs.sort(key=lambda x: x["overall_similarity"], reverse=True)

    return {
        "matrix": matrix,
        "ranked_pairs": ranked_pairs,
        "gene_sets": {k: sorted(v) for k, v in gene_sets.items()},
        "drug_sets": {k: sorted(v) for k, v in drug_sets.items()},
    }


# ── Multi-Disease Drug Scoring ────────────────────────────────────────────


def score_multi_disease_drugs(data: dict, shared_genes: dict, shared_pathways: dict) -> list:
    """Score each drug for multi-disease therapeutic potential.

    For each drug that appears in at least one disease KG, compute a
    multi-disease repurposing score based on disease coverage, target
    centrality, pathway breadth, mechanistic transferability, and novelty.

    Returns:
        List of scored drug entries, sorted by composite_score descending.
    """
    all_disease_ids = sorted(data.keys())
    n_diseases = len(all_disease_ids)

    # Build drug->disease mapping and drug detail cache
    drug_info: dict = {}
    for did in all_disease_ids:
        for d in data[did]["drugs"].get("drugs", []):
            did_norm = _normalize_drug_id(d["id"])
            if did_norm not in drug_info:
                drug_info[did_norm] = {
                    "drug_id": did_norm,
                    "name": d.get("name", did_norm),
                    "diseases": set(),
                    "targets": set(),
                    "categories": set(),
                    "per_disease": {},
                }
            drug_info[did_norm]["diseases"].add(did)
            drug_info[did_norm]["targets"].add(d.get("target", ""))
            drug_info[did_norm]["categories"].add(d.get("category", ""))
            drug_info[did_norm]["per_disease"][did] = {
                "target": d.get("target", ""),
                "mechanism": d.get("mechanism", "")[:200],
                "category": d.get("category", ""),
                "approval": d.get("approval", ""),
            }

    # Build target -> disease count map (how many diseases involve each target)
    target_disease_count: dict = {}
    for did in all_disease_ids:
        for g in data[did]["genes"].get("genes", []):
            gid = _normalize_gene_id(g["id"])
            if gid not in target_disease_count:
                target_disease_count[gid] = set()
            target_disease_count[gid].add(did)

    gene_disease_counts = {g: len(ds) for g, ds in target_disease_count.items()}

    results = []

    for did_norm, info in drug_info.items():
        disease_count = len(info["diseases"])
        targets = info["targets"]
        target_disease_cov = [
            gene_disease_counts.get(t, 1) for t in targets if t in gene_disease_counts
        ]
        avg_target_coverage = (
            sum(target_disease_cov) / len(target_disease_cov) if target_disease_cov else 1
        )

        disease_coverage_score = min(10.0, disease_count / max(1, n_diseases) * 10.0)
        target_centrality_score = min(10.0, avg_target_coverage / max(1, n_diseases) * 10.0)
        pathway_breadth_score = min(10.0, len(info["categories"]) * 2.5)
        mechanistic_transferability = min(
            10.0, (disease_count * 1.5) + (len(targets) * 1.0 if targets else 0)
        )
        novelty_score = min(10.0, max(2.0, 10.0 - disease_count * 1.2))

        weights = {
            "disease_coverage": 0.30,
            "target_centrality": 0.25,
            "pathway_breadth": 0.20,
            "mechanistic_transferability": 0.15,
            "novelty": 0.10,
        }

        composite = (
            disease_coverage_score * weights["disease_coverage"]
            + target_centrality_score * weights["target_centrality"]
            + pathway_breadth_score * weights["pathway_breadth"]
            + mechanistic_transferability * weights["mechanistic_transferability"]
            + novelty_score * weights["novelty"]
        )

        results.append({
            "drug_id": did_norm,
            "drug_name": info["name"],
            "disease_count": disease_count,
            "diseases": sorted(info["diseases"]),
            "targets": sorted(info["targets"]),
            "categories": sorted(info["categories"]),
            "per_disease": info["per_disease"],
            "disease_coverage": round(disease_coverage_score, 1),
            "target_centrality": round(target_centrality_score, 1),
            "pathway_breadth": round(pathway_breadth_score, 1),
            "mechanistic_transferability": round(mechanistic_transferability, 1),
            "novelty": round(novelty_score, 1),
            "composite_score": round(composite, 2),
            "tier": _assign_tier(composite),
        })

    results.sort(key=lambda x: x["composite_score"], reverse=True)
    return results


def _assign_tier(score: float) -> str:
    if score >= 7.5:
        return "Tier 1 — Strong Multi-Disease Candidate"
    elif score >= 6.0:
        return "Tier 2 — Promising Cross-Disease Candidate"
    elif score >= 4.5:
        return "Tier 3 — Moderate Cross-Disease Potential"
    return "Tier 4 — Disease-Specific"


# ── Cross-Disease Repurposing Recommendations ─────────────────────────────


def compute_cross_disease_repurposing(data: dict) -> list:
    """Find drugs that appear in one disease's KG but target genes present
    in another disease's KG — potential cross-disease repurposing opportunities.

    Returns:
        List of repurposing recommendations sorted by confidence.
    """
    recommendations = []

    for src_disease, src_data in data.items():
        src_drugs = {_normalize_drug_id(d["id"]): d for d in src_data["drugs"].get("drugs", [])}

        for tgt_disease, tgt_data in data.items():
            if src_disease == tgt_disease:
                continue

            tgt_genes = {
                _normalize_gene_id(g["id"]): g
                for g in tgt_data["genes"].get("genes", [])
            }

            for drug_id, drug in src_drugs.items():
                target_str = drug.get("target", "")

                # Check if any of the drug's targets are risk genes in the target disease
                matched_genes = []
                for tgt_gene_id, tgt_gene in tgt_genes.items():
                    if tgt_gene_id in target_str or target_str in tgt_gene_id or _normalize_gene_id(tgt_gene.get("name", "")) in target_str:
                        matched_genes.append(tgt_gene_id)

                if matched_genes:
                    # Check if drug is already used in the target disease
                    tgt_drugs = {
                        _normalize_drug_id(d["id"])
                        for d in tgt_data["drugs"].get("drugs", [])
                    }
                    already_used = drug_id in tgt_drugs

                    confidence = min(10.0, len(matched_genes) * 3.0 + 4.0)

                    recommendations.append({
                        "source_disease": src_disease,
                        "source_disease_name": src_data["name"],
                        "target_disease": tgt_disease,
                        "target_disease_name": tgt_data["name"],
                        "drug_id": drug_id,
                        "drug_name": drug.get("name", drug_id),
                        "drug_target": target_str,
                        "matched_genes": matched_genes,
                        "already_used_in_target": already_used,
                        "confidence": round(confidence, 1),
                    })

    # Filter out already-used drugs
    novel = [r for r in recommendations if not r["already_used_in_target"]]
    novel.sort(key=lambda x: x["confidence"], reverse=True)

    # Group already-used ones separately
    existing = [r for r in recommendations if r["already_used_in_target"]]
    existing.sort(key=lambda x: x["confidence"], reverse=True)

    return novel + existing


# ── Full Pipeline ─────────────────────────────────────────────────────────


def compute_cross_disease_analysis(progress_callback=None) -> dict[str, Any]:
    """Run the full cross-disease analysis pipeline.

    Returns:
        dict with keys: disease_summary, shared_genes, shared_drugs,
        shared_pathways, disease_similarity, multi_disease_drugs,
        cross_disease_repurposing.
    """
    cb = progress_callback or (lambda p, m: None)

    cb(0, "Loading all disease data...")
    data = load_all_disease_data()
    disease_ids = sorted(data.keys())

    cb(10, f"Loaded {len(disease_ids)} diseases: {', '.join(disease_ids)}")

    cb(15, "Computing shared genes...")
    shared_genes = compute_shared_genes(data)

    cb(30, "Computing shared drugs...")
    shared_drugs = compute_shared_drugs(data)

    cb(45, "Computing shared pathways...")
    shared_pathways = compute_shared_pathways(data)

    cb(55, "Computing disease similarity...")
    similarity = compute_disease_similarity(data)

    cb(70, "Scoring multi-disease drugs...")
    multi_disease_drugs = score_multi_disease_drugs(data, shared_genes, shared_pathways)

    cb(85, "Computing cross-disease repurposing...")
    repurposing = compute_cross_disease_repurposing(data)

    cb(95, "Saving results...")
    result = {
        "disease_summary": {
            did: {
                "name": d_data["name"],
                "gene_count": len(d_data["genes"].get("genes", [])),
                "drug_count": len(d_data["drugs"].get("drugs", [])),
                "pathway_count": len(d_data["pathways"].get("pathways", [])),
                "relationship_count": len(d_data["relationships"].get("relationships", [])),
            }
            for did, d_data in data.items()
        },
        "shared_genes": shared_genes,
        "shared_drugs": shared_drugs,
        "shared_pathways": shared_pathways,
        "disease_similarity": similarity["ranked_pairs"],
        "multi_disease_drugs": multi_disease_drugs,
        "cross_disease_repurposing": repurposing,
        "total_diseases": len(disease_ids),
    }

    DATA_DIR.mkdir(parents=True, exist_ok=True)
    output_path = DATA_DIR / "cross_disease_analysis.json"
    safe = {}
    for k, v in result.items():
        if isinstance(v, dict):
            safe[k] = {str(k2): v2 for k2, v2 in v.items()}
        elif isinstance(v, list):
            safe[k] = v
        else:
            safe[k] = v

    # Convert sets to lists for JSON serialization
    safe["shared_genes"]["shared_genes"] = [
        {**sg, "diseases": list(sg["diseases"])}
        for sg in result["shared_genes"]["shared_genes"]
    ]
    safe["shared_drugs"]["shared_drugs"] = [
        {**sd, "diseases": list(sd["diseases"])}
        for sd in result["shared_drugs"]["shared_drugs"]
    ]
    safe["shared_pathways"]["shared_pathways"] = [
        {**sp, "diseases": list(sp["diseases"])}
        for sp in result["shared_pathways"]["shared_pathways"]
    ]

    output_path.write_text(json.dumps(safe, indent=2, default=list), encoding="utf-8")

    cb(100, f"Results saved to {output_path}")
    return result


# ── CLI ──────────────────────────────────────────────────────────────────


def analyze(results: dict[str, Any]) -> None:
    """Log analysis summary."""
    d_summary = results["disease_summary"]
    n = results["total_diseases"]

    logger.info("")
    logger.info("=" * 75)
    logger.info("CROSS-DISEASE DRUG REPURPOSING ANALYSIS")
    logger.info("=" * 75)
    logger.info("Diseases analyzed: %d", n)
    for did, info in sorted(d_summary.items()):
        logger.info("    %-5s -- %-35s (%d genes, %d drugs, %d pathways)",
                     did, info['name'], info['gene_count'], info['drug_count'],
                     info['pathway_count'])

    sg = results["shared_genes"]
    logger.info("Shared Genes (>=2 diseases): %d", len(sg['shared_genes']))
    for g in sg["shared_genes"][:10]:
        logger.info("    %-8s -- %d diseases: %s",
                     g['gene_id'], g['disease_count'], ', '.join(g['diseases']))

    sd = results["shared_drugs"]
    logger.info("Shared Drugs (>=2 diseases): %d", len(sd['shared_drugs']))
    for d in sd["shared_drugs"][:10]:
        logger.info("    %-20s -- %d diseases: %s",
                     d['drug_id'], d['disease_count'], ', '.join(d['diseases']))

    sp = results["shared_pathways"]
    logger.info("Shared Pathways (>=2 diseases): %d", len(sp['shared_pathways']))
    for p in sp["shared_pathways"][:10]:
        logger.info("    %-30s -- %d diseases",
                     p['pathway_id'], p['disease_count'])

    ds = results["disease_similarity"]
    logger.info("Most Similar Disease Pairs:")
    for pair in ds[:5]:
        logger.info("    %s <-> %s: %.4f (genes:%.3f, drugs:%.3f, pathways:%.3f)",
                     pair['disease_a'], pair['disease_b'],
                     pair['overall_similarity'], pair['gene_similarity'],
                     pair['drug_similarity'], pair['pathway_similarity'])

    mdd = results["multi_disease_drugs"]
    logger.info("Multi-Disease Drug Candidates: %d", len(mdd))
    tiers = {}
    for d in mdd:
        tiers[d["tier"]] = tiers.get(d["tier"], 0) + 1
    for tier, count in sorted(tiers.items()):
        logger.info("    %s: %d", tier, count)


def print_top_drugs(results: dict, top_n: int = 20):
    """Log top multi-disease drugs."""
    mdd = results["multi_disease_drugs"][:top_n]
    logger.info("")
    logger.info("=" * 75)
    logger.info("TOP %d MULTI-DISEASE DRUG CANDIDATES", top_n)
    logger.info("=" * 75)

    for i, d in enumerate(mdd, 1):
        logger.info("  #%d | %s", i, d['tier'])
        logger.info("  " + "-" * 50)
        logger.info("  Drug:      %s", d['drug_name'][:60])
        logger.info("  Diseases:  %d (%s)", d['disease_count'], ', '.join(d['diseases']))
        logger.info("  Targets:   %s", ', '.join(d['targets']) if d['targets'] else 'N/A')
        logger.info("  Score:     %.2f/10", d['composite_score'])
        logger.info("     |-- Disease Coverage:           %.1f/10", d['disease_coverage'])
        logger.info("     |-- Target Centrality:          %.1f/10", d['target_centrality'])
        logger.info("     |-- Pathway Breadth:            %.1f/10", d['pathway_breadth'])
        logger.info("     |-- Mechanistic Transferability:%.1f/10", d['mechanistic_transferability'])
        logger.info("     |-- Novelty:                    %.1f/10", d['novelty'])


def print_repurposing(results: dict, top_n: int = 15):
    """Log cross-disease repurposing recommendations."""
    recs = results["cross_disease_repurposing"]
    novel = [r for r in recs if not r["already_used_in_target"]][:top_n]

    logger.info("")
    logger.info("=" * 75)
    logger.info("TOP %d CROSS-DISEASE REPURPOSING OPPORTUNITIES", top_n)
    logger.info("=" * 75)

    for i, r in enumerate(novel[:top_n], 1):
        logger.info("  #%d", i)
        logger.info("  " + "-" * 50)
        logger.info("  %s -> %s", r['source_disease_name'], r['target_disease_name'])
        logger.info("  %s", r['drug_name'][:60])
        logger.info("  Target: %s", r['drug_target'])
        logger.info("  Matched Genes: %s", ', '.join(r['matched_genes']))
        logger.info("  Confidence: %.1f/10", r['confidence'])


def main():
    parser = argparse.ArgumentParser(
        description="Cross-Disease Drug Repurposing Analyzer — Phase 22"
    )
    parser.add_argument(
        "--top", type=int, default=20,
        help="Number of top results to display (default: 20)"
    )
    parser.add_argument(
        "--export-html", action="store_true",
        help="Generate HTML report"
    )
    args = parser.parse_args()

    results = compute_cross_disease_analysis()
    analyze(results)
    print_top_drugs(results, args.top)
    print_repurposing(results, args.top)

    if args.export_html:
        from med_research.pipeline.cross_disease.report import generate_html_report
        generate_html_report(results)
        logger.info("HTML report generated: cross_disease/report.html")

    return results


if __name__ == "__main__":
    main()
