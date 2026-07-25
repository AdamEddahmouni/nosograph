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
    python main.py screening        Run virtual drug screening
    python main.py trials           Track lupus clinical trials
    python main.py ml               Train ML target predictor
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
    "trials": "clinical_trials/tracker.py",
    "ml": "ml_predictor/predictor.py",
    "synergy": "drug_synergy/engine.py",
    "safety": "adverse_events/profiler.py",
    "network": "network_pharmacology/analyzer.py",
    "expression": "gene_expression/correlator.py",
    "cart": "car_t_predictor/predictor.py",
    "biomarker": "biomarker_discovery/discover.py",
    "semantic": "semantic_search/engine.py",
    "evidence": "evidence_gatherer/gatherer.py",
    "extractor": "llm_extractor/extractor.py",
    "monitor": "evidence_monitor/monitor.py",
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

    print(f"\n{'=' * 70}")
    print(f">> Running: {script}")
    print(f"{'=' * 70}")

    result = subprocess.run(cmd, cwd=str(PROJECT_ROOT))
    return result.returncode


def cmd_kg(args):
    """Build and export the knowledge graph."""
    extra = []
    if args.disease:
        extra.extend(["--disease", args.disease])
    if args.analyze:
        extra.append("--analyze")
    extra.append("--export")
    return run_module(SCRIPTS["kg"], extra)


def cmd_repurpose(args):
    """Run drug repurposing analysis."""
    extra = ["--disease", args.disease]
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
            print("WARNING: GWAS module had errors, continuing...")
        time.sleep(0.5)
    else:
        print("\nSKIP: Skipping GWAS analysis")

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
            print("WARNING: Enrichment module had errors, continuing...")
        time.sleep(0.5)
    else:
        print("\nSKIP: Skipping enrichment analysis")

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
            print("WARNING: PPI module had errors, continuing...")
    else:
        print("\nSKIP: Skipping PPI analysis")

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
    if args.extract:
        extra.append("--extract")
    return run_module(SCRIPTS["literature"], extra)


