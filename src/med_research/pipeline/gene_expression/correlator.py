"""
Gene Expression Correlation Engine (Connectivity Map Approach)

Compares drug mechanisms against curated SLE gene expression signatures
to score each drug's potential to reverse disease-associated dysregulation.

Scoring Dimensions (each 0-10, weighted):
  1. Signature Reversal (35%): Counteracts up/down-regulated disease genes?
  2. Target-Disease Gene Overlap (25%): Drug targets in lupus pathways?
  3. Cell Type Specificity (20%): Active in SLE-relevant cell types?
  4. Expression Evidence (15%): Well-studied in SLE expression datasets?
  5. Directionality (5%): Drug's effect directionally correct?

Usage:
    python gene_expression/correlator.py              # Full analysis
    python gene_expression/correlator.py --top 15     # Top 15 drugs
    python gene_expression/correlator.py --export-html  # Generate report
    python gene_expression/correlator.py --geo         # Use GEO consensus
    python gene_expression/correlator.py --geo --tissue kidney  # Tissue-specific
"""

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from med_research.pipeline.knowledge_graph.config import load_drugs as config_load_drugs

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

DATA_DIR = Path(__file__).parent / "data"

_DEFAULT_SIGNATURE = None

def _get_default_signature():
    global _DEFAULT_SIGNATURE
    if _DEFAULT_SIGNATURE is None:
        try:
            from med_research.pipeline.gene_expression.signature import get_signature
            sig = get_signature(source="curated")
            _up = {k: v["fold_change"] for k, v in sig.get("upregulated", {}).items()}
            _down = {k: v["fold_change"] for k, v in sig.get("downregulated", {}).items()}
            _DEFAULT_SIGNATURE = {"upregulated": _up, "downregulated": _down,
                                  "source": sig.get("source", "curated"),
                                  "num_studies_used": sig.get("num_studies_used", 0)}
        except Exception:
            _DEFAULT_SIGNATURE = {"upregulated": SLE_UPREGULATED,
                                  "downregulated": SLE_DOWNREGULATED,
                                  "source": "curated_literature",
                                  "num_studies_used": 0}
    return _DEFAULT_SIGNATURE


def _normalize_signature(signature):
    """Normalize a signature dict to {upregulated: {gene: fc}, downregulated: {gene: fc}}."""
    if signature is None:
        sig = _get_default_signature()
        return sig["upregulated"], sig["downregulated"], sig.get("source", ""), sig.get("num_studies_used", 0)

    if isinstance(next(iter(signature.get("upregulated", {}).values()), None), dict):
        up = {k: v["fold_change"] for k, v in signature.get("upregulated", {}).items()}
        down = {k: v["fold_change"] for k, v in signature.get("downregulated", {}).items()}
    else:
        up = signature.get("upregulated", {})
        down = signature.get("downregulated", {})

    source = signature.get("source", "")
    num_studies = signature.get("num_studies_used", 0)
    return up, down, source, num_studies



def load_json(path: Path) -> dict:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def load_drugs() -> dict:
    """Load drug data indexed by drug ID."""
    data = config_load_drugs()
    return {d["id"]: d for d in data["drugs"]}


# ── Curated SLE Gene Expression Signature ────────────────────────────────
# Based on published SLE transcriptomic studies (PBMC, whole blood, kidney)
# These are well-replicated differentially expressed genes in SLE

SLE_UPREGULATED = {
    "IRF5": 2.5, "IRF7": 3.2, "STAT1": 2.8, "STAT2": 2.1,
    "IFI44L": 4.5, "IFIT1": 3.8, "IFIT3": 3.5, "MX1": 3.0,
    "MX2": 2.7, "OAS1": 2.9, "OAS2": 2.4, "OAS3": 2.6,
    "ISG15": 3.3, "RSAD2": 3.1, "IFIH1": 2.2, "DDX58": 2.0,
    "TLR7": 1.8, "TLR9": 1.6, "MYD88": 1.7, "IRAK4": 1.5,
    "BAFF": 2.3, "TNFSF13B": 2.3, "CD40L": 1.9, "CD40LG": 1.9,
    "TNFSF4": 1.6, "ICOS": 1.5, "CD86": 1.7, "CD80": 1.4,
    "IL6": 2.1, "TNF": 1.8, "IL1B": 1.6, "CCL2": 2.0,
    "CCL5": 1.9, "CXCL10": 2.8, "CXCR3": 1.7,
    "PRDM1": 1.8, "IKZF1": 1.5, "IKZF3": 1.4,
    "UBE2L3": 1.6, "TNFAIP3": 1.7, "TNIP1": 1.5,
    "CASP1": 1.4, "AIM2": 1.3, "NLRC4": 1.2,
}

