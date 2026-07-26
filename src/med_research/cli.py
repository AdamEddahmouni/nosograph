#!/usr/bin/env python3
"""Medical Research Platform — Unified CLI

Run the full computational pipeline against any disease.

Usage:
    med-research run-all --disease sle          Run complete pipeline for SLE
    med-research kg --disease ra                Build KG for RA
    med-research repurpose --disease ms --top 15 Drug repurposing for MS
    med-research diseases                       List available diseases
    med-research modules                        List available pipeline modules
    med-research serve                          Start the web API server
"""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

from med_research.diseases.base import Disease
from med_research.logging_config import get_logger, setup_logging
from med_research.rate_limiter import rate_limited_sleep


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Medical Research Platform — Multi-disease drug discovery pipeline",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--verbose", "-v", action="store_true", help="Enable debug output")
    parser.add_argument("--quiet", "-q", action="store_true", help="Suppress non-error output")
    sub = parser.add_subparsers(dest="command", title="commands")

    # ── Discovery ──────────────────────────────────────────────────────
    sub.add_parser("diseases", help="List all available diseases")
    sub.add_parser("modules", help="List all available pipeline modules")

    # ── Knowledge Graph ────────────────────────────────────────────────
    kg = sub.add_parser("kg", help="Build and export the knowledge graph")
    kg.add_argument("--disease", "-d", default="sle", help="Disease ID (default: sle)")
    kg.add_argument("--analyze", action="store_true", help="Run graph analysis")
    kg.add_argument("--export", action="store_true", help="Export for web visualization")

    # ── Core Pipeline ──────────────────────────────────────────────────
    repurpose = sub.add_parser("repurpose", help="Score drug repurposing candidates")
    repurpose.add_argument("--disease", "-d", default="sle", help="Disease ID")
    repurpose.add_argument("--top", type=int, default=15, help="Top N candidates")
    repurpose.add_argument("--gene", type=str, help="Filter to specific gene")
    repurpose.add_argument("--export-html", action="store_true", help="Generate HTML report")

    bio = sub.add_parser("bioinformatics", help="Run GWAS + enrichment + PPI")
    bio.add_argument("--disease", "-d", default="sle", help="Disease ID")
    bio.add_argument("--skip-gwas", action="store_true")
    bio.add_argument("--skip-enrichment", action="store_true")
    bio.add_argument("--skip-ppi", action="store_true")
    bio.add_argument("--no-cache", action="store_true")
    bio.add_argument("--export-html", action="store_true")

    lit = sub.add_parser("literature", help="Mine PubMed for disease articles")
    lit.add_argument("--disease", "-d", default="sle", help="Disease ID")
    lit.add_argument("--max", dest="max_articles", type=int, default=200)
    lit.add_argument("--no-cache", action="store_true")
    lit.add_argument("--targeted", action="store_true")
    lit.add_argument("--extract", action="store_true")
    lit.add_argument("--export-html", action="store_true")

    screen = sub.add_parser("screening", help="Virtual drug screening")
    screen.add_argument("--disease", "-d", default="sle", help="Disease ID")
    screen.add_argument("--gene", type=str)
    screen.add_argument("--top", type=int, default=15)
    screen.add_argument("--use-vina", action="store_true")
    screen.add_argument("--export-html", action="store_true")

    trials = sub.add_parser("trials", help="Track clinical trials")
    trials.add_argument("--disease", "-d", default="sle", help="Disease ID")
    trials.add_argument("--top", type=int, default=20)
    trials.add_argument("--no-cache", action="store_true")
    trials.add_argument("--export-html", action="store_true")

    ml = sub.add_parser("ml", help="Train ML target predictor")
    ml.add_argument("--disease", "-d", default="sle", help="Disease ID")
    ml.add_argument("--top", type=int, default=15)
    ml.add_argument("--export-html", action="store_true")

    # ── Advanced Analysis ──────────────────────────────────────────────
    synergy = sub.add_parser("synergy", help="Drug combination synergy scoring")
    synergy.add_argument("--disease", "-d", default="sle", help="Disease ID")
    synergy.add_argument("--top", type=int, default=20)
    synergy.add_argument("--export-html", action="store_true")

    safety = sub.add_parser("safety", help="Adverse event safety profiling")
    safety.add_argument("--disease", "-d", default="sle", help="Disease ID")
    safety.add_argument("--drug", type=str)
    safety.add_argument("--top", type=int, default=20)
    safety.add_argument("--export-html", action="store_true")

    network = sub.add_parser("network", help="Deep network pharmacology analysis")
    network.add_argument("--disease", "-d", default="sle", help="Disease ID")
    network.add_argument("--top", type=int, default=20)
    network.add_argument("--export-html", action="store_true")

    expr = sub.add_parser("expression", help="Gene expression correlation analysis")
    expr.add_argument("--disease", "-d", default="sle", help="Disease ID")
    expr.add_argument("--top", type=int, default=15)
    expr.add_argument("--export-html", action="store_true")

    cart = sub.add_parser("cart", help="CAR-T response prediction")
    cart.add_argument("--disease", "-d", default="sle", help="Disease ID")
    cart.add_argument("--top", type=int, default=15)
    cart.add_argument("--export-html", action="store_true")

    biomarker = sub.add_parser("biomarker", help="Cross-module biomarker discovery")
    biomarker.add_argument("--disease", "-d", default="sle", help="Disease ID")
    biomarker.add_argument("--top", type=int, default=15)
    biomarker.add_argument("--export-html", action="store_true")

    # ── Evidence & Knowledge ───────────────────────────────────────────
    semantic = sub.add_parser("semantic", help="Semantic search over biomedical abstracts")
    semantic.add_argument("--query", "-q", default="treatment targets lupus", help="Search query")
    semantic.add_argument("--top", type=int, default=20)
    semantic.add_argument("--export-html", action="store_true")

    evidence = sub.add_parser("evidence", help="Multi-source evidence gathering")
    evidence.add_argument("--query", "-q", default="B cell depletion therapy lupus")
    evidence.add_argument("--sources", default="all")
    evidence.add_argument("--max", type=int, default=20)
    evidence.add_argument("--no-cache", action="store_true")
    evidence.add_argument("--top", type=int, default=15)
    evidence.add_argument("--export-html", action="store_true")

    extractor = sub.add_parser("extractor", help="LLM-powered evidence extraction")
    extractor.add_argument("--query", "-q", default="B cell depletion therapy lupus")
    extractor.add_argument("--sources", default="pubmed,preprints,clinical_trials")
    extractor.add_argument("--model", "-m", default="")
    extractor.add_argument("--max", type=int, default=20)
    extractor.add_argument("--no-cache", action="store_true")
    extractor.add_argument("--top", type=int, default=15)
    extractor.add_argument("--export-html", action="store_true")

    monitor = sub.add_parser("monitor", help="Continuous evidence monitoring")
    monitor.add_argument("--snapshot", action="store_true")
    monitor.add_argument("--diff", action="store_true")
    monitor.add_argument("--list", dest="list_snapshots", action="store_true")
    monitor.add_argument("--sources", default="pubmed,preprints,clinical_trials")
    monitor.add_argument("--max", type=int, default=10)
    monitor.add_argument("--export-html", action="store_true")

    # ── Cross-Disease ──────────────────────────────────────────────────
    cd = sub.add_parser("cross-disease", help="Cross-disease drug repurposing analysis")
    cd.add_argument("--top", type=int, default=20)
    cd.add_argument("--export-html", action="store_true")

    # ── Full Pipeline & Server ─────────────────────────────────────────
    run_all = sub.add_parser("run-all", help="Run the complete research pipeline")
    run_all.add_argument("--disease", "-d", default="sle", help="Disease ID")
    run_all.add_argument("--export-html", action="store_true", help="Generate HTML reports")
    run_all.add_argument("--no-cache", action="store_true", help="Skip caches")
    run_all.add_argument("--skip-trials", action="store_true")
    run_all.add_argument("--skip-ml", action="store_true")
    run_all.add_argument("--skip-synergy", action="store_true")

    serve = sub.add_parser("serve", help="Start the web API server")
    serve.add_argument("--host", default="0.0.0.0")
    serve.add_argument("--port", type=int, default=8000)
    serve.add_argument("--reload", action="store_true")

    test = sub.add_parser("test", help="Run the test suite")
    test.add_argument("--path", "-p", default="tests/")
    test.add_argument("--verbose", "-v", action="store_true", default=True)

    cache = sub.add_parser("cache", help="Manage pipeline caches")
    cache_sub = cache.add_subparsers(dest="cache_action")
    cache_sub.add_parser("stats", help="Show cache statistics")
    clear_cmd = cache_sub.add_parser("clear", help="Clear all caches")
    clear_cmd.add_argument("--namespace", "-n", help="Clear specific namespace")
    cleanup_cmd = cache_sub.add_parser("cleanup", help="Remove expired entries")
    cleanup_cmd.add_argument("--ttl", type=int, help="TTL in seconds")

    return parser