def cmd_run_all(args):
    """Run the complete pipeline in dependency order (7 steps)."""
    import json
    start_time = time.time()
    errors = 0

    print("=" * 70)
    print("LUPUS RESEARCH PLATFORM -- FULL PIPELINE")
    print("=" * 70)
    print("\n7 Steps: KG → Repurpose → Bioinformatics → Literature → Screening → Trials → ML")

    # Step 1: Knowledge Graph (prerequisite for all other modules)
    print("\n[STEP 1/8] Knowledge Graph")
    rc = run_module(SCRIPTS["kg"], ["--disease", args.disease, "--analyze", "--export"])
    if rc != 0:
        print("ERROR: Knowledge graph build failed. Cannot continue.")
        return 1
    time.sleep(0.5)

    # Step 2: Drug Repurposing (depends on KG)
    print("\n[STEP 2/8] Drug Repurposing")
    extra = ["--top", "15"]
    if args.export_html:
        extra.append("--export-html")
    rc = run_module(SCRIPTS["repurpose"], extra)
    if rc != 0:
        errors += 1
        print("WARNING: Drug repurposing had errors, continuing...")
    time.sleep(0.5)

    # Step 3: Bioinformatics (depends on KG + drug candidates)
    print("\n[STEP 3/8] Bioinformatics")
    bio_extra = []
    if args.no_cache:
        bio_extra.append("--no-cache")

    for bio_module in ["gwas", "enrichment", "ppi"]:
        rc = run_module(SCRIPTS[bio_module], bio_extra)
        if rc != 0:
            errors += 1
            print(f"WARNING: {bio_module} module had errors, continuing...")
        time.sleep(0.5)

    if args.export_html:
        print("\n[INFO] Generating consolidated bioinformatics report...")
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
            print(f"   OK: Consolidated bioinformatics report: {report_path}")
        except Exception as e:
            print(f"   WARNING: Could not generate consolidated report: {e}")
            errors += 1

    # Step 4: Literature Mining (depends on KG + candidates)
    print("\n[STEP 4/8] Literature Mining")
    lit_extra = []
    if args.no_cache:
        lit_extra.append("--no-cache")
    if args.export_html:
        lit_extra.append("--export-html")
    rc = run_module(SCRIPTS["literature"], lit_extra)
    if rc != 0:
        errors += 1
        print("WARNING: Literature mining had errors, continuing...")

    # Step 5: Virtual Screening (depends on KG + drug candidates)
    print("\n[STEP 5/8] Virtual Drug Screening")
    screen_extra = []
    if args.export_html:
        screen_extra.append("--export-html")
    rc = run_module(SCRIPTS["screening"], screen_extra)
    if rc != 0:
        errors += 1
        print("WARNING: Virtual screening had errors, continuing...")

    # Step 6: Clinical Trials (depends on KG)
    print("\n[STEP 6/8] Clinical Trial Tracker")
    ct_extra = []
    if args.no_cache:
        ct_extra.append("--no-cache")
    if args.export_html:
        ct_extra.append("--export-html")
    rc = run_module(SCRIPTS["trials"], ct_extra)
    if rc != 0:
        errors += 1
        print("WARNING: Clinical trial tracker had errors, continuing...")
    time.sleep(0.5)

    # Step 7: ML Target Predictor (depends on KG)
    print("\n[STEP 7/8] ML Target Predictor")
    ml_extra = []
    if args.export_html:
        ml_extra.append("--export-html")
    rc = run_module(SCRIPTS["ml"], ml_extra)
    if rc != 0:
        errors += 1
        print("WARNING: ML predictor had errors, continuing...")

    # Step 8: Drug Synergy (depends on KG)
    print("\n[STEP 8/8] Drug Combination Synergy")
    synergy_extra = []
    if args.export_html:
        synergy_extra.append("--export-html")
    rc = run_module(SCRIPTS["synergy"], synergy_extra)
    if rc != 0:
        errors += 1
        print("WARNING: Drug synergy prediction had errors, continuing...")

    elapsed = time.time() - start_time
    print("\n" + "=" * 70)
    if errors == 0:
        print(f"Pipeline complete! ({elapsed:.0f}s elapsed, 0 errors)")
    else:
        print(f"WARNING: Pipeline finished with {errors} error(s) ({elapsed:.0f}s elapsed)")
    print("=" * 70)
    print("\nGenerated files:")
    if args.export_html:
        print("   knowledge_graph/web/graph_data.json     — Interactive KG data")
        print("   knowledge_graph/web/index.html           — Interactive KG viewer")
        print("   drug_repurposing/report.html             — Drug repurposing report")
        print("   bioinformatics/bioinformatics_report.html — Combined bioinformatics")
        print("   literature_mining/literature_report.html     — Literature mining")
        print("   virtual_screening/screening_report.html      — Virtual screening")
        print("   clinical_trials/ct_report.html               — Clinical trial tracker")
        print("   ml_predictor/ml_report.html                  — ML target predictor")
        print("   drug_synergy/report.html                     — Drug synergy report")
    else:
        print("   knowledge_graph/web/graph_data.json          — Interactive KG data")
        print("   knowledge_graph/web/index.html               — Interactive KG viewer")
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


def cmd_trials(args):
    """Run clinical trial tracker."""
    extra = []
    if args.max:
        extra.extend(["--max", str(args.max)])
    if args.query:
        extra.extend(["--query", args.query])
    if args.no_cache:
        extra.append("--no-cache")
    if args.export_html:
        extra.append("--export-html")
    return run_module(SCRIPTS["trials"], extra)


def cmd_ml(args):
    """Run ML target predictor."""
    extra = []
    if args.top:
        extra.extend(["--top", str(args.top)])
    if args.export_html:
        extra.append("--export-html")
    if getattr(args, 'no_shap', False):
        extra.append("--no-shap")
    return run_module(SCRIPTS["ml"], extra)


def cmd_synergy(args):
    """Run drug combination synergy prediction."""
    extra = []
    if args.top:
        extra.extend(["--top", str(args.top)])
    if args.export_html:
        extra.append("--export-html")
    return run_module(SCRIPTS["synergy"], extra)


