"""
Lupus Virtual Drug Screening Engine

Screens compound libraries against lupus protein targets using:
  1. Molecular property scoring (drug-likeness, Lipinski Rule of 5)
  2. Target complementarity (pathway/category matching)
  3. Molecular similarity to known SLE therapeutics
  4. Optional AutoDock Vina molecular docking (if binary available)

Scoring Dimensions (each 0-10, weighted):
  - Binding Affinity Estimate: 30%
  - Drug-likeness: 20%
  - Target Complementarity: 25%
  - Similarity to Known SLE Drugs: 15%
  - Novelty: 10%

Usage:
    python screening.py                          # Full screening
    python screening.py --gene BTK               # Screen against BTK only
    python screening.py --top 15 --export-html    # Top 15 + HTML report
"""

import argparse
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

try:
    import numpy as np  # noqa: F401
    NUMPY_AVAILABLE = True
except ImportError:
    NUMPY_AVAILABLE = False

# Add parent to path
sys.path.insert(0, str(Path(__file__).parent.parent))

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

PROJECT_ROOT = Path(__file__).parent.parent
KG_DATA_DIR = PROJECT_ROOT / "knowledge_graph" / "data"
DATA_DIR = Path(__file__).parent / "data"

# ── Optional RDKit / AutoDock Vina detection ────────────────────────────

RDKIT_AVAILABLE = False
VINA_AVAILABLE = False


def _check_rdkit():
    """Lazy-check if RDKit is installed."""
    global RDKIT_AVAILABLE
    if not RDKIT_AVAILABLE:
        try:
            import rdkit  # noqa: F401
            RDKIT_AVAILABLE = True
        except ImportError:
            pass
    return RDKIT_AVAILABLE


def _check_vina():
    """Check if AutoDock Vina binary is on PATH."""
    global VINA_AVAILABLE
    if not VINA_AVAILABLE:
        vina_path = shutil.which("vina") or shutil.which("vina.exe")
        VINA_AVAILABLE = vina_path is not None
    return VINA_AVAILABLE


# ═══════════════════════════════════════════════════════════════════════
#  Compound Library
# ═══════════════════════════════════════════════════════════════════════

# Estimated molecular properties for each KG drug
# (MW, LogP, HBD, HBA, RotatableBonds, TPSA)
# These are approximate values for demonstration; real screening would
# compute these from SMILES using RDKit.

_DRUG_PROPERTIES = {
    "belimumab":        {"mw": 147000, "logp": -10.0, "hbd": 120, "hba": 150, "rotb": 200, "tpsa": 5000},
    "anifrolumab":      {"mw": 148000, "logp": -9.5,  "hbd": 118, "hba": 148, "rotb": 195, "tpsa": 4900},
    "voclosporin":      {"mw": 1215,   "logp": 3.8,   "hbd": 5,   "hba": 14,  "rotb": 8,   "tpsa": 200},
    "hydroxychloroquine":{"mw": 336,    "logp": 3.6,   "hbd": 1,   "hba": 3,   "rotb": 8,   "tpsa": 45},
    "mycophenolate":    {"mw": 433,    "logp": 1.8,   "hbd": 2,   "hba": 9,   "rotb": 8,   "tpsa": 125},
    "cyclophosphamide": {"mw": 261,    "logp": 0.6,   "hbd": 1,   "hba": 4,   "rotb": 5,   "tpsa": 42},
    "rituximab":        {"mw": 145000, "logp": -10.5, "hbd": 115, "hba": 145, "rotb": 198, "tpsa": 4800},
    "prednisone":       {"mw": 358,    "logp": 1.5,   "hbd": 1,   "hba": 5,   "rotb": 2,   "tpsa": 74},
    "tacrolimus":       {"mw": 804,    "logp": 4.3,   "hbd": 3,   "hba": 12,  "rotb": 7,   "tpsa": 178},
    "azathioprine":     {"mw": 277,    "logp": 0.1,   "hbd": 0,   "hba": 7,   "rotb": 3,   "tpsa": 101},
    "baricitinib":      {"mw": 371,    "logp": 1.7,   "hbd": 2,   "hba": 7,   "rotb": 5,   "tpsa": 112},
    "obinutuzumab":     {"mw": 149000, "logp": -10.8, "hbd": 122, "hba": 152, "rotb": 202, "tpsa": 5100},
    "acalabrutinib":    {"mw": 465,    "logp": 2.2,   "hbd": 2,   "hba": 7,   "rotb": 5,   "tpsa": 102},
    "avacopan":         {"mw": 582,    "logp": 3.9,   "hbd": 2,   "hba": 5,   "rotb": 6,   "tpsa": 78},
    "cyclosporine":     {"mw": 1202,   "logp": 3.5,   "hbd": 5,   "hba": 14,  "rotb": 7,   "tpsa": 195},
    "dimethyl_fumarate":{"mw": 144,    "logp": 0.8,   "hbd": 0,   "hba": 4,   "rotb": 4,   "tpsa": 52},
    "iscalimab":        {"mw": 146000, "logp": -10.2, "hbd": 116, "hba": 146, "rotb": 196, "tpsa": 4950},
    "ravulizumab":      {"mw": 148000, "logp": -10.3, "hbd": 119, "hba": 149, "rotb": 199, "tpsa": 4970},
    "rozanolixizumab":  {"mw": 50000,  "logp": -7.0,  "hbd": 70,  "hba": 85,  "rotb": 80,  "tpsa": 3000},
    "tofacitinib":      {"mw": 312,    "logp": 1.2,   "hbd": 1,   "hba": 6,   "rotb": 4,   "tpsa": 89},
}