# ── Command Handlers ────────────────────────────────────────────────────

def _run_module(module_path: str, func_name: str, *args, **kwargs):
    """Import and call a module function directly."""
    import importlib
    mod = importlib.import_module(module_path)
    func = getattr(mod, func_name)
    return func(*args, **kwargs)


def cmd_diseases(_args):
    """List all available diseases."""
    print("\nAvailable Diseases:")
    print("-" * 60)
    for did, disease in Disease.discover().items():
        p = disease.profile
        print(f"  {did:6s}  {p.name}")
        print(f"          {p.description[:80]}...")
        print()
    return 0


def cmd_modules(_args):
    """List all available pipeline modules."""
    modules = {
        "Core": ["kg", "repurpose", "bioinformatics", "literature", "screening", "trials", "ml"],
        "Advanced": ["synergy", "safety", "network", "expression", "cart", "biomarker"],
        "Evidence": ["semantic", "evidence", "extractor", "monitor"],
        "Meta": ["cross-disease", "serve", "test"],
    }
    print("\nAvailable Pipeline Modules:")
    for category, cmds in modules.items():
        print(f"\n  {category}:")
        for c in cmds:
            print(f"    {c}")
    print()
    return 0


def cmd_kg(args):
    """Build the knowledge graph for a disease."""
    from med_research.pipeline.knowledge_graph.builder import (
        analyze_graph,
        build_graph,
        export_for_web,
    )

    disease = Disease(args.disease)
    print(f"\nBuilding {disease.profile.name} Knowledge Graph...")

    G = build_graph(args.disease)
    print(f"Graph: {G.number_of_nodes()} nodes, {G.number_of_edges()} edges")

    if args.analyze:
        analyze_graph(G)

    if args.export or not args.analyze:
        export_for_web(G, disease_id=args.disease)

    return 0