SLE_DOWNREGULATED = {
    "C1QA": 3.5, "C1QB": 3.2, "C1QC": 3.0, "C2": 2.8,
    "C4A": 3.3, "C4B": 2.9, "ITGAM": 2.2, "FCGR2A": 2.0,
    "FCGR3A": 2.1, "CD32": 2.0, "CD16A": 2.1,
    "ATG5": 1.8, "ATG7": 1.5, "BECN1": 1.4,
    "FOXP3": 2.2, "CTLA4": 1.9, "IL2RA": 1.7,
    "TGFB1": 1.8, "IL10": 1.6, "CD25": 1.7,
    "DNASE1": 2.5, "DNASE1L3": 2.8, "TREX1": 2.0,
    "SAMHD1": 1.6, "ACP5": 1.4,
    "ELMO1": 1.7, "MERTK": 1.5, "GAS6": 1.4,
}

# ── Drug → Target Gene(s) Mapping ─────────────────────────────────────────
# Maps drug IDs to the genes their targets modulate (for expression reversal)

DRUG_TARGET_GENES = {
    "belimumab": ["BAFF", "TNFSF13B"],
    "anifrolumab": ["IFNAR1"],
    "voclosporin": ["Calcineurin"],
    "hydroxychloroquine": ["TLR7", "TLR9"],
    "mycophenolate": ["IMPDH"],
    "cyclophosphamide": ["DNA", "TOP2A"],
    "rituximab": ["CD20", "MS4A1"],
    "prednisone": ["NR3C1", "NFKB1", "NFKB2"],
    "tacrolimus": ["Calcineurin"],
    "azathioprine": ["HPRT1", "PPAT"],
    "baricitinib": ["JAK1", "JAK2", "STAT1", "STAT2"],
    "obinutuzumab": ["CD20", "MS4A1"],
    "acalabrutinib": ["BTK"],
    "avacopan": ["C5AR1", "C5"],
    "cyclosporine": ["Calcineurin"],
    "dimethyl_fumarate": ["NFE2L2", "NFKB1"],
    "iscalimab": ["CD40", "CD40LG"],
    "ravulizumab": ["C5"],
    "rozanolixizumab": ["FCGRT"],
    "tofacitinib": ["JAK1", "JAK3", "STAT1", "STAT3"],
    "deucravacitinib": ["TYK2", "STAT1", "STAT2"],
    "dapirolizumab_pegol": ["CD40LG", "CD40L"],
    "litifilimab": ["CLEC4C", "BDCA2"],
    "iberdomide": ["IKZF1", "IKZF3"],
    "teclistamab": ["TNFRSF17", "BCMA"],
    "anti_cd19_cart": ["CD19"],
}

# ── Drug Mechanism → Expression Reversal Mapping ──────────────────────────
# For drugs targeting pathways (not single genes), which SLE genes are affected

