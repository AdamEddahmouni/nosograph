#!/usr/bin/env python3
"""
Lupus Research Platform — Unified CLI

Orchestrates all modules: Knowledge Graph, Drug Repurposing,
Bioinformatics (GWAS, Enrichment, PPI), and Literature Mining.

Usage:
    python main.py run-all          Run the complete pipeline
    python main.py kg               Build & export the knowledge graph
    python main.py repurpose        Score drug repurposing candidates
    python main.py bioinformatics   Run GWAS + enrichment + PPI
    python main.py literature       Mine PubMed for SLE articles
    python main.py test             Run the test suite
"""

import argparse
import subprocess
import sys
import time
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent

# ── Module script paths relative to project root ─────────────────────────

SCRIPTS = {
    "kg": "knowledge_graph/build_graph.py",
    "repurpose": "drug_repurposing/engine.py",
    "gwas": "bioinformatics/gwas.py",
    "enrichment": "bioinformatics/enrichment.py",
    "ppi": "bioinformatics/ppi.py",
    "literature": "literature_mining/miner.py",
    "screening": "virtual_screening/screening.py",
}


def run_module(script: str, extra_args: list = None) -> int:
    """Run a module script with the given extra arguments.

    Args:
        script: Path to the Python script relative to project root.
        extra_args: List of additional CLI args to pass.

    Returns:
        Exit code (0 = success, non-zero = error).
    """
    cmd = [sys.executable, str(PROJECT_ROOT / script)]
    if extra_args:
        cmd.extend(extra_args)

    print(f"\n{'─' * 70}")
    print(f"▶  Running: {script}")
    print(f"{'─' * 70}")

    result = subprocess.run(cmd, cwd=str(PROJECT_ROOT))
    return result.returncode


def cmd_kg(args):
    """Build and export the knowledge graph."""
    extra = []
    if args.analyze:
        extra.append("--analyze")
    extra.append("--export")
    return run_module(SCRIPTS["kg"], extra)


def cmd_repurpose(args):
    """Run drug repurposing analysis."""
    extra = []
    if args.top:
        extra.extend(["--top", str(args.top)])
    if args.gene:
        extra.extend(["--gene", args.gene])
    if args.export_html:
        extra.append("--export-html")
    return run_module(SCRIPTS["repurpose"], extra)


def cmd_bioinformatics(args):
    """Run bioinformatics analyses (GWAS, enrichment, PPI)."""
    errors = 0

    # GWAS
    if not args.skip_gwas:
        extra = []
        if args.gwas_max_studies:
            extra.extend(["--max-studies", str(args.gwas_max_studies)])
        if args.no_cache:
            extra.append("--no-cache")
        if args.export_html:
            extra.append("--export-html")
        rc = run_module(SCRIPTS["gwas"], extra)
        if rc != 0:
            errors += 1
            print("⚠️  GWAS module had errors, continuing...")
        time.sleep(0.5)
    else:
        print("\n⏭️  Skipping GWAS analysis")

    # Enrichment
    if not args.skip_enrichment:
        extra = []
        if args.no_cache:
            extra.append("--no-cache")
        if args.export_html:
            extra.append("--export-html")
        rc = run_module(SCRIPTS["enrichment"], extra)
        if rc != 0:
            errors += 1
            print("⚠️  Enrichment module had errors, continuing...")
        time.sleep(0.5)
    else:
        print("\n⏭️  Skipping enrichment analysis")

    # PPI
    if not args.skip_ppi:
        extra = []
        if args.ppi_confidence:
            extra.extend(["--confidence", str(args.ppi_confidence)])
        if args.no_cache:
            extra.append("--no-cache")
        if args.export_html:
            extra.append("--export-html")
        rc = run_module(SCRIPTS["ppi"], extra)
        if rc != 0:
            errors += 1
            print("⚠️  PPI module had errors, continuing...")
    else:
        print("\n⏭️  Skipping PPI analysis")

    return 0 if errors == 0 else 1