def cmd_repurpose(args):
    """Run drug repurposing analysis."""
    from med_research.pipeline.drug_repurposing.engine import DrugRepurposingEngine

    disease = Disease(args.disease)
    engine = DrugRepurposingEngine(disease.disease_id)
    results = engine.run()

    if args.export_html:
        from med_research.pipeline.drug_repurposing.report import generate_html_report
        generate_html_report(results)

    return 0


def cmd_bioinformatics(args):
    """Run bioinformatics pipeline (GWAS + Enrichment + PPI)."""
    import json
    data_dir = Path(__file__).parent / "pipeline" / "bioinformatics" / "data"
    data_dir.mkdir(parents=True, exist_ok=True)

    if not args.skip_gwas:
        print("\n[GWAS] Running GWAS analysis...")
        from med_research.pipeline.bioinformatics.gwas import run_gwas_analysis
        run_gwas_analysis()

    if not args.skip_enrichment:
        print("\n[Enrichment] Running pathway enrichment...")
        from med_research.pipeline.bioinformatics.enrichment import run_enrichment_analysis
        run_enrichment_analysis()

    if not args.skip_ppi:
        print("\n[PPI] Running PPI network analysis...")
        from med_research.pipeline.bioinformatics.ppi import run_ppi_analysis
        run_ppi_analysis()

    if args.export_html:
        from med_research.pipeline.bioinformatics.report import generate_bioinformatics_report
        gwas_path = data_dir / "gwas_results.json"
        enrich_path = data_dir / "enrichment_results.json"
        ppi_path = data_dir / "ppi_results.json"

        gwas = json.loads(gwas_path.read_text()) if gwas_path.exists() else {}
        enrich = json.loads(enrich_path.read_text()) if enrich_path.exists() else {}
        ppi = json.loads(ppi_path.read_text()) if ppi_path.exists() else {}

        generate_bioinformatics_report(
            enrich.get("enrichment_results"),
            enrich.get("gene_list"),
            enrich.get("kg_pathway_matches"),
            ppi.get("hub_scores"),
            ppi.get("crossref"),
            ppi.get("graph"),
            gwas.get("gwas_results"),
            gwas.get("crossref"),
        )
    return 0