def cmd_safety(args):
    """Run adverse event safety profiling."""
    extra = []
    if args.drug:
        extra.extend(["--drug", args.drug])
    if args.export_html:
        extra.append("--export-html")
    return run_module(SCRIPTS["safety"], extra)


def cmd_network(args):
    """Run network pharmacology analysis."""
    extra = []
    if args.centrality:
        extra.append("--centrality")
    if args.communities:
        extra.append("--communities")
    if args.export_html:
        extra.append("--export-html")
    return run_module(SCRIPTS["network"], extra)


def cmd_expression(args):
    """Run gene expression correlation analysis."""
    extra = []
    if args.top:
        extra.extend(["--top", str(args.top)])
    if args.export_html:
        extra.append("--export-html")
    return run_module(SCRIPTS["expression"], extra)


def cmd_cart(args):
    """Run CAR-T response prediction."""
    extra = []
    if args.top:
        extra.extend(["--top", str(args.top)])
    if args.export_html:
        extra.append("--export-html")
    return run_module(SCRIPTS["cart"], extra)


def cmd_biomarker(args):
    """Run biomarker discovery analysis."""
    extra = []
    if args.top:
        extra.extend(["--top", str(args.top)])
    if args.export_html:
        extra.append("--export-html")
    return run_module(SCRIPTS["biomarker"], extra)


def cmd_semantic(args):
    """Run semantic literature search."""
    extra = []
    if args.index:
        extra.append("--index")
    if args.query:
        extra.extend(["--query", args.query])
    if args.top:
        extra.extend(["--top", str(args.top)])
    if args.export_html:
        extra.append("--export-html")
    return run_module(SCRIPTS["semantic"], extra)


def cmd_evidence(args):
    """Run web-scale evidence gathering."""
    extra = []
    if args.query:
        extra.extend(["--query", args.query])
    if args.sources:
        extra.extend(["--sources", args.sources])
    if args.max:
        extra.extend(["--max", str(args.max)])
    if args.no_cache:
        extra.append("--no-cache")
    if args.top:
        extra.extend(["--top", str(args.top)])
    if args.export_html:
        extra.append("--export-html")
    return run_module(SCRIPTS["evidence"], extra)


def cmd_extractor(args):
    """Run LLM-powered evidence extraction."""
    extra = []
    if args.query:
        extra.extend(["--query", args.query])
    if args.sources:
        extra.extend(["--sources", args.sources])
    if args.model:
        extra.extend(["--model", args.model])
    if args.max:
        extra.extend(["--max", str(args.max)])
    if args.no_cache:
        extra.append("--no-cache")
    if args.top:
        extra.extend(["--top", str(args.top)])
    if args.export_html:
        extra.append("--export-html")
    return run_module(SCRIPTS["extractor"], extra)


