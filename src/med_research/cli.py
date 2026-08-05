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
    extractor.add_argument("--model", "-m", default="gpt-4o-mini",
                          help="LLM model (default: gpt-4o-mini)")
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
    """List all available diseases with config validation status."""
    print("\nAvailable Diseases:")
    print("-" * 60)
    issues = []
    for did, disease in Disease.discover().items():
        p = disease.profile
        print(f"  {did:6s}  {p.name}")
        print(f"          {p.description[:80]}...")
        for field, status in disease.validate().items():
            if status != "ok":
                issues.append(f"{did}.{field}: {status}")
        print()
    if issues:
        print("[WARN] Config gaps detected:")
        for issue in issues:
            print(f"  - {issue}")
        print()
    else:
        print("[OK] All disease configs complete.")
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
    from med_research.pipeline.drug_repurposing.engine import (
        DATA_DIR,
        analyze,
        identify_untargeted_genes,
        load_genes,
        load_json,
        load_knowledge_graph,
        print_top_candidates,
        score_candidates,
    )

    G = load_knowledge_graph(args.disease)
    genes = load_genes(args.disease)
    candidates = load_json(DATA_DIR / "candidates.json")["repurposing_candidates"]

    untargeted = identify_untargeted_genes(G)
    untargeted_ids = {g["id"] for g in untargeted}

    scored = score_candidates(G, candidates, genes)
    scored = [c for c in scored if c["gene_id"] in untargeted_ids]

    analyze(scored)
    print_top_candidates(scored, args.top)

    if args.export_html:
        from med_research.pipeline.drug_repurposing.report import generate_html_report
        generate_html_report(scored, untargeted, genes, G)

    return 0


def cmd_bioinformatics(args):
    """Run bioinformatics pipeline (GWAS + Enrichment + PPI)."""
    if not args.skip_gwas:
        print("\n[GWAS] Running GWAS analysis...")
        _run_gwas(args)

    if not args.skip_enrichment:
        print("\n[Enrichment] Running pathway enrichment...")
        _run_enrichment(args)

    if not args.skip_ppi:
        print("\n[PPI] Running PPI network analysis...")
        _run_ppi(args)

    return 0


def _run_gwas(args):
    """GWAS Catalog analysis (mirrors gwas.main())."""
    import json

    from med_research.pipeline.bioinformatics.gwas import (
        DATA_DIR,
        SLE_SEARCH_TERMS,
        analyze,
        config_load_genes,
        cross_reference_with_kg,
        extract_gene_associations,
        rate_limited_sleep,
        search_gwas_studies,
    )

    kg_genes = {g["id"]: g for g in config_load_genes()["genes"]}
    all_studies = []
    for term in SLE_SEARCH_TERMS[:2]:
        all_studies.extend(search_gwas_studies(term, max_results=15))
        rate_limited_sleep(0.5)

    seen, unique_studies = set(), []
    for s in all_studies:
        acc = s.get("accessionId")
        if acc and acc not in seen:
            seen.add(acc)
            unique_studies.append(s)

    cache_path = DATA_DIR / "gwas_cache.json"
    cached = None
    if not args.no_cache and cache_path.exists():
        try:
            cached = json.loads(cache_path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, KeyError):
            cached = None

    if cached:
        gwas_results, crossref = cached["gwas_results"], cached["crossref"]
    else:
        gwas_results = extract_gene_associations(unique_studies, max_studies=30)
        crossref = cross_reference_with_kg(gwas_results, kg_genes)
        cache_path.write_text(
            json.dumps({"gwas_results": gwas_results, "crossref": crossref},
                       indent=2, ensure_ascii=False, default=str),
            encoding="utf-8",
        )

    analyze(gwas_results, crossref, kg_genes)

    if args.export_html:
        from med_research.pipeline.bioinformatics.report import generate_bioinformatics_report
        generate_bioinformatics_report(gwas_results=gwas_results, gwas_crossref=crossref)