def cmd_literature(args):
    """Run literature mining."""
    from med_research.pipeline.literature_mining.miner import LiteratureMiner

    miner = LiteratureMiner()
    results = miner.search(
        max_articles=args.max_articles,
        target_gene_queries=args.targeted,
        extract_content=args.extract,
        no_cache=args.no_cache,
    )

    if args.export_html:
        from med_research.pipeline.literature_mining.report import generate_html_report
        generate_html_report(results)

    return 0


def cmd_screening(args):
    """Run virtual drug screening."""
    from med_research.pipeline.virtual_screening.screening import VirtualScreeningEngine
    engine = VirtualScreeningEngine()
    engine.run(gene_id=args.gene, top_n=args.top, use_vina=args.use_vina)

    if args.export_html:
        from med_research.pipeline.virtual_screening.report import generate_html_report
        generate_html_report(engine.results)
    return 0


def cmd_trials(args):
    """Track clinical trials."""
    from med_research.pipeline.clinical_trials.tracker import ClinicalTrialTracker
    tracker = ClinicalTrialTracker(args.disease)
    tracker.run(no_cache=args.no_cache)

    if args.export_html:
        from med_research.pipeline.clinical_trials.report import generate_html_report
        generate_html_report(tracker.results)
    return 0


def cmd_ml(args):
    """Train ML predictor."""
    from med_research.pipeline.ml_predictor.predictor import MLPredictor
    pred = MLPredictor(args.disease)
    pred.run()

    if args.export_html:
        from med_research.pipeline.ml_predictor.report import generate_html_report
        generate_html_report(pred.results)
    return 0


def cmd_synergy(args):
    """Drug combination synergy."""
    from med_research.pipeline.drug_synergy.engine import DrugSynergyEngine
    engine = DrugSynergyEngine(args.disease)
    engine.run()

    if args.export_html:
        from med_research.pipeline.drug_synergy.report import generate_html_report
        generate_html_report(engine.results)
    return 0


def cmd_safety(args):
    """Adverse event safety profiling."""
    from med_research.pipeline.adverse_events.profiler import (
        get_drug_profile,
        get_safety_summary,
        print_analysis,
        score_all_drugs,
    )

    results = []
    if args.drug:
        profile = get_drug_profile(args.drug)
        results = [profile]
        print_analysis(results)
    else:
        results = score_all_drugs()
        summary = get_safety_summary()
        print(f"Total drugs: {summary['total_drugs']}")
        print(f"Avg safety score: {summary['avg_safety_score']:.1f}")
        print_analysis(results[:15])

    if args.export_html:
        from med_research.pipeline.adverse_events.report import generate_html_report
        generate_html_report(results)
    return 0


def cmd_network(args):
    """Network pharmacology analysis."""
    from med_research.pipeline.network_pharmacology.analyzer import NetworkAnalyzer
    ana = NetworkAnalyzer(args.disease)
    ana.run()

    if args.export_html:
        from med_research.pipeline.network_pharmacology.report import generate_html_report
        generate_html_report(ana.results)
    return 0


def cmd_expression(args):
    """Gene expression correlations."""
    from med_research.pipeline.gene_expression.correlator import ExpressionCorrelator
    corr = ExpressionCorrelator(args.disease)
    corr.run()

    if args.export_html:
        from med_research.pipeline.gene_expression.report import generate_html_report
        generate_html_report(corr.results)
    return 0