def cmd_monitor(args):
    """Run continuous evidence monitoring."""
    extra = []
    if args.snapshot:
        extra.append("--snapshot")
    if args.diff:
        extra.append("--diff")
    if args.list_snapshots:
        extra.append("--list")
    if args.sources:
        extra.extend(["--sources", args.sources])
    if args.max:
        extra.extend(["--max", str(args.max)])
    if args.export_html:
        extra.append("--export-html")
    return run_module(SCRIPTS["monitor"], extra)


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
        help="Run the complete pipeline (KG > repurpose > bioinformatics > literature > screening > trials > ml)",
    )
    run_all_parser.add_argument(
        "--disease", type=str, default="sle",
        help="Disease ID to run pipeline for (default: sle)",
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
        "--disease", type=str, default="sle",
        help="Disease ID to build graph for (default: sle)",
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
        "--disease", type=str, default="sle",
        help="Disease ID (default: sle)",
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
    lit_parser.add_argument(
        "--extract", action="store_true",
        help="Pre-filter abstracts to KG-relevant sentences (reduces NER tokens ~60%%)",
    )

    # ── test ────────────────────────────────────────────────────────────
    test_parser = subparsers.add_parser(
        "test", help="Run the test suite",
    )
    test_parser.add_argument(
        "--quiet", "-q", action="store_true",
        help="Quiet mode (less output)",
    )

    # ── trials ────────────────────────────────────────────────────────
    ct_parser = subparsers.add_parser(
        "trials", help="Track lupus clinical trials from ClinicalTrials.gov",
    )
    ct_parser.add_argument(
        "--max", type=int, default=100,
        help="Max trials to fetch (default: 100)",
    )
    ct_parser.add_argument(
        "--query", type=str, default="lupus OR SLE",
        help="ClinicalTrials.gov query (default: 'lupus OR SLE')",
    )
    ct_parser.add_argument(
        "--no-cache", action="store_true",
        help="Skip cache, re-fetch from ClinicalTrials.gov",
    )
    ct_parser.add_argument(
        "--export-html", action="store_true",
        help="Generate HTML report",
    )

    # ── ml ────────────────────────────────────────────────────
    ml_parser = subparsers.add_parser(
        "ml", help="Train ML model to predict novel druggable targets",
    )
    ml_parser.add_argument(
        "--top", type=int, default=15,
        help="Number of top predicted targets (default: 15)",
    )
    ml_parser.add_argument(
        "--export-html", action="store_true",
        help="Generate HTML report with SHAP charts",
    )
    ml_parser.add_argument(
        "--no-shap", action="store_true",
        help="Skip SHAP analysis (faster)",
    )

    # ── network ────────────────────────────────────────────────────────
    network_parser = subparsers.add_parser(
        "network", help="Run network pharmacology analysis (centrality, communities)",
    )
    network_parser.add_argument(
        "--centrality", action="store_true",
        help="Show centrality metrics only",
    )
    network_parser.add_argument(
        "--communities", action="store_true",
        help="Show community detection only",
    )
    network_parser.add_argument(
        "--export-html", action="store_true",
        help="Generate HTML report",
    )

    # ── synergy ────────────────────────────────────────────────────────
    synergy_parser = subparsers.add_parser(
        "synergy", help="Predict synergistic drug combinations",
    )
    synergy_parser.add_argument(
        "--top", type=int, default=15,
        help="Number of top pairs to display (default: 15)",
    )
    synergy_parser.add_argument(
        "--export-html", action="store_true",
        help="Generate HTML report",
    )

    # ── safety ─────────────────────────────────────────────────────────
    safety_parser = subparsers.add_parser(
        "safety", help="Profile adverse events and drug safety",
    )
    safety_parser.add_argument(
        "--drug", type=str,
        help="Show safety profile for a specific drug ID",
    )
    safety_parser.add_argument(
        "--export-html", action="store_true",
        help="Generate HTML report",
    )

    # ── expression ─────────────────────────────────────────────────────
    expression_parser = subparsers.add_parser(
        "expression", help="Correlate drug mechanisms against SLE gene expression signatures",
    )
    expression_parser.add_argument(
        "--top", type=int, default=15,
        help="Number of top drugs to display (default: 15)",
    )
    expression_parser.add_argument(
        "--export-html", action="store_true",
        help="Generate HTML report",
    )

    # ── cart ───────────────────────────────────────────────────────────
    cart_parser = subparsers.add_parser(
        "cart", help="Predict CAR-T therapy suitability for lupus genes",
    )
    cart_parser.add_argument(
        "--top", type=int, default=15,
        help="Number of top genes to display (default: 15)",
    )
    cart_parser.add_argument(
        "--export-html", action="store_true",
        help="Generate HTML report",
    )

    # ── biomarker ──────────────────────────────────────────────────
    biomarker_parser = subparsers.add_parser(
        "biomarker", help="Cross-module biomarker discovery",
    )
    biomarker_parser.add_argument(
        "--top", type=int, default=15,
        help="Number of top biomarkers to display (default: 15)",
    )
    biomarker_parser.add_argument(
        "--export-html", action="store_true",
        help="Generate HTML report",
    )

    # ── semantic ───────────────────────────────────────────────────
    semantic_parser = subparsers.add_parser(
        "semantic", help="Semantic literature search using embeddings",
    )
    semantic_parser.add_argument(
        "--index", action="store_true",
        help="Index cached PubMed articles into vector DB",
    )
    semantic_parser.add_argument(
        "--query", type=str,
        help="Semantic search query (natural language)",
    )
    semantic_parser.add_argument(
        "--top", type=int, default=20,
        help="Number of results (default: 20)",
    )
    semantic_parser.add_argument(
        "--export-html", action="store_true",
        help="Generate HTML report",
    )

    # ── extractor ──────────────────────────────────────────────────
    extractor_parser = subparsers.add_parser(
        "extractor", help="Extract structured data from evidence using LLM",
    )
    extractor_parser.add_argument(
        "--query", "-q", type=str, default="B cell depletion therapy lupus",
        help="Search query (natural language)",
    )
    extractor_parser.add_argument(
        "--sources", type=str, default="pubmed,preprints,clinical_trials",
        help="Comma-separated evidence sources",
    )
    extractor_parser.add_argument(
        "--model", "-m", type=str, default="",
        help="LLM model name (default: gpt-4o-mini)",
    )
    extractor_parser.add_argument(
        "--max", type=int, default=20,
        help="Max articles to extract from (default: 20)",
    )
    extractor_parser.add_argument(
        "--no-cache", action="store_true",
        help="Skip cache, re-extract everything",
    )
    extractor_parser.add_argument(
        "--top", type=int, default=15,
        help="Number of top results to display (default: 15)",
    )
    extractor_parser.add_argument(
        "--export-html", action="store_true",
        help="Generate HTML report",
    )

    # ── evidence ───────────────────────────────────────────────────
    evidence_parser = subparsers.add_parser(
        "evidence", help="Gather evidence from multiple biomedical sources",
    )
    evidence_parser.add_argument(
        "--query", "-q", type=str, default="B cell depletion therapy lupus",
        help="Search query (natural language)",
    )
    evidence_parser.add_argument(
        "--sources", type=str, default="all",
        help="Comma-separated sources: pubmed,preprints,clinical_trials,fda_labels,patents or 'all'",
    )
    evidence_parser.add_argument(
        "--max", type=int, default=20,
        help="Max results per source (default: 20)",
    )
    evidence_parser.add_argument(
        "--no-cache", action="store_true",
        help="Skip cache, re-fetch from APIs",
    )
    evidence_parser.add_argument(
        "--top", type=int, default=15,
        help="Number of top results to display (default: 15)",
    )
    evidence_parser.add_argument(
        "--export-html", action="store_true",
        help="Generate HTML report",
    )

    # ── monitor ───────────────────────────────────────────────────
    monitor_parser = subparsers.add_parser(
        "monitor", help="Continuously monitor evidence for new publications & trials",
    )
    monitor_parser.add_argument(
        "--snapshot", action="store_true",
        help="Take a new evidence snapshot",
    )
    monitor_parser.add_argument(
        "--diff", action="store_true",
        help="Compare latest 2 snapshots",
    )
    monitor_parser.add_argument(
        "--list", dest="list_snapshots", action="store_true",
        help="List available snapshots",
    )
    monitor_parser.add_argument(
        "--sources", type=str, default="pubmed,preprints,clinical_trials",
        help="Comma-separated sources",
    )
    monitor_parser.add_argument(
        "--max", type=int, default=10,
        help="Max results per query (default: 10)",
    )
    monitor_parser.add_argument(
        "--export-html", action="store_true",
        help="Generate HTML diff report",
    )

    # ── screening ──────────────────────────────────────────────────
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
        "trials": cmd_trials,
        "ml": cmd_ml,
        "synergy": cmd_synergy,
        "safety": cmd_safety,
        "network": cmd_network,
        "expression": cmd_expression,
        "cart": cmd_cart,
        "biomarker": cmd_biomarker,
        "semantic": cmd_semantic,
        "evidence": cmd_evidence,
        "extractor": cmd_extractor,
        "monitor": cmd_monitor,
        "test": cmd_test,
    }

    handler = commands[args.command]
    return handler(args)


if __name__ == "__main__":
    sys.exit(main())