def _run_enrichment(args):
    """Pathway enrichment (mirrors enrichment.main())."""
    from med_research.pipeline.bioinformatics.enrichment import (
        analyze,
        cross_reference_with_kg_pathways,
        get_lupus_gene_list,
        load_kg_genes,
        load_kg_graph,
        load_pathways,
        run_enrichment,
    )

    G = load_kg_graph()
    genes = load_kg_genes()
    gene_list = get_lupus_gene_list(genes, G, untargeted_only=False)
    enrichment_results = run_enrichment(gene_list, use_cache=not args.no_cache)
    kg_pathways = load_pathways()
    kg_matches = cross_reference_with_kg_pathways(enrichment_results, kg_pathways)
    analyze(enrichment_results, gene_list, kg_matches)

    if args.export_html:
        from med_research.pipeline.bioinformatics.report import generate_bioinformatics_report
        generate_bioinformatics_report(
            enrichment_results=enrichment_results, gene_list=gene_list, kg_matches=kg_matches
        )


def _run_ppi(args):
    """PPI network analysis (mirrors ppi.main())."""
    import json

    from med_research.pipeline.bioinformatics.ppi import (
        DEFAULT_CONFIDENCE,
        analyze,
        build_ppi_network,
        compute_hub_scores,
        cross_reference_with_candidates,
        get_gene_symbols,
        load_genes,
    )

    genes = load_genes()
    gene_symbols = get_gene_symbols(genes)
    candidates_data = json.loads(
        (Path(__file__).parent / "pipeline" / "drug_repurposing" / "data" / "candidates.json")
        .read_text(encoding="utf-8")
    )
    candidates = candidates_data["repurposing_candidates"]

    G = build_ppi_network(gene_symbols, confidence=DEFAULT_CONFIDENCE, use_cache=not args.no_cache)
    if G.number_of_nodes() == 0:
        print("❌ Empty PPI network. Cannot proceed.")
        return

    hub_scores = compute_hub_scores(G)
    crossref = cross_reference_with_candidates(hub_scores, G, genes, candidates)
    analyze(hub_scores, crossref, G)

    if args.export_html:
        from med_research.pipeline.bioinformatics.report import generate_bioinformatics_report
        graph_data = {
            "nodes": [{"id": n, "symbol": G.nodes[n].get("symbol", n)} for n in G.nodes()],
            "edges": [{"source": u, "target": v, "score": d["score"]} for u, v, d in G.edges(data=True)],
        }
        generate_bioinformatics_report(hub_scores=hub_scores, ppi_crossref=crossref, ppi_graph=graph_data)


def cmd_literature(args):
    """Run literature mining."""
    import med_research.pipeline.literature_mining.miner as miner_mod
    from med_research.pipeline.literature_mining.miner import (
        mine_literature,
        print_summary,
    )

    results, entities, candidates, _ = mine_literature(
        max_per_query=args.max_articles,
        use_cache=not args.no_cache,
        targeted_candidates=args.targeted,
        extract_content=args.extract,
    )

    # print_summary reads the module-global entities_hack (set by miner.main())
    miner_mod.entities_hack = {
        gid: entities["genes"].get(gid, {"name": gid})
        for gid in results.get("gene_coverage", {})
    }
    print_summary(results, candidates, entities)

    if args.export_html:
        from med_research.pipeline.literature_mining.report import generate_literature_report
        generate_literature_report(results, entities, candidates)

    return 0


def cmd_screening(args):
    """Run virtual drug screening."""
    from med_research.pipeline.virtual_screening.screening import (
        build_compound_library,
        get_untargeted_genes,
        print_summary,
        screen_compounds,
    )

    library = build_compound_library()
    untargeted = get_untargeted_genes()
    target_ids = [args.gene] if args.gene else [g["id"] for g in untargeted]
    results = screen_compounds(
        target_genes=target_ids,
        compound_library=library,
        top_n=args.top,
        use_vina=args.use_vina,
    )
    print_summary(results)

    if args.export_html:
        from med_research.pipeline.virtual_screening.report import generate_screening_report
        generate_screening_report(results)
    return 0


def cmd_trials(args):
    """Track clinical trials."""
    from med_research.pipeline.clinical_trials.tracker import print_summary, track_trials

    results = track_trials(
        query="lupus OR SLE",
        max_results=args.top,
        use_cache=not args.no_cache,
    )
    print_summary(results["stats"], results["kg_crossref"])

    if args.export_html:
        from med_research.pipeline.clinical_trials.report import generate_ct_report
        generate_ct_report(results)
    return 0