DRUG_PATHWAY_REVERSAL = {
    "belimumab": {
        "downregulated_genes": ["BAFF", "TNFSF13B"],
        "effect": "Reduces BAFF, decreasing B cell survival signals",
    },
    "anifrolumab": {
        "downregulated_genes": ["IRF5", "IRF7", "STAT1", "IFI44L", "IFIT1", "MX1",
                                "ISG15", "OAS1", "RSAD2"],
        "effect": "Blocks type I IFN receptor, suppressing IFN gene signature",
    },
    "baricitinib": {
        "downregulated_genes": ["STAT1", "STAT2", "IRF5", "IRF7", "IL6"],
        "effect": "JAK1/2 inhibition reduces IFN and IL-6 signaling",
    },
    "deucravacitinib": {
        "downregulated_genes": ["STAT1", "STAT2", "IRF5", "IRF7"],
        "effect": "Selective TYK2 inhibition blocks type I IFN signaling",
    },
    "tofacitinib": {
        "downregulated_genes": ["STAT1", "STAT3", "IL6", "TNF"],
        "effect": "Pan-JAK inhibition broadly suppresses cytokine signaling",
    },
    "acalabrutinib": {
        "downregulated_genes": ["BTK", "CD86", "CD80"],
        "effect": "BTK inhibition reduces BCR signaling and costimulation",
    },
    "litifilimab": {
        "downregulated_genes": ["IRF7", "IFIT1", "MX1", "ISG15", "RSAD2"],
        "effect": "Depletes pDCs, reducing type I IFN production at source",
    },
    "iberdomide": {
        "downregulated_genes": ["IKZF1", "IKZF3", "PRDM1"],
        "effect": "Degrades IKZF1/3, reducing plasma cell differentiation",
    },
    "iscalimab": {
        "downregulated_genes": ["CD40L", "CD40LG", "ICOS", "TNFSF4"],
        "effect": "Blocks CD40-CD40L, reducing T-B costimulation",
    },
    "dapirolizumab_pegol": {
        "downregulated_genes": ["CD40L", "CD40LG", "ICOS"],
        "effect": "Blocks CD40L, inhibiting T-dependent B cell activation",
    },
    "hydroxychloroquine": {
        "downregulated_genes": ["TLR7", "TLR9", "IRF7", "IFIT1"],
        "effect": "Inhibits endosomal TLR7/9, reducing IFN-α production",
    },
}

# ── Cell Type Relevance ───────────────────────────────────────────────────

CELL_TYPE_RELEVANCE = {
    "B_cell": 9.0,
    "plasma_cell": 9.5,
    "plasmacytoid_DC": 9.0,
    "myeloid_DC": 7.0,
    "T_follicular_helper": 8.5,
    "CD4_T_cell": 7.5,
    "CD8_T_cell": 6.0,
    "monocyte": 7.0,
    "macrophage": 7.5,
    "neutrophil": 6.5,
    "NK_cell": 6.0,
}

DRUG_CELL_TYPES = {
    "belimumab": ["B_cell", "plasma_cell"],
    "anifrolumab": ["plasmacytoid_DC", "monocyte", "B_cell"],
    "baricitinib": ["CD4_T_cell", "T_follicular_helper", "B_cell", "monocyte"],
    "deucravacitinib": ["CD4_T_cell", "T_follicular_helper", "plasmacytoid_DC"],
    "acalabrutinib": ["B_cell", "macrophage", "monocyte"],
    "litifilimab": ["plasmacytoid_DC"],
    "iberdomide": ["plasma_cell", "B_cell"],
    "iscalimab": ["B_cell", "T_follicular_helper", "CD4_T_cell"],
    "dapirolizumab_pegol": ["B_cell", "T_follicular_helper", "CD4_T_cell"],
    "hydroxychloroquine": ["plasmacytoid_DC", "B_cell", "monocyte"],
    "rituximab": ["B_cell"],
    "obinutuzumab": ["B_cell"],
    "teclistamab": ["plasma_cell"],
    "anti_cd19_cart": ["B_cell", "plasma_cell"],
    "ravulizumab": ["macrophage", "monocyte", "neutrophil"],
    "avacopan": ["neutrophil", "macrophage"],
    "prednisone": ["CD4_T_cell", "B_cell", "monocyte", "macrophage", "neutrophil"],
    "voclosporin": ["T_follicular_helper", "CD4_T_cell"],
    "tacrolimus": ["T_follicular_helper", "CD4_T_cell"],
    "cyclosporine": ["T_follicular_helper", "CD4_T_cell"],
    "mycophenolate": ["B_cell", "CD4_T_cell", "CD8_T_cell"],
    "azathioprine": ["B_cell", "CD4_T_cell", "CD8_T_cell"],
    "cyclophosphamide": ["B_cell", "CD4_T_cell", "plasma_cell"],
    "dimethyl_fumarate": ["monocyte", "macrophage", "CD4_T_cell"],
    "tofacitinib": ["CD4_T_cell", "T_follicular_helper", "monocyte", "NK_cell"],
    "rozanolixizumab": ["B_cell", "plasma_cell"],
}


# ── Scoring Functions ────────────────────────────────────────────────────