def load_kg_genes() -> dict:
    """Load gene data indexed by gene ID."""
    data = json.loads((KG_DATA_DIR / "genes.json").read_text(encoding="utf-8"))
    return {g["id"]: g for g in data["genes"]}


def load_kg_drugs() -> dict:
    """Load drug data indexed by drug ID."""
    data = json.loads((KG_DATA_DIR / "drugs.json").read_text(encoding="utf-8"))
    return {d["id"]: d for d in data["drugs"]}


def build_compound_library() -> list:
    """Build a compound library from the 20 KG drugs with estimated properties."""
    drugs = load_kg_drugs()
    library = []

    for drug_id, drug_info in drugs.items():
        props = _DRUG_PROPERTIES.get(drug_id, {})
        compound = {
            "id": drug_id,
            "name": drug_info["name"],
            "type": drug_info.get("type", ""),
            "target": drug_info.get("target", ""),
            "mechanism": drug_info.get("mechanism", ""),
            "category": drug_info.get("category", ""),
            "mw": props.get("mw", 400),
            "logp": props.get("logp", 2.0),
            "hbd": props.get("hbd", 2),
            "hba": props.get("hba", 5),
            "rotb": props.get("rotb", 5),
            "tpsa": props.get("tpsa", 100),
        }
        library.append(compound)

    return library


# ═══════════════════════════════════════════════════════════════════════
#  Scoring Functions
# ═══════════════════════════════════════════════════════════════════════

def compute_druglikeness(compound: dict) -> float:
    """
    Score drug-likeness based on Lipinski's Rule of 5.

    Returns 0-10, where 10 means fully compliant.
    """
    violations = 0
    mw = compound.get("mw", 400)
    logp = compound.get("logp", 2.0)
    hbd = compound.get("hbd", 2)
    hba = compound.get("hba", 5)

    if mw > 500 and mw < 1000:
        violations += 0.5
    elif mw >= 1000:
        violations += 2  # biologics get a penalty

    if logp > 5:
        violations += 1
    if hbd > 5:
        violations += 1
    if hba > 10:
        violations += 1

    # Biologics (mAbs) get a separate scale
    if mw > 50000:
        # Biologics have different rules (no Lipinski)
        return 5.0  # neutral — they're valid but not small-molecule

    score = max(0.0, 10.0 - violations * 2.5)
    return round(min(10.0, score), 1)