def cmd_ml(args):
    """Train ML predictor."""
    from med_research.pipeline.knowledge_graph.builder import build_graph
    from med_research.pipeline.ml_predictor.predictor import print_summary, train_and_predict

    G = build_graph(args.disease)
    results = train_and_predict(G, top_n=args.top)
    if "error" in results:
        print(f"❌ {results['error']}")
        return 0
    print_summary(results)

    if args.export_html:
        from med_research.pipeline.ml_predictor.report import generate_ml_report
        generate_ml_report(results)
    return 0


def cmd_synergy(args):
    """Drug combination synergy."""
    from med_research.pipeline.drug_synergy.engine import (
        analyze,
        compute_synergy,
        print_top_pairs,
    )

    pairs = compute_synergy()
    analyze(pairs)
    print_top_pairs(pairs, args.top)

    if args.export_html:
        from med_research.pipeline.drug_synergy.report import generate_html_report
        generate_html_report(pairs)
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
    from med_research.pipeline.network_pharmacology.analyzer import (
        compute_all_metrics,
        print_analysis,
    )

    results = compute_all_metrics()
    print_analysis(results)

    if args.export_html:
        from med_research.pipeline.network_pharmacology.report import generate_html_report
        generate_html_report(results)
    return 0


def cmd_expression(args):
    """Gene expression correlations."""
    from med_research.pipeline.gene_expression.correlator import (
        analyze,
        compute_all_correlations,
        print_top_correlations,
    )

    results = compute_all_correlations()
    analyze(results, None)
    print_top_correlations(results, args.top)

    if args.export_html:
        from med_research.pipeline.gene_expression.report import generate_html_report
        generate_html_report(results)
    return 0


def cmd_cart(args):
    """CAR-T response prediction."""
    from med_research.pipeline.car_t_predictor.predictor import (
        analyze,
        compute_all_scores,
        print_top_genes,
    )

    results = compute_all_scores()
    analyze(results)
    print_top_genes(results, args.top)

    if args.export_html:
        from med_research.pipeline.car_t_predictor.report import generate_html_report
        generate_html_report(results)
    return 0


def cmd_biomarker(args):
    """Biomarker discovery."""
    from med_research.pipeline.biomarker_discovery.discover import (
        analyze,
        compute_biomarker_matrix,
        print_top_biomarkers,
    )

    results = compute_biomarker_matrix()
    analyze(results)
    print_top_biomarkers(results, args.top)

    if args.export_html:
        from med_research.pipeline.biomarker_discovery.report import generate_html_report
        generate_html_report(results)
    return 0


def cmd_semantic(args):
    """Semantic search."""
    from med_research.pipeline.semantic_search.engine import SemanticSearchEngine

    engine = SemanticSearchEngine()
    results = engine.search(args.query, top_k=args.top)

    if args.export_html:
        from med_research.pipeline.semantic_search.report import generate_semantic_report
        generate_semantic_report(results, args.query, engine.get_indexed_count())
    return 0


def cmd_evidence(args):
    """Multi-source evidence gathering."""
    from med_research.pipeline.evidence.gatherer import gather_evidence

    sources = None if args.sources == "all" else [s.strip() for s in args.sources.split(",")]
    results = gather_evidence(
        query=args.query,
        sources=sources,
        max_per_source=args.max,
        use_cache=not args.no_cache,
    )

    if args.export_html:
        from med_research.pipeline.evidence.gatherer_report import generate_html_report
        generate_html_report(results)
    return 0


def cmd_extractor(args):
    """LLM-powered evidence extraction."""
    from med_research.pipeline.evidence.extractor import extract_all

    sources = [s.strip() for s in args.sources.split(",")]
    results = extract_all(
        query=args.query,
        sources=sources,
        max_articles=args.max,
        model=args.model or None,
        use_cache=not args.no_cache,
    )

    if args.export_html:
        from med_research.pipeline.evidence.extractor_report import generate_html_report
        generate_html_report(results)
    return 0