def cmd_cart(args):
    """CAR-T response prediction."""
    from med_research.pipeline.car_t_predictor.predictor import CARTPredictor
    pred = CARTPredictor(args.disease)
    pred.run()

    if args.export_html:
        from med_research.pipeline.car_t_predictor.report import generate_html_report
        generate_html_report(pred.results)
    return 0


def cmd_biomarker(args):
    """Biomarker discovery."""
    from med_research.pipeline.biomarker_discovery.discover import BiomarkerDiscoverer
    disc = BiomarkerDiscoverer(args.disease)
    disc.run()

    if args.export_html:
        from med_research.pipeline.biomarker_discovery.report import generate_html_report
        generate_html_report(disc.results)
    return 0


def cmd_semantic(args):
    """Semantic search."""
    from med_research.pipeline.semantic_search.engine import SemanticSearchEngine
    engine = SemanticSearchEngine()
    results = engine.search(args.query, top_n=args.top)

    if args.export_html:
        from med_research.pipeline.semantic_search.report import generate_html_report
        generate_html_report(results)
    return 0


def cmd_evidence(args):
    """Multi-source evidence gathering."""
    from med_research.pipeline.evidence.gatherer import gather_evidence
    results = gather_evidence(
        query=args.query,
        sources=args.sources,
        max_results=args.max,
        no_cache=args.no_cache,
    )

    if args.export_html:
        from med_research.pipeline.evidence.gatherer_report import generate_html_report
        generate_html_report(results)
    return 0


def cmd_extractor(args):
    """LLM-powered evidence extraction."""
    from med_research.pipeline.evidence.extractor import EvidenceExtractor
    extractor = EvidenceExtractor(
        model=args.model or None,
        max_articles=args.max,
        no_cache=args.no_cache,
    )
    results = extractor.extract(query=args.query, sources=args.sources)

    if args.export_html:
        from med_research.pipeline.evidence.extractor_report import generate_html_report
        generate_html_report(results)
    return 0


def cmd_monitor(args):
    """Evidence monitoring."""
    from med_research.pipeline.evidence.monitor import EvidenceMonitor
    monitor = EvidenceMonitor()

    if args.snapshot:
        monitor.take_snapshot(sources=args.sources)
    elif args.list_snapshots:
        monitor.list_snapshots()
    else:
        monitor.diff(sources=args.sources)

    if args.export_html:
        from med_research.pipeline.evidence.monitor_report import generate_html_report
        generate_html_report(monitor.last_diff)
    return 0


def cmd_cross_disease(args):
    """Cross-disease analysis."""
    from med_research.pipeline.cross_disease.analyzer import compute_cross_disease_analysis
    results = compute_cross_disease_analysis()

    if args.export_html:
        from med_research.pipeline.cross_disease.report import generate_html_report
        generate_html_report(results)
    return 0


def cmd_run_all(args):
    """Run the complete research pipeline for a disease."""
    logger = get_logger(__name__)
    disease = Disease(args.disease)
    logger.info("=" * 70)
    logger.info("MEDICAL RESEARCH PIPELINE — %s", disease.profile.name)
    logger.info("=" * 70)
    logger.info("%d steps for %s", len(PIPELINE_STEPS), disease.profile.name)

    start_time = time.time()
    errors = 0

    for i, (step_name, handler_fn) in enumerate(PIPELINE_STEPS, 1):
        logger.info("[STEP %d/%d] %s", i, len(PIPELINE_STEPS), step_name)
        try:
            handler_fn(args)
        except Exception as e:
            errors += 1
            logger.error("  %s", e)
        rate_limited_sleep(0.3)

    elapsed = time.time() - start_time
    logger.info("=" * 70)
    logger.info("Pipeline complete in %.0fs with %d error(s)", elapsed, errors)
    logger.info("=" * 70)
    return 1 if errors > 0 else 0


def _step_kg(args):
    from med_research.pipeline.knowledge_graph.builder import build_graph, export_for_web
    G = build_graph(args.disease)
    export_for_web(G, disease_id=args.disease)