def compute_target_complementarity(compound: dict, gene_info: dict) -> float:
    """
    Score how well a compound's mechanism matches the target gene's biology.

    Uses category matching and mechanism text overlap.
    """
    gene_category = gene_info.get("category", "").lower()
    gene_function = gene_info.get("function", "").lower()
    drug_mechanism = compound.get("mechanism", "").lower()
    drug_target = compound.get("target", "").lower()
    drug_category = compound.get("category", "").lower()

    score = 2.0  # baseline

    # Category overlap
    category_keywords = {
        "b cell signaling": ["b cell", "btk", "cd20", "bcr"],
        "jak-stat signaling": ["jak", "stat", "tyk2", "cytokine"],
        "type i interferon pathway": ["interferon", "ifn", "ifnar", "tlr"],
        "nf-κb pathway": ["nf-κb", "nfkb", "proteasome"],
        "t cell signaling": ["t cell", "calcineurin", "nfat", "cd4"],
        "innate immune sensing": ["tlr", "innate", "sensor"],
        "immune complex clearance": ["fc receptor", "fcrn", "immune complex"],
    }

    for pathway_cat, keywords in category_keywords.items():
        if pathway_cat in gene_category:
            for kw in keywords:
                if kw in drug_mechanism or kw in drug_target or kw in drug_category:
                    score += 3.0
                    break
            break

    # Mechanism-to-function text overlap (simple keyword matching)
    function_keywords = gene_function.replace(",", " ").split()
    mechanism_words = set(drug_mechanism.replace(",", " ").split())
    overlap = len([w for w in function_keywords if len(w) > 4 and w in mechanism_words])
    score += min(overlap * 1.5, 5.0)

    return round(min(10.0, score), 1)


def compute_similarity_score(compound: dict, gene_info: dict) -> float:
    """
    Estimate molecular similarity to known SLE drugs for this target.

    Based on property similarity (MW, LogP) and mechanism overlap.
    """
    # Find known drugs targeting this gene or pathway
    gene_id = gene_info.get("id", "")
    try:
        candidates_data = json.loads(
            (PROJECT_ROOT / "drug_repurposing" / "data" / "candidates.json")
            .read_text(encoding="utf-8")
        )
        existing_candidates = candidates_data.get("repurposing_candidates", [])
    except (FileNotFoundError, json.JSONDecodeError):
        existing_candidates = []

    same_gene_candidates = [
        c for c in existing_candidates
        if c.get("gene_id") == gene_id
    ]

    if not same_gene_candidates:
        return 3.0  # no known reference — neutral

    # Higher score if this compound is one of the candidates
    compound_name = compound.get("name", "").lower()
    for c in same_gene_candidates:
        if c.get("drug_name", "").lower().split("(")[0].strip() in compound_name:
            return 8.0  # this compound IS a known candidate for this gene

    # Compound type similarity
    compound_category = compound.get("category", "").lower()
    for c in same_gene_candidates:
        candidate_cat = c.get("drug_category", "").lower()
        # Simple category overlap
        if compound_category and candidate_cat:
            cat_words_a = set(compound_category.split())
            cat_words_b = set(candidate_cat.split())
            overlap = len(cat_words_a & cat_words_b)
            if overlap > 0:
                return min(5.0 + overlap * 1.5, 10.0)

    return 3.0


def compute_binding_estimate(compound: dict, gene_info: dict) -> float:
    """
    Estimate binding affinity based on molecular properties.

    Simplified scoring function inspired by AutoDock Vina's scoring:
    - Steric complementarity (MW fitting)
    - Hydrogen bonding potential
    - Hydrophobic matching (LogP)

    Returns a pseudo-binding score 0-10.
    """
    mw = compound.get("mw", 400)
    logp = compound.get("logp", 2.0)
    hbd = compound.get("hbd", 2)
    hba = compound.get("hba", 5)
    tpsa = compound.get("tpsa", 100)

    score = 5.0  # baseline

    # Large biologics can't be "docked" meaningfully
    if mw > 50000:
        return 3.0

    # MW preference: ideal range 200-600 Da for small molecules
    if 200 <= mw <= 600:
        score += 2.0
    elif 100 <= mw <= 800:
        score += 1.0
    elif mw > 800:
        score -= 1.0

    # LogP: ideal range 1-4
    if 1 <= logp <= 4:
        score += 1.5
    elif 0 <= logp <= 5:
        score += 0.5

    # Hydrogen bonding: balanced HBD/HBA
    if 1 <= hbd <= 4 and 2 <= hba <= 8:
        score += 1.5

    # TPSA: ideal < 140 Å² for oral bioavailability
    if tpsa < 140:
        score += 1.0

    return round(max(0.0, min(10.0, score)), 1)