def score_signature_reversal(drug_id: str, signature=None) -> float:
    """Score how well the drug reverses the SLE expression signature.

    Higher score = drug mechanism directly counteracts more dysregulated genes.

    Args:
        drug_id: Drug identifier
        signature: Optional signature dict with upregulated/downregulated gene maps
    """
    up_genes, down_genes, _, _ = _normalize_signature(signature)

    if drug_id not in DRUG_PATHWAY_REVERSAL and drug_id not in DRUG_TARGET_GENES:
        return 2.0

    score = 0.0
    downregulated_hits = 0
    upregulated_reversed = 0

    if drug_id in DRUG_PATHWAY_REVERSAL:
        reversal = DRUG_PATHWAY_REVERSAL[drug_id]
        for gene in reversal.get("downregulated_genes", []):
            if gene in up_genes:
                downregulated_hits += 1
                score += up_genes[gene] * 0.8

    targets = DRUG_TARGET_GENES.get(drug_id, [])
    for gene in targets:
        if gene in up_genes:
            upregulated_reversed += 1
            score += up_genes[gene] * 0.5

    if downregulated_hits >= 5:
        score += 3.0
    elif downregulated_hits >= 3:
        score += 2.0
    elif downregulated_hits >= 1:
        score += 1.0

    score = min(10.0, score * 0.6 + 1.0)

    return round(score, 1)


def score_target_disease_overlap(drug_id: str, signature=None) -> float:
    """Score based on how many drug target genes overlap with SLE-dysregulated genes.

    Args:
        drug_id: Drug identifier
        signature: Optional signature dict with upregulated/downregulated gene maps
    """
    up_genes, down_genes, _, _ = _normalize_signature(signature)

    targets = DRUG_TARGET_GENES.get(drug_id, [])

    pathway_genes = set()
    if drug_id in DRUG_PATHWAY_REVERSAL:
        pathway_genes = set(DRUG_PATHWAY_REVERSAL[drug_id].get("downregulated_genes", []))

    all_affected = set(targets) | pathway_genes
    upregulated_overlap = all_affected & set(up_genes.keys())
    downregulated_overlap = all_affected & set(down_genes.keys())

    up_score = sum(up_genes.get(g, 0) for g in upregulated_overlap)
    down_score = sum(down_genes.get(g, 0) for g in downregulated_overlap)

    total = up_score * 0.7 + down_score * 0.3
    return round(min(10.0, total * 0.7 + 1.0), 1)


def score_cell_type_specificity(drug_id: str) -> float:
    """Score based on how relevant the drug's cell targets are to SLE pathology."""
    cell_types = DRUG_CELL_TYPES.get(drug_id, [])
    if not cell_types:
        return 3.0  # Unknown — neutral

    scores = [CELL_TYPE_RELEVANCE.get(ct, 5.0) for ct in cell_types]
    avg = sum(scores) / len(scores)

    # Bonus for targeting B cells or pDCs (key SLE cell types)
    key_types = {"B_cell", "plasma_cell", "plasmacytoid_DC"}
    key_hits = sum(1 for ct in cell_types if ct in key_types)
    bonus = min(2.0, key_hits * 1.0)

    return round(min(10.0, avg * 0.7 + bonus + 1.0), 1)


def score_expression_evidence(drug_id: str, drugs: dict = None) -> float:
    """Score based on publication evidence strength for gene expression studies."""
    if drugs is None:
        drugs = load_drugs()
    drug = drugs.get(drug_id, {})

    references = drug.get("references", [])
    n_refs = len(references)

    if n_refs >= 3:
        return 8.0
    elif n_refs >= 2:
        return 6.0
    elif n_refs >= 1:
        return 4.0
    return 2.0


def score_directionality(drug_id: str) -> float:
    """Check if the drug's effect is directionally correct for SLE."""
    if drug_id not in DRUG_PATHWAY_REVERSAL:
        return 5.0

    reversal = DRUG_PATHWAY_REVERSAL[drug_id]
    downregulated_count = len(reversal.get("downregulated_genes", []))

    # Drugs that downregulate the IFN signature are directionally correct
    ifn_genes = {"IRF5", "IRF7", "STAT1", "IFI44L", "IFIT1", "ISG15", "MX1"}
    downregulated = reversal.get("downregulated_genes", [])
    ifn_hits = sum(1 for g in downregulated if g in ifn_genes)

    if ifn_hits >= 3:
        return 10.0
    elif ifn_hits >= 1:
        return 8.0
    elif downregulated_count >= 3:
        return 7.0
    elif downregulated_count >= 1:
        return 6.0
    return 5.0