def _step_repurpose(args):
    from med_research.pipeline.drug_repurposing.engine import DrugRepurposingEngine
    engine = DrugRepurposingEngine(args.disease)
    engine.run()


def _step_bioinformatics(args):
    if not args.no_cache:
        from med_research.pipeline.bioinformatics.enrichment import run_enrichment_analysis
        from med_research.pipeline.bioinformatics.gwas import run_gwas_analysis
        from med_research.pipeline.bioinformatics.ppi import run_ppi_analysis
        run_gwas_analysis()
        run_enrichment_analysis()
        run_ppi_analysis()


def _step_literature(args):
    from med_research.pipeline.literature_mining.miner import LiteratureMiner
    miner = LiteratureMiner()
    miner.search(max_articles=100, target_gene_queries=True)


def _step_screening(args):
    from med_research.pipeline.virtual_screening.screening import VirtualScreeningEngine
    engine = VirtualScreeningEngine()
    engine.run(top_n=10)


def _step_trials(args):
    from med_research.pipeline.clinical_trials.tracker import ClinicalTrialTracker
    tracker = ClinicalTrialTracker(args.disease)
    tracker.run()


def _step_ml(args):
    from med_research.pipeline.ml_predictor.predictor import MLPredictor
    pred = MLPredictor(args.disease)
    pred.run()


def _step_synergy(args):
    from med_research.pipeline.drug_synergy.engine import DrugSynergyEngine
    engine = DrugSynergyEngine(args.disease)
    engine.run()


PIPELINE_STEPS = [
    ("Knowledge Graph", _step_kg),
    ("Drug Repurposing", _step_repurpose),
    ("Bioinformatics", _step_bioinformatics),
    ("Literature Mining", _step_literature),
    ("Virtual Screening", _step_screening),
    ("Clinical Trials", _step_trials),
    ("ML Predictor", _step_ml),
    ("Drug Synergy", _step_synergy),
]


def cmd_serve(args):
    """Start the web API server."""
    import uvicorn

    from med_research.web.config import HOST, PORT
    uvicorn.run(
        "med_research.web.main:app",
        host=args.host or HOST,
        port=args.port or PORT,
        reload=args.reload,
    )
    return 0


def cmd_cache(args):
    """Manage pipeline caches."""
    from med_research.cache import CacheManager
    cache = CacheManager()

    if args.cache_action == "stats":
        stats = cache.stats()
        print(f"Total cached entries: {stats['total_entries']}")
        for ns, info in stats["namespaces"].items():
            print(f"  {ns}: {info['entries']} entries, {info['size_bytes']:,} bytes")
    elif args.cache_action == "clear":
        n = cache.clear(namespace=getattr(args, "namespace", None))
        print(f"Cleared {n} cache entries")
    elif args.cache_action == "cleanup":
        n = cache.cleanup(ttl_seconds=getattr(args, "ttl", None))
        print(f"Removed {n} expired entries")
    else:
        print("Usage: med-research cache {stats|clear|cleanup}")
    return 0


def cmd_test(args):
    """Run the test suite."""
    import subprocess
    cmd = [sys.executable, "-m", "pytest", args.path]
    if args.verbose:
        cmd.append("-v")
    return subprocess.run(cmd).returncode


def main():
    parser = _build_parser()
    args = parser.parse_args()

    if args.command is None:
        parser.print_help()
        return 0

    if args.quiet:
        setup_logging(level=40)  # ERROR only
    elif args.verbose:
        setup_logging(level=10)  # DEBUG
    else:
        setup_logging(level=20)  # INFO

    handlers = {
        "diseases": cmd_diseases,
        "modules": cmd_modules,
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
        "cross-disease": cmd_cross_disease,
        "run-all": cmd_run_all,
        "serve": cmd_serve,
        "test": cmd_test,
        "cache": cmd_cache,
    }

    handler = handlers.get(args.command)
    if handler:
        return handler(args)

    parser.print_help()
    return 0


if __name__ == "__main__":
    sys.exit(main())