def cmd_literature(args):
    """Run literature mining."""
    extra = []
    if args.max_articles:
        extra.extend(["--max", str(args.max_articles)])
    if args.no_cache:
        extra.append("--no-cache")
    if args.export_html:
        extra.append("--export-html")
    if args.targeted:
        extra.append("--targeted")
    return run_module(SCRIPTS["literature"], extra)


def cmd_run_all(args):
    """Run the complete pipeline in dependency order (5 steps)."""
    import json
    start_time = time.time()
    errors = 0

    print("=" * 70)
    print("🚀 LUPUS RESEARCH PLATFORM — FULL PIPELINE")
    print("=" * 70)

    # Step 1: Knowledge Graph (prerequisite for all other modules)
    print("\n📦 STEP 1/5: Knowledge Graph")
    rc = run_module(SCRIPTS["kg"], ["--analyze", "--export"])
    if rc != 0:
        print("❌ Knowledge graph build failed. Cannot continue.")
        return 1
    time.sleep(0.5)

    # Step 2: Drug Repurposing (depends on KG)
    print("\n📦 STEP 2/5: Drug Repurposing")
    extra = ["--top", "15"]
    if args.export_html:
        extra.append("--export-html")
    rc = run_module(SCRIPTS["repurpose"], extra)
    if rc != 0:
        errors += 1
        print("⚠️  Drug repurposing had errors, continuing...")
    time.sleep(0.5)

    # Step 3: Bioinformatics (depends on KG + drug candidates)
    print("\n📦 STEP 3/5: Bioinformatics")
    bio_extra = []
    if args.no_cache:
        bio_extra.append("--no-cache")

    for bio_module in ["gwas", "enrichment", "ppi"]:
        rc = run_module(SCRIPTS[bio_module], bio_extra)
        if rc != 0:
            errors += 1
            print(f"⚠️  {bio_module} module had errors, continuing...")
        time.sleep(0.5)

    if args.export_html:
        print("\n📋 Generating consolidated bioinformatics report...")
        try:
            from bioinformatics.report import generate_bioinformatics_report
            bio_data = PROJECT_ROOT / "bioinformatics" / "data"
            gwas_results = None
            gwas_crossref = None
            gwas_path = bio_data / "gwas_results.json"
            if gwas_path.exists():
                gwas = json.loads(gwas_path.read_text(encoding="utf-8"))
                gwas_results = gwas.get("gwas_results")
                gwas_crossref = gwas.get("crossref")
            enrichment_results = None
            gene_list = None
            kg_matches = None
            enrich_path = bio_data / "enrichment_results.json"
            if enrich_path.exists():
                enrich = json.loads(enrich_path.read_text(encoding="utf-8"))
                enrichment_results = enrich.get("enrichment_results")
                gene_list = enrich.get("gene_list")
                kg_matches = enrich.get("kg_pathway_matches")
            hub_scores = None
            ppi_crossref_data = None
            ppi_graph = None
            ppi_path = bio_data / "ppi_results.json"
            if ppi_path.exists():
                ppi = json.loads(ppi_path.read_text(encoding="utf-8"))
                hub_scores = ppi.get("hub_scores")
                ppi_crossref_data = ppi.get("crossref")
                ppi_graph = ppi.get("graph")
            report_path = generate_bioinformatics_report(
                enrichment_results, gene_list, kg_matches,
                hub_scores, ppi_crossref_data, ppi_graph,
                gwas_results, gwas_crossref,
            )
            print(f"   ✅ Consolidated bioinformatics report: {report_path}")
        except Exception as e:
            print(f"   ⚠️  Could not generate consolidated report: {e}")
            errors += 1

    # Step 4: Literature Mining (depends on KG + candidates)
    print("\n📦 STEP 4/5: Literature Mining")
    lit_extra = []
    if args.no_cache:
        lit_extra.append("--no-cache")
    if args.export_html:
        lit_extra.append("--export-html")
    rc = run_module(SCRIPTS["literature"], lit_extra)
    if rc != 0:
        errors += 1
        print("⚠️  Literature mining had errors, continuing...")

    # Step 5: Virtual Screening (depends on KG + drug candidates)
    print("\n📦 STEP 5/5: Virtual Drug Screening")
    screen_extra = []
    if args.export_html:
        screen_extra.append("--export-html")
    rc = run_module(SCRIPTS["screening"], screen_extra)
    if rc != 0:
        errors += 1
        print("⚠️  Virtual screening had errors, continuing...")

    elapsed = time.time() - start_time
    print("\n" + "=" * 70)
    if errors == 0:
        print(f"✅ Pipeline complete! ({elapsed:.0f}s elapsed, 0 errors)")
    else:
        print(f"⚠️  Pipeline finished with {errors} error(s) ({elapsed:.0f}s elapsed)")
    print("=" * 70)
    print("\n📂 Generated files:")
    if args.export_html:
        print("   knowledge_graph/web/graph_data.json     — Interactive KG data")
        print("   knowledge_graph/web/index.html           — Interactive KG viewer")
        print("   drug_repurposing/report.html             — Drug repurposing report")
        print("   bioinformatics/bioinformatics_report.html — Combined bioinformatics")
        print("   literature_mining/literature_report.html     — Literature mining")
        print("   virtual_screening/screening_report.html      — Virtual screening")
    else:
        print("   knowledge_graph/web/graph_data.json       — Interactive KG data")
        print("   knowledge_graph/web/index.html            — Interactive KG viewer")
    print("\n   Run with --export-html to generate all HTML reports.")
    print("=" * 70)

    return 0 if errors == 0 else 1