def cmd_monitor(args):
    """Evidence monitoring."""
    from med_research.pipeline.evidence.monitor import (
        compare_snapshots,
        list_snapshots,
        load_latest_snapshots,
        print_diff_summary,
        take_snapshot,
    )

    sources = [s.strip() for s in args.sources.split(",")]

    if args.list_snapshots:
        snapshots = list_snapshots()
        print(f"\n📂 Available snapshots ({len(snapshots)}):")
        for p in snapshots[:20]:
            print(f"  {p.name}")
        return 0

    if args.diff or args.export_html:
        snapshots = load_latest_snapshots(2)
        if len(snapshots) < 2:
            print("⚠️  Need at least 2 snapshots. Taking baseline + new snapshot...")
            prev = take_snapshot(sources=sources, max_per_query=args.max)
            rate_limited_sleep(2)
            curr = take_snapshot(sources=sources, max_per_query=args.max)
        else:
            prev, curr = snapshots
        diff = compare_snapshots(prev, curr)
        print_diff_summary(diff)
        if args.export_html:
            from med_research.pipeline.evidence.monitor_report import generate_html_report
            generate_html_report(diff, prev, curr)
        return 0

    take_snapshot(sources=sources, max_per_query=args.max)
    return 0


def cmd_cross_disease(args):
    """Cross-disease analysis."""
    from med_research.pipeline.cross_disease.analyzer import (
        analyze,
        compute_cross_disease_analysis,
        print_repurposing,
        print_top_drugs,
    )
    results = compute_cross_disease_analysis()

    analyze(results)
    print_top_drugs(results, top_n=args.top)
    print_repurposing(results, top_n=args.top)

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
    from med_research.pipeline.drug_repurposing.engine import (
        DATA_DIR,
        analyze,
        identify_untargeted_genes,
        load_genes,
        load_json,
        load_knowledge_graph,
        print_top_candidates,
        score_candidates,
    )

    G = load_knowledge_graph(args.disease)
    genes = load_genes(args.disease)
    candidates = load_json(DATA_DIR / "candidates.json")["repurposing_candidates"]
    untargeted = identify_untargeted_genes(G)
    untargeted_ids = {g["id"] for g in untargeted}
    scored = score_candidates(G, candidates, genes)
    scored = [c for c in scored if c["gene_id"] in untargeted_ids]
    analyze(scored)
    print_top_candidates(scored, 10)


def _step_bioinformatics(args):
    if not args.no_cache:
        _run_gwas(args)
        _run_enrichment(args)
        _run_ppi(args)


def _step_literature(args):
    from med_research.pipeline.literature_mining.miner import mine_literature
    mine_literature(max_per_query=20, use_cache=True)


def _step_screening(args):
    from med_research.pipeline.virtual_screening.screening import (
        build_compound_library,
        get_untargeted_genes,
        screen_compounds,
    )

    library = build_compound_library()
    target_ids = [g["id"] for g in get_untargeted_genes()]
    screen_compounds(target_genes=target_ids, compound_library=library, top_n=10)


def _step_trials(args):
    from med_research.pipeline.clinical_trials.tracker import track_trials
    track_trials(max_results=20, use_cache=True)


def _step_ml(args):
    from med_research.pipeline.knowledge_graph.builder import build_graph
    from med_research.pipeline.ml_predictor.predictor import train_and_predict

    G = build_graph(args.disease)
    train_and_predict(G, top_n=10)


def _step_synergy(args):
    from med_research.pipeline.drug_synergy.engine import compute_synergy
    compute_synergy()


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

    from med_research.web.config import DEBUG, HOST, PORT
    logger = get_logger(__name__)
    # --reload is only honored when DEBUG=true (avoids leaking source/stack
    # traces in production where the flag may be set accidentally).
    reload_mode = bool(args.reload) and DEBUG
    if args.reload and not DEBUG:
        logger.warning("--reload ignored: set DEBUG=true to enable auto-reload")
    uvicorn.run(
        "med_research.web.main:app",
        host=args.host or HOST,
        port=args.port or PORT,
        reload=reload_mode,
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