def correlate_drug(drug_id: str, drug: dict, all_drugs: dict = None,
                   signature=None) -> dict:
    """Score a single drug for gene expression reversal potential.

    Returns dict with individual scores and composite score.

    Args:
        drug_id: Drug identifier
        drug: Drug metadata dict
        all_drugs: Full drug library for evidence scoring
        signature: Optional signature dict with upregulated/downregulated gene maps
    """
    sig_rev = score_signature_reversal(drug_id, signature)
    overlap = score_target_disease_overlap(drug_id, signature)
    cell_type = score_cell_type_specificity(drug_id)
    evidence = score_expression_evidence(drug_id, all_drugs)
    direction = score_directionality(drug_id)

    weights = {
        "signature_reversal": 0.35,
        "target_disease_overlap": 0.25,
        "cell_type_specificity": 0.20,
        "expression_evidence": 0.15,
        "directionality": 0.05,
    }

    composite = (
        sig_rev * weights["signature_reversal"]
        + overlap * weights["target_disease_overlap"]
        + cell_type * weights["cell_type_specificity"]
        + evidence * weights["expression_evidence"]
        + direction * weights["directionality"]
    )

    return {
        "drug_id": drug_id,
        "drug_name": drug.get("name", drug_id),
        "category": drug.get("category", ""),
        "type": drug.get("type", ""),
        "mechanism": drug.get("mechanism", "")[:200],
        "signature_reversal": sig_rev,
        "target_disease_overlap": overlap,
        "cell_type_specificity": cell_type,
        "expression_evidence": evidence,
        "directionality": direction,
        "composite_score": round(composite, 2),
        "tier": _assign_tier(composite),
    }


def _assign_tier(score: float) -> str:
    if score >= 7.5:
        return "🔴 Tier 1 — Strong Expression Reversal"
    elif score >= 6.0:
        return "🟠 Tier 2 — Moderate Reversal"
    elif score >= 4.5:
        return "🟡 Tier 3 — Weak Reversal"
    return "🟢 Tier 4 — Minimal Reversal"


def compute_all_correlations(progress_callback=None, signature=None,
                             signature_source="auto", tissue=None) -> list:
    """Correlate all 26 drugs against the SLE expression signature.

    Returns list of scored drugs sorted by composite score descending.

    Args:
        progress_callback: Optional fn(percent, message) for progress reporting
        signature: Optional pre-loaded signature dict
        signature_source: "auto", "geo", or "curated"
        tissue: Tissue filter for GEO search
    """
    cb = progress_callback or (lambda p, m: None)

    cb(0, "Loading drug library...")
    drugs = load_drugs()

    if signature is None and signature_source != "curated":
        try:
            from med_research.pipeline.gene_expression.signature import get_signature
            sig = get_signature(source=signature_source, tissue=tissue)
            if sig and sig.get("num_studies_used", 0) > 0:
                signature = sig
        except Exception:
            pass

    if signature is None:
        signature = _get_default_signature()

    _, _, sig_source, num_studies = _normalize_signature(signature)

    cb(10, f"Correlating {len(drugs)} drugs against SLE expression signature ({sig_source})...")
    results = []
    for i, (drug_id, drug) in enumerate(drugs.items()):
        if i % 5 == 0:
            cb(10 + int(i / len(drugs) * 75), f"Scoring {drug_id}...")
        try:
            results.append(correlate_drug(drug_id, drug, drugs, signature))
        except (KeyError, TypeError, AttributeError):
            results.append({
                "drug_id": drug_id,
                "drug_name": drug.get("name", drug_id),
                "composite_score": 0.0,
                "tier": "🟢 Tier 4 — Minimal Reversal",
            })

    results.sort(key=lambda x: x["composite_score"], reverse=True)

    cb(95, "Saving results...")
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    output_path = DATA_DIR / "expression_correlations.json"
    output_path.write_text(json.dumps({
        "drugs": results,
        "total_drugs": len(results),
        "signature_upregulated": len(signature.get("upregulated", {})),
        "signature_downregulated": len(signature.get("downregulated", {})),
        "signature_source": sig_source,
        "signature_studies": num_studies,
    }, indent=2), encoding="utf-8")

    cb(100, f"Results saved to {output_path}")
    return results