def cmd_screening(args):
    """Run virtual drug screening."""
    extra = []
    if args.gene:
        extra.extend(["--gene", args.gene])
    if args.top:
        extra.extend(["--top", str(args.top)])
    if args.export_html:
        extra.append("--export-html")
    if getattr(args, 'use_vina', False):
        extra.append("--use-vina")
    return run_module(SCRIPTS["screening"], extra)


def cmd_test(args):
    """Run the test suite."""
    cmd = [sys.executable, "-m", "pytest", "tests/", "-v", "--tb=short"]
    if args.quiet:
        cmd = [sys.executable, "-m", "pytest", "tests/", "-q", "--tb=line"]
    result = subprocess.run(cmd, cwd=str(PROJECT_ROOT))
    return result.returncode


def main():
    parser = argparse.ArgumentParser(
        description="Lupus Research Platform — Unified CLI",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python main.py run-all                    Run the full pipeline
  python main.py run-all --export-html      Full pipeline + all HTML reports
  python main.py kg --analyze               Build & analyze knowledge graph
  python main.py repurpose --top 10         Top 10 drug repurposing candidates
  python main.py bioinformatics --skip-gwas  Only enrichment + PPI
  python main.py literature --export-html    Mine PubMed + generate report
  python main.py screening --export-html    Virtual drug screening + report
  python main.py test                       Run all tests
  python main.py test --quiet               Quick test run
        """,
    )

    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # ── run-all ─────────────────────────────────────────────────────────
    run_all_parser = subparsers.add_parser(
        "run-all",
        help="Run the complete pipeline (KG > repurpose > bioinformatics > literature > screening)",
    )
    run_all_parser.add_argument(
        "--export-html", action="store_true",
        help="Generate HTML reports for all modules",
    )
    run_all_parser.add_argument(
        "--no-cache", action="store_true",
        help="Skip all caches, re-fetch from APIs",
    )

    # ── kg ──────────────────────────────────────────────────────────────
    kg_parser = subparsers.add_parser(
        "kg", help="Build and export the knowledge graph",
    )
    kg_parser.add_argument(
        "--analyze", action="store_true",
        help="Run full graph analysis after building",
    )

    # ── repurpose ───────────────────────────────────────────────────────
    rp_parser = subparsers.add_parser(
        "repurpose", help="Score drug repurposing candidates",
    )
    rp_parser.add_argument(
        "--top", type=int, default=15,
        help="Number of top candidates to display (default: 15)",
    )
    rp_parser.add_argument(
        "--gene", type=str,
        help="Focus analysis on a specific gene ID (e.g. BTK, TYK2)",
    )
    rp_parser.add_argument(
        "--export-html", action="store_true",
        help="Generate HTML report",
    )

    # ── bioinformatics ──────────────────────────────────────────────────
    bio_parser = subparsers.add_parser(
        "bioinformatics",
        help="Run bioinformatics analyses (GWAS, enrichment, PPI)",
    )
    bio_parser.add_argument(
        "--skip-gwas", action="store_true",
        help="Skip GWAS catalog annotation",
    )
    bio_parser.add_argument(
        "--skip-enrichment", action="store_true",
        help="Skip pathway enrichment analysis",
    )
    bio_parser.add_argument(
        "--skip-ppi", action="store_true",
        help="Skip PPI network analysis",
    )
    bio_parser.add_argument(
        "--gwas-max-studies", type=int, default=30,
        help="Max GWAS studies to fetch (default: 30)",
    )
    bio_parser.add_argument(
        "--ppi-confidence", type=float, default=0.4,
        help="STRING confidence threshold (default: 0.4)",
    )
    bio_parser.add_argument(
        "--no-cache", action="store_true",
        help="Skip cache, re-fetch from APIs",
    )
    bio_parser.add_argument(
        "--export-html", action="store_true",
        help="Generate combined HTML report",
    )

    # ── literature ──────────────────────────────────────────────────────
    lit_parser = subparsers.add_parser(
        "literature", help="Mine PubMed for SLE-related articles",
    )
    lit_parser.add_argument(
        "--max", dest="max_articles", type=int, default=30,
        help="Max articles per query (default: 30)",
    )
    lit_parser.add_argument(
        "--no-cache", action="store_true",
        help="Skip cache, re-fetch from PubMed",
    )
    lit_parser.add_argument(
        "--export-html", action="store_true",
        help="Generate HTML report",
    )
    lit_parser.add_argument(
        "--targeted", action="store_true",
        help="Also run per-candidate targeted PubMed queries (+39 queries)",
    )

    # ── test ────────────────────────────────────────────────────────────
    test_parser = subparsers.add_parser(
        "test", help="Run the test suite",
    )
    test_parser.add_argument(
        "--quiet", "-q", action="store_true",
        help="Quiet mode (less output)",
    )

    # ── screening ───────────────────────────────────────────────────────
    screen_parser = subparsers.add_parser(
        "screening", help="Run virtual drug screening against lupus targets",
    )
    screen_parser.add_argument(
        "--gene", type=str,
        help="Screen against a specific gene ID (e.g. BTK, TYK2)",
    )
    screen_parser.add_argument(
        "--top", type=int, default=15,
        help="Number of top compounds per target (default: 15)",
    )
    screen_parser.add_argument(
        "--export-html", action="store_true",
        help="Generate HTML report",
    )
    screen_parser.add_argument(
        "--use-vina", action="store_true",
        help="Run AutoDock Vina docking (requires Vina binary)",
    )

    args = parser.parse_args()

    if args.command is None:
        parser.print_help()
        return 0

    # Dispatch
    commands = {
        "run-all": cmd_run_all,
        "kg": cmd_kg,
        "repurpose": cmd_repurpose,
        "bioinformatics": cmd_bioinformatics,
        "literature": cmd_literature,
        "screening": cmd_screening,
        "test": cmd_test,
    }

    handler = commands[args.command]
    return handler(args)


if __name__ == "__main__":
    sys.exit(main())