def compute_novelty_score(compound: dict, gene_info: dict) -> float:
    """
    Score how novel this compound-target pairing is.

    Already-approved SLE drugs get low novelty.
    Investigational or off-label drugs get high novelty.
    """
    compound_category = compound.get("category", "").lower()

    if "approved" in compound_category or "standard of care" in compound_category:
        if "sle" in compound_category or "lupus" in compound_category:
            return 2.0  # already used in SLE
        return 4.0  # approved for other diseases

    if "investigational" in compound_category or "phase" in compound_category:
        return 8.0  # novel for SLE

    if "off-label" in compound_category:
        return 7.0

    return 5.0


def compute_composite_score(scores: dict) -> float:
    """Compute weighted composite score from individual dimension scores."""
    weights = {
        "binding_estimate": 0.30,
        "druglikeness": 0.20,
        "target_complementarity": 0.25,
        "similarity_score": 0.15,
        "novelty_score": 0.10,
    }
    composite = sum(scores[k] * weights[k] for k in weights)
    return round(composite, 2)


# ═══════════════════════════════════════════════════════════════════════
#  AutoDock Vina Integration (Optional)
# ═══════════════════════════════════════════════════════════════════════

def run_autodock_vina(
    protein_pdb: str,
    ligand_sdf: str,
    output_dir: str,
    exhaustiveness: int = 8,
) -> dict:
    """
    Run AutoDock Vina docking if the binary is available.

    Returns docking scores or empty dict if Vina is unavailable.
    """
    if not _check_vina():
        return {}

    os.makedirs(output_dir, exist_ok=True)
    output_file = os.path.join(output_dir, "docking_output.pdbqt")

    try:
        cmd = [
            "vina",
            "--receptor", protein_pdb,
            "--ligand", ligand_sdf,
            "--out", output_file,
            "--exhaustiveness", str(exhaustiveness),
            "--num_modes", "5",
        ]
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)

        scores = []
        for line in result.stdout.split("\n"):
            if line.strip().startswith(("1", "2", "3", "4", "5")) and len(line.split()) >= 2:
                from contextlib import suppress
                with suppress(ValueError):
                    scores.append(float(line.split()[1]))

        return {
            "best_score": min(scores) if scores else None,
            "all_scores": scores,
            "output_file": output_file,
            "modes_found": len(scores),
        }

    except (subprocess.TimeoutExpired, FileNotFoundError, Exception) as e:
        print(f"   ⚠️  Vina docking error: {e}")
        return {}


def get_vina_status() -> str:
    """Get a human-readable Vina availability status."""
    if _check_vina():
        vina_path = shutil.which("vina") or shutil.which("vina.exe")
        return f"active ({vina_path})"
    return "not available (install AutoDock Vina for molecular docking)"


# ═══════════════════════════════════════════════════════════════════════
#  Screening Pipeline
# ═══════════════════════════════════════════════════════════════════════