# ── CLI ──────────────────────────────────────────────────────────────────


def analyze(results: list, signature=None):
    """Print statistical summary."""
    up_genes, down_genes, sig_source, num_studies = _normalize_signature(signature)

    print("\n" + "=" * 75)
    print("🧬 GENE EXPRESSION CORRELATION ANALYSIS")
    print("=" * 75)

    print("\n  SLE Expression Signature:")
    print(f"    Source:               {sig_source}")
    print(f"    GEO Studies:          {num_studies}")
    print(f"    Upregulated genes:    {len(up_genes)}")
    print(f"    Downregulated genes:  {len(down_genes)}")
    print(f"    Drugs with known pathway effects: {len(DRUG_PATHWAY_REVERSAL)}")
    print(f"    Drugs with target gene mappings: {len(DRUG_TARGET_GENES)}")

    # Score stats
    scores = [r["composite_score"] for r in results]
    print(f"\n  {len(results)} drugs scored")
    print(f"  Score range: {min(scores):.2f} - {max(scores):.2f}")
    print(f"  Mean score: {sum(scores)/len(scores):.2f}")

    tier_counts = {}
    for r in results:
        tier_counts[r["tier"]] = tier_counts.get(r["tier"], 0) + 1
    print("\n  Distribution by tier:")
    for tier in ["🔴 Tier 1 — Strong Expression Reversal", "🟠 Tier 2 — Moderate Reversal",
                  "🟡 Tier 3 — Weak Reversal", "🟢 Tier 4 — Minimal Reversal"]:
        count = tier_counts.get(tier, 0)
        label = tier.split("—")[0].strip()
        print(f"    {label}: {count} drugs")


def print_top_correlations(results: list, top_n: int = 15):
    """Print the top N drugs by expression correlation."""
    print("\n" + "=" * 75)
    print(f"🏆 TOP {top_n} EXPRESSION-CORRELATED DRUGS")
    print("=" * 75)

    for i, r in enumerate(results[:top_n], 1):
        print(f"\n  #{i} | {r['tier']}")
        print("  " + "─" * 50)
        print(f"  💊 Drug:     {r['drug_name']}")
        print(f"  📂 Category:  {r.get('category', '')}")
        print(f"  ⭐ Score:     {r['composite_score']:.2f}/10")
        print(f"     ├─ Signature Reversal:     {r['signature_reversal']}/10")
        print(f"     ├─ Target-Disease Overlap: {r['target_disease_overlap']}/10")
        print(f"     ├─ Cell Type Specificity:  {r['cell_type_specificity']}/10")
        print(f"     ├─ Expression Evidence:    {r['expression_evidence']}/10")
        print(f"     └─ Directionality:         {r['directionality']}/10")


def main():
    parser = argparse.ArgumentParser(
        description="Gene Expression Correlation — Connectivity Map approach for lupus"
    )
    parser.add_argument("--top", type=int, default=15, help="Number of top drugs to display")
    parser.add_argument("--export-html", action="store_true", help="Generate HTML report")
    parser.add_argument("--geo", action="store_true",
                        help="Use GEO-derived consensus signature (auto-fallback to curated)")
    parser.add_argument("--tissue", type=str, default=None,
                        help="Tissue to filter by (broad, pbmc_blood, kidney, skin)")
    args = parser.parse_args()

    signature_source = "geo" if args.geo else "curated"
    signature = None
    if args.geo:
        try:
            from med_research.pipeline.gene_expression.signature import get_signature
            signature = get_signature(source="auto", tissue=args.tissue)
        except Exception:
            pass

    results = compute_all_correlations(signature=signature,
                                       signature_source=signature_source,
                                       tissue=args.tissue)
    analyze(results, signature if signature else None)
    print_top_correlations(results, args.top)

    if args.export_html:
        from med_research.pipeline.gene_expression.report import generate_html_report
        _, _, sig_source, num_studies = _normalize_signature(signature)
        generate_html_report(results, signature_source=sig_source,
                            num_studies=num_studies,
                            tissue=args.tissue or "broad")
        print("\n✅ HTML report generated: gene_expression/report.html")

    return results


if __name__ == "__main__":
    main()