def screen_compounds(
    target_genes: list = None,
    compound_library: list = None,
    top_n: int = 15,
    use_vina: bool = False,
) -> dict:
    """
    Run virtual screening of all compounds against all target genes.

    Args:
        target_genes: List of gene IDs to screen against (None = all untargeted)
        compound_library: Pre-built compound library (None = auto-build)
        top_n: Number of top results per target
        use_vina: Attempt AutoDock Vina docking

    Returns:
        dict with screening_results, targets, library, stats
    """
    if compound_library is None:
        compound_library = build_compound_library()

    all_genes = load_kg_genes()
    untargeted_genes = get_untargeted_genes()

    if target_genes:
        gene_ids = [g for g in target_genes if g in all_genes]
    else:
        gene_ids = [g["id"] for g in untargeted_genes]

    if not gene_ids:
        gene_ids = [g["id"] for g in untargeted_genes[:5]]

    results_per_target = {}
    all_scored = []

    for gene_id in gene_ids:
        gene_info = all_genes.get(gene_id, {"id": gene_id, "name": gene_id})
        scored_compounds = []

        for compound in compound_library:
            scores = {
                "binding_estimate": compute_binding_estimate(compound, gene_info),
                "druglikeness": compute_druglikeness(compound),
                "target_complementarity": compute_target_complementarity(compound, gene_info),
                "similarity_score": compute_similarity_score(compound, gene_info),
                "novelty_score": compute_novelty_score(compound, gene_info),
            }
            composite = compute_composite_score(scores)

            result = {
                **compound,
                **scores,
                "composite_score": composite,
                "gene_id": gene_id,
                "gene_name": gene_info.get("name", gene_id),
                "gene_category": gene_info.get("category", ""),
            }

            # Assign tier
            if composite >= 7.5:
                result["tier"] = "🔴 Tier 1 — Strong Candidate"
            elif composite >= 6.5:
                result["tier"] = "🟠 Tier 2 — Promising"
            elif composite >= 5.0:
                result["tier"] = "🟡 Tier 3 — Possible"
            else:
                result["tier"] = "🟢 Tier 4 — Low Priority"

            scored_compounds.append(result)
            all_scored.append(result)

        # Vina docking (optional)
        vina_results = {}
        if use_vina and _check_vina():
            print(f"   🧬 Running Vina docking for {gene_info.get('name', gene_id)}...")
            for compound in compound_library[:5]:  # Only top 5 per target for speed
                vina_out = run_autodock_vina(
                    protein_pdb=f"targets/{gene_id}.pdb",
                    ligand_sdf=f"ligands/{compound['id']}.sdf",
                    output_dir=str(DATA_DIR / "docking" / gene_id / compound["id"]),
                )
                if vina_out:
                    vina_results[compound["id"]] = vina_out

        # Sort and take top N
        scored_compounds.sort(key=lambda x: x["composite_score"], reverse=True)
        results_per_target[gene_id] = {
            "gene_info": gene_info,
            "top_compounds": scored_compounds[:top_n],
            "vina_results": vina_results,
            "total_screened": len(compound_library),
            "mean_score": round(
                sum(c["composite_score"] for c in scored_compounds) / len(scored_compounds), 2
            ) if scored_compounds else 0,
        }

    all_scored.sort(key=lambda x: x["composite_score"], reverse=True)

    # Stats
    n_tier1 = sum(1 for c in all_scored if c["tier"].startswith("🔴"))
    n_tier2 = sum(1 for c in all_scored if c["tier"].startswith("🟠"))

    return {
        "results_per_target": results_per_target,
        "all_results": all_scored,
        "target_genes": gene_ids,
        "compound_library": compound_library,
        "stats": {
            "targets_screened": len(gene_ids),
            "compounds_screened": len(compound_library),
            "total_pairings": len(all_scored),
            "tier1_count": n_tier1,
            "tier2_count": n_tier2,
            "vina_available": _check_vina(),
            "rdkit_available": _check_rdkit(),
            "vina_status": get_vina_status(),
        },
    }


def get_untargeted_genes() -> list:
    """Identify lupus genes with no direct targeted therapy in the KG."""
    try:
        from knowledge_graph.build_graph import build_graph
        G = build_graph()

        targeted = set()
        for _u, v, d in G.edges(data=True):
            if d.get("type") == "TARGETS" and G.nodes[v].get("type") == "gene":
                targeted.add(v)

        all_genes = load_kg_genes()
        untargeted = []
        for gene_id, gene_info in all_genes.items():
            if gene_id not in targeted:
                untargeted.append({
                    "id": gene_id,
                    "name": gene_info["name"],
                    "category": gene_info.get("category", ""),
                    "function": gene_info.get("function", ""),
                })

        # Filter out non-lupus-risk genes
        drug_target_genes = {"CD20", "IMPDH", "Calcineurin", "Glucocorticoid Receptor"}
        untargeted = [g for g in untargeted if g["id"] not in drug_target_genes]

        return untargeted
    except Exception as e:
        print(f"⚠️  Could not load KG for untargeted gene detection: {e}")
        return []


# ═══════════════════════════════════════════════════════════════════════
#  Summary & CLI
# ═══════════════════════════════════════════════════════════════════════

def print_summary(results: dict):
    """Print a summary of virtual screening results."""
    stats = results["stats"]

    print("\n" + "=" * 70)
    print("🔬 VIRTUAL DRUG SCREENING RESULTS")
    print("=" * 70)

    print(f"\n  Targets screened:        {stats['targets_screened']}")
    print(f"  Compounds screened:      {stats['compounds_screened']}")
    print(f"  Total pairings scored:   {stats['total_pairings']}")
    print(f"  Tier 1 candidates:       {stats['tier1_count']} (≥7.5)")
    print(f"  Tier 2 candidates:       {stats['tier2_count']} (6.5-7.4)")
    print(f"  AutoDock Vina:           {stats['vina_status']}")
    print(f"  RDKit:                   {'available' if stats['rdkit_available'] else 'not available'}")

    # Top results per target
    print("\n  📋 Top compound per target:")
    for gene_id, target_data in sorted(results["results_per_target"].items()):
        gene_name = target_data["gene_info"].get("name", gene_id)
        top = target_data["top_compounds"]
        if top:
            best = top[0]
            print(
                f"    • {gene_name[:45]:<47} "
                f"{best['name'][:30]:<32} "
                f"Score: {best['composite_score']:.1f}"
            )

    # Top 10 overall
    print("\n  🏆 Top 10 overall virtual screening hits:")
    for i, c in enumerate(results["all_results"][:10], 1):
        print(
            f"    {i:2}. {c['name'][:40]:<42} "
            f"→ {c['gene_name'][:25]:<27} "
            f"{c['composite_score']:.1f} ({c['tier'].split('—')[0].strip()})"
        )


def main():
    parser = argparse.ArgumentParser(
        description="Lupus Virtual Drug Screening Engine — Compound library screening"
    )
    parser.add_argument(
        "--gene", type=str,
        help="Screen against a specific gene ID (e.g. BTK, TYK2)",
    )
    parser.add_argument(
        "--top", type=int, default=15,
        help="Number of top compounds per target (default: 15)",
    )
    parser.add_argument(
        "--export-html", action="store_true",
        help="Generate HTML report",
    )
    parser.add_argument(
        "--use-vina", action="store_true",
        help="Run AutoDock Vina docking (requires Vina binary)",
    )
    args = parser.parse_args()

    print("🔄 Building compound library...")
    library = build_compound_library()
    print(f"   {len(library)} compounds loaded")

    print("🔄 Identifying untargeted lupus genes...")
    untargeted = get_untargeted_genes()
    target_ids = [g["id"] for g in untargeted]
    print(f"   {len(untargeted)} untargeted genes identified")

    if args.gene:
        target_ids = [args.gene]
        print(f"   🎯 Screening against: {args.gene}")

    print("🔄 Running virtual screening...")
    results = screen_compounds(
        target_genes=target_ids,
        compound_library=library,
        top_n=args.top,
        use_vina=args.use_vina,
    )

    print_summary(results)

    # Save results
    os.makedirs(DATA_DIR, exist_ok=True)
    output_path = DATA_DIR / "screening_results.json"
    output_path.write_text(
        json.dumps(results, indent=2, ensure_ascii=False, default=str),
        encoding="utf-8",
    )
    print(f"\n💾 Results saved to {output_path}")

    if args.export_html:
        from virtual_screening.report import generate_screening_report
        report_path = generate_screening_report(results)
        print(f"✅ HTML report generated: {report_path}")

    return results


if __name__ == "__main__":
    results = main()
