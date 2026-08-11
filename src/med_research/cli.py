#!/usr/bin/env python3
"""Medical Research Platform — Unified CLI

Run the full computational pipeline against any disease.

Usage:
    med-research run-all --disease sle          Run complete pipeline for SLE
    med-research kg --disease ra                Build KG for RA
    med-research repurpose --disease ms --top 15 Drug repurposing for MS
    med-research diseases                       List available diseases
    med-research modules                        List available pipeline modules
    med-research workspace-migrate --dry-run    Inspect persisted Workspace migrations
    med-research serve                          Start the web API server
"""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path
from typing import Any, cast

from med_research.diseases.base import Disease
from med_research.logging_config import get_logger, setup_logging
from med_research.pipeline.base import PipelineRunResult
from med_research.pipeline.results import MlPredictionResult, NetworkAnalysis
from med_research.rate_limiter import rate_limited_sleep

logger = get_logger(__name__)


def _default_pubmed_query(disease_id: str) -> str:
    """Return a disease-scoped default query for CLI search commands."""
    disease = Disease(disease_id)
    queries = disease.config.get("PUBMED_QUERIES", [])
    if queries:
        return str(queries[0])
    return f"treatment targets {disease.get_display_name()}"


def _exit_from_result(result: Any, *, context: str = "") -> int:
    """Map a failed :class:`PipelineRunResult` to a CLI exit code."""
    from med_research.exceptions import ModuleNotAvailableError
    from med_research.pipeline_errors import EXIT_RUNTIME, handle_pipeline_error

    if not isinstance(result, PipelineRunResult):
        return EXIT_RUNTIME
    if result.success:
        return 0

    prefix = f"{context}: " if context else ""
    ctx = prefix.rstrip(": ")
    for err in result.errors:
        if any(
            token in err.lower()
            for token in ("not available", "missing", "blocked", "module '")
        ):
            return handle_pipeline_error(
                ModuleNotAvailableError(err),
                logger=logger,
                context=ctx,
            )
        logger.error("%s%s", prefix, err)
    return EXIT_RUNTIME


def _data_blocked(data: Any) -> bool:
    """Return True when engine output indicates a coverage block."""
    if isinstance(data, dict):
        if data.get("status") == "blocked":
            return True
        if data.get("error") == "blocked":
            return True
        nested = data.get("results")
        if isinstance(nested, dict) and nested.get("status") == "blocked":
            return True
    return False


def _dispatch(
    module_id: str,
    disease_id: str,
    args: Any,
    *,
    export_html: bool | None = None,
    **opts: Any,
) -> PipelineRunResult[Any]:
    """Run a registry module through the unified dispatch path."""
    from med_research.pipeline.gateway import pipeline_gateway

    if export_html is None:
        export_html = bool(getattr(args, "export_html", False))
    return pipeline_gateway.execute(
        module_id,
        disease_id,
        export_html=export_html,
        **opts,
    )


def _run_all_opts(args: Any) -> dict:
    """Common kwargs forwarded from ``run-all`` flags."""
    opts: dict = {}
    if getattr(args, "no_cache", False):
        opts["use_cache"] = False
    return opts


def _trial_query(disease_id: str) -> str:
    try:
        return Disease(disease_id).get_trial_query()
    except ValueError:
        return "lupus OR SLE"


def _schema_argument_type(definition: dict) -> type | object:
    """Return an argparse converter that enforces catalog bounds."""
    type_by_schema = {"integer": int, "number": float, "string": str}
    schema_type = definition.get("type")
    if not isinstance(schema_type, str):
        schema_type = "string"
    converter = type_by_schema.get(schema_type, str)
    minimum = definition.get("minimum")
    maximum = definition.get("maximum")
    min_length = definition.get("minLength")
    max_length = definition.get("maxLength")
    if all(value is None for value in (minimum, maximum, min_length, max_length)):
        return converter

    def convert(value: str) -> Any:
        try:
            parsed = converter(value)
        except (TypeError, ValueError) as exc:
            raise argparse.ArgumentTypeError(f"invalid value: {value}") from exc
        if minimum is not None and parsed < minimum:
            raise argparse.ArgumentTypeError(f"must be >= {minimum}")
        if maximum is not None and parsed > maximum:
            raise argparse.ArgumentTypeError(f"must be <= {maximum}")
        if min_length is not None and len(parsed) < min_length:
            raise argparse.ArgumentTypeError(f"must have at least {min_length} characters")
        if max_length is not None and len(parsed) > max_length:
            raise argparse.ArgumentTypeError(f"must have at most {max_length} characters")
        return parsed

    return convert


def _add_request_schema_arguments(
    parser: argparse.ArgumentParser,
    schema: dict,
) -> None:
    """Expose catalog request properties as options on a generic CLI command."""
    for name, definition in schema.get("properties", {}).items():
        flag = f"--{name.replace('_', '-')}"
        kwargs = {
            "dest": name,
            "default": None,
            "help": definition.get("description", "Module request option"),
        }
        if definition.get("type") == "boolean":
            kwargs["action"] = "store_true"
        else:
            kwargs["type"] = _schema_argument_type(definition)
            if "enum" in definition:
                kwargs["choices"] = definition["enum"]
        parser.add_argument(flag, **kwargs)


def _add_workspace_request_arguments(parser: argparse.ArgumentParser) -> None:
    """Generate the Workspace-specific CLI options from the registry schema."""
    from med_research.pipeline.registry import module_request_schema

    schema = module_request_schema("evidence_workspace")
    for name, definition in schema["properties"].items():
        flag = f"--{name.replace('_', '-')}"
        default = definition.get("default")
        if name == "sources":
            flag_default = ",".join(definition.get("body_default", []))
        else:
            flag_default = default
        kwargs = {
            "dest": name,
            "default": flag_default,
            "required": name in schema.get("required", []),
            "help": definition.get("description", "Workspace request option"),
        }
        if name == "question":
            kwargs["option_strings"] = [flag, "-q"]
        if name == "enable_llm":
            kwargs.update(
                option_strings=["--no-llm"],
                action="store_false",
                default=default,
                help="Skip optional LLM enrichment",
            )
        elif name == "sources":
            kwargs["type"] = str
        else:
            kwargs["type"] = _schema_argument_type(definition)
            if "enum" in definition:
                kwargs["choices"] = definition["enum"]
        option_strings = kwargs.pop("option_strings", [flag])
        parser.add_argument(*option_strings, **kwargs)



def _add_registry_cli_commands(
    subparsers: argparse._SubParsersAction,
) -> None:
    """Add generic CLI entry points and refresh help from the module catalog."""
    from med_research.pipeline.registry import module_catalog

    catalog = module_catalog()
    existing = getattr(subparsers, "_name_parser_map", {})
    for entry in catalog:
        command = entry["cli_command"]
        if command in existing:
            continue
        module_parser = subparsers.add_parser(command, help=entry["cli_help"])
        module_parser.set_defaults(registry_module_id=entry["module_id"])
        module_parser.add_argument(
            "--disease", "-d", default="sle", help="Disease ID"
        )
        module_parser.add_argument(
            "--export-html", action="store_true", help="Generate an HTML report"
        )
        _add_request_schema_arguments(module_parser, entry["request_schema"])

    # Existing specialized commands keep their handlers/options, but their
    # help text is still generated from the registered adapter metadata.
    help_by_command = {entry["cli_command"]: entry["cli_help"] for entry in catalog}
    for action in getattr(subparsers, "_choices_actions", []):
        if action.dest in help_by_command:
            action.help = help_by_command[action.dest]


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
    modules_parser = sub.add_parser("modules", help="List all available pipeline modules")
    modules_parser.add_argument(
        "--json", action="store_true", help="Output registered adapter modules as JSON"
    )

    # ── Disease Management (scaffolding) ────────────────────────────────
    disease = sub.add_parser("disease", help="Scaffold and manage disease modules")
    disease_sub = disease.add_subparsers(dest="disease_action", required=True)
    dadd = disease_sub.add_parser("add", help="Scaffold a new disease from public knowledge bases")
    dadd.add_argument("disease_id", help="Disease ID (slug, e.g. crohns)")
    dadd.add_argument("--name", help="Disease name (defaults to the ID)")
    dadd.add_argument("--efo", help="Open Targets EFO id (default: auto-resolved by name)")
    dadd.add_argument("--max-genes", type=int, default=60, help="Max genes to scaffold")
    dadd.add_argument("--max-drugs", type=int, default=60, help="Max drugs to scaffold")
    dadd.add_argument("--max-pathways", type=int, default=30, help="Max pathways to scaffold")
    dadd.add_argument("--skip-gwas", action="store_true", help="Skip GWAS Catalog fetch")
    dadd.add_argument("--skip-opentargets", action="store_true", help="Skip Open Targets fetch")
    dadd.add_argument("--skip-reactome", action="store_true", help="Skip Reactome fetch")
    dadd.add_argument("--no-cache", action="store_true", help="Bypass the EFO lookup cache")
    dadd.add_argument("--overwrite", action="store_true", help="Regenerate an existing module")
    dadd.add_argument("--dry-run", action="store_true", help="Fetch + plan but do not write files")
    dref = disease_sub.add_parser(
        "refresh", help="Re-run sources and merge new genes/drugs into an existing module"
    )
    dref.add_argument("disease_id", help="Disease ID to refresh")
    dref.add_argument("--efo", help="Open Targets EFO id (default: auto-resolved by name)")
    dref.add_argument("--max-genes", type=int, default=60, help="Max genes to fetch")
    dref.add_argument("--max-drugs", type=int, default=60, help="Max drugs to fetch")
    dref.add_argument("--max-pathways", type=int, default=30, help="Max pathways to fetch")
    dref.add_argument("--skip-gwas", action="store_true", help="Skip GWAS Catalog fetch")
    dref.add_argument("--skip-opentargets", action="store_true", help="Skip Open Targets fetch")
    dref.add_argument("--skip-reactome", action="store_true", help="Skip Reactome fetch")
    dref.add_argument("--no-cache", action="store_true", help="Bypass the EFO lookup cache")
    dref.add_argument(
        "--dry-run", action="store_true", help="Fetch + merge in memory; do not write files"
    )
    dref.add_argument(
        "--prune",
        action="store_true",
        help="Remove genes/drugs no source reports on this run (confirms before applying)",
    )
    dref.add_argument(
        "--yes", "-y", action="store_true", help="Skip the --prune confirmation prompt"
    )
    dres = disease_sub.add_parser(
        "restore", help="Re-merge a pruned backup back into a module (undo --prune)"
    )
    dres.add_argument("disease_id", help="Disease ID to restore into")
    dres.add_argument(
        "--backup", help="Path to the pruned backup JSON (default: newest in data/backups/)"
    )
    dres.add_argument(
        "--dry-run", action="store_true", help="Preview the restore without writing files"
    )
    dback = disease_sub.add_parser(
        "backups", help="List pruned backups for a disease; --purge to delete old ones"
    )
    dback.add_argument("disease_id", help="Disease ID")
    dback.add_argument("--purge", action="store_true", help="Delete all but the newest backups")
    dback.add_argument(
        "--keep", type=int, default=5, help="Newest backups to keep when purging (default: 5)"
    )
    dback.add_argument(
        "--yes", "-y", action="store_true", help="Skip the --purge confirmation prompt"
    )
    dback.add_argument(
        "--dry-run", action="store_true", help="Preview the purge without deleting files"
    )
    disease_sub.add_parser("list", help="List all available diseases")
    dval = disease_sub.add_parser("validate", help="Validate a disease module's config")
    dval.add_argument("disease_id", nargs="?", help="Disease ID to validate (omit with --all)")
    dval.add_argument("--all", action="store_true", help="Validate every disease module")
    dval.add_argument(
        "--strict", action="store_true", help="Exit non-zero when config gaps are found (for CI)"
    )
    dcoverage = disease_sub.add_parser(
        "coverage", help="Show strict data and module coverage for a disease"
    )
    dcoverage.add_argument("disease_id", help="Disease ID")
    dcoverage.add_argument("--json", dest="json_path", help="Write the complete report as JSON")

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
    workspace = sub.add_parser("workspace", help="Build a cited evidence-to-hypothesis dossier")
    workspace.add_argument("--disease", "-d", default="sle", help="Disease ID (MVP: sle)")
    _add_workspace_request_arguments(workspace)
    workspace.add_argument(
        "--json", dest="json_path", help="Write complete dossier JSON to this path"
    )
    workspace.add_argument(
        "--html", dest="html_path", help="Write self-contained dossier HTML to this path"
    )

    workspace_migrate = sub.add_parser(
        "workspace-migrate",
        help="Inspect and migrate persisted Workspace SQLite runs",
    )
    workspace_migrate.add_argument(
        "--db", type=Path, help="Workspace SQLite path (defaults to WORKSPACE_DB_PATH)"
    )
    workspace_migrate.add_argument("--run-id", help="Inspect or migrate one run only")
    workspace_migrate.add_argument(
        "--limit", type=int, default=200, help="Maximum runs to inspect (default: 200)"
    )
    workspace_migrate_mode = workspace_migrate.add_mutually_exclusive_group()
    workspace_migrate_mode.add_argument(
        "--dry-run",
        action="store_true",
        help="Inspect migrations without writing rows (the default)",
    )
    workspace_migrate_mode.add_argument(
        "--apply",
        action="store_true",
        help="Rewrite legacy rows instead of only reporting them",
    )
    workspace_migrate.add_argument(
        "--json", action="store_true", help="Print the machine-readable migration report"
    )

    semantic = sub.add_parser("semantic", help="Semantic search over biomedical abstracts")
    semantic.add_argument("--disease", "-d", default="sle", help="Disease ID")
    semantic.add_argument("--query", "-q", default=None, help="Search query")
    semantic.add_argument("--top", type=int, default=20)
    semantic.add_argument("--export-html", action="store_true")

    evidence = sub.add_parser("evidence", help="Multi-source evidence gathering")
    evidence.add_argument("--disease", "-d", default="sle", help="Disease ID")
    evidence.add_argument("--query", "-q", default=None)
    evidence.add_argument("--sources", default="all")
    evidence.add_argument("--max", type=int, default=20)
    evidence.add_argument("--no-cache", action="store_true")
    evidence.add_argument("--top", type=int, default=15)
    evidence.add_argument("--export-html", action="store_true")

    extractor = sub.add_parser("extractor", help="LLM-powered evidence extraction")
    extractor.add_argument("--disease", "-d", default="sle", help="Disease ID")
    extractor.add_argument("--query", "-q", default=None)
    extractor.add_argument("--sources", default="pubmed,preprints,clinical_trials")
    extractor.add_argument(
        "--model", "-m", default="gpt-4o-mini", help="LLM model (default: gpt-4o-mini)"
    )
    extractor.add_argument("--max", type=int, default=20)
    extractor.add_argument("--no-cache", action="store_true")
    extractor.add_argument("--top", type=int, default=15)
    extractor.add_argument("--export-html", action="store_true")

    monitor = sub.add_parser("monitor", help="Continuous evidence monitoring")
    monitor.add_argument("--disease", "-d", default="sle", help="Disease ID")
    monitor.add_argument("--snapshot", action="store_true")
    monitor.add_argument("--diff", action="store_true")
    monitor.add_argument("--list", dest="list_snapshots", action="store_true")
    monitor.add_argument("--sources", default="pubmed,preprints,clinical_trials")
    monitor.add_argument("--max", type=int, default=10)
    monitor.add_argument("--export-html", action="store_true")

    # ── Cross-Disease ──────────────────────────────────────────────────
    cd = sub.add_parser("cross-disease", help="Cross-disease drug repurposing analysis")
    cd.add_argument("--disease", "-d", default="sle", help="Disease ID (for provenance/reporting)")
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
    run_all.add_argument(
        "--full",
        action="store_true",
        help=(
            "Include advanced modules (safety, network, expression, cart, biomarker, cross-disease). "
            "Evidence modules (workspace, semantic, evidence, extractor, monitor) are not included — "
            "run them via their individual CLI commands."
        ),
    )
    run_mode = run_all.add_mutually_exclusive_group()
    run_mode.add_argument(
        "--parallel",
        action="store_true",
        help="Run independent modules in parallel via registry DAG",
    )
    run_mode.add_argument(
        "--sequential",
        action="store_true",
        help="Run pipeline steps sequentially (default)",
    )

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
    migrate_cmd = cache_sub.add_parser("migrate", help="Migrate legacy flat JSON caches")
    migrate_cmd.add_argument(
        "--dry-run",
        action="store_true",
        help="Report what would be migrated without writing",
    )

    _add_registry_cli_commands(sub)
    return parser


# ── Command Handlers ────────────────────────────────────────────────────


def cmd_diseases(_args):
    """List all available diseases with config validation status."""
    logger.info("\nAvailable Diseases:")
    logger.info("-" * 60)
    issues = []
    for did, disease in Disease.discover().items():
        p = disease.profile
        logger.info(f"  {did:6s}  {p.name}")
        logger.info(f"          {p.description[:80]}...")
        for field, status in disease.validate().items():
            if status != "ok":
                issues.append(f"{did}.{field}: {status}")
        logger.info("")
    if issues:
        logger.warning("[WARN] Config gaps detected:")
        for issue in issues:
            logger.info(f"  - {issue}")
        logger.info("")
    else:
        logger.info("[OK] All disease configs complete.")
    return 0


def cmd_modules(args):
    """List all available pipeline modules."""
    import json

    from med_research.pipeline.registry import list_modules, module_catalog

    registered = list_modules()
    catalog = module_catalog()

    if args.json:
        print(json.dumps(registered, indent=2))
        return 0

    modules = {
        "Core": ["kg", "repurpose", "bioinformatics", "literature", "screening", "trials", "ml"],
        "Advanced": ["synergy", "safety", "network", "expression", "cart", "biomarker"],
        "Evidence": ["workspace", "semantic", "evidence", "extractor", "monitor"],
        "Meta": ["disease", "cross-disease", "serve", "test"],
    }
    logger.info("\nAvailable Pipeline Modules:")
    for category, cmds in modules.items():
        logger.info(f"\n  {category}:")
        for c in cmds:
            logger.info(f"    {c}")
    if registered:
        logger.info("\n  Registered adapters:")
        for entry in catalog:
            aliases = ", ".join(entry["job_aliases"])
            logger.info(
                "    %-24s  CLI: %-14s  Celery: %-28s  aliases: %s",
                entry["module_id"],
                entry["cli_command"],
                entry["celery_task"],
                aliases,
            )
    logger.info("")
    return 0


def cmd_registry_module(args):
    """Run a registry-generated generic CLI module entry point."""
    import json

    from med_research.pipeline.gateway import pipeline_gateway
    from med_research.pipeline.registry import module_request_schema

    schema = module_request_schema(args.registry_module_id)
    opts = {
        name: value
        for name in schema["properties"]
        if (value := getattr(args, name, None)) is not None
    }
    if opts.pop("no_cache", False):
        opts["use_cache"] = False

    result = pipeline_gateway.execute(
        args.registry_module_id,
        args.disease,
        export_html=bool(args.export_html),
        **opts,
    )
    if not result.success:
        return _exit_from_result(result, context=args.registry_module_id)
    logger.info(json.dumps(result.data, default=str, indent=2))
    if result.report_path is not None:
        logger.info("Report: %s", result.report_path)
    return 0


def cmd_disease(args):
    """Scaffold and manage disease modules."""
    from med_research.diseases.base import Disease

    if args.disease_action == "list":
        return cmd_diseases(args)

    if args.disease_action == "coverage":
        import json

        from med_research.diseases.coverage_report import build_coverage_report

        try:
            report = build_coverage_report(args.disease_id)
        except (ValueError, OSError, KeyError, TypeError) as exc:
            logger.error(f"❌ {exc}")
            return 1
        logger.info(f"\nCoverage: {report['name']} ({report['disease_id']})")
        logger.info(f"Fingerprint: {report['fingerprint']}")
        for module, coverage in report["modules"].items():
            label = coverage["level"].upper()
            logger.info(f"  {label:12s} {module:14s} ({coverage['status']})")
            for item in coverage.get("missing_inputs", []):
                logger.info(f"      missing: {item}")
            for item in coverage.get("limitations", []):
                logger.info(f"      limit:   {item}")
        if args.json_path:
            Path(args.json_path).write_text(
                json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8"
            )
        return 0

    if args.disease_action == "validate":
        if not args.all and not args.disease_id:
            logger.error("❌ disease validate needs a disease_id or --all")
            return 2

        if args.all:
            # Validate every disease module in one pass — the cheap CI check.
            diseases = Disease.discover()
            gaps: list[str] = []
            logger.info("\nValidating all disease modules...")
            for did in sorted(diseases):
                disease = diseases[did]
                try:
                    checks = disease.validate()
                    name = disease.profile.name
                except Exception as e:  # noqa: BLE001 — report, don't crash the health check
                    gaps.append(f"{did}: config load failed — {e}")
                    logger.warning(f"  ⚠️  {did:8s} config load failed: {e}")
                    continue
                bad = {f: s for f, s in checks.items() if s != "ok"}
                mark = "✅" if not bad else "⚠️ "
                logger.info(f"  {mark} {did:8s} {name}")
                for field, status in bad.items():
                    gaps.append(f"{did}.{field}: {status}")
                    logger.info(f"          - {field}: {status}")
            if gaps:
                n_diseases = len({g.split(".", 1)[0] for g in gaps})
                logger.warning(f"\n[WARN] Config gaps in {n_diseases} disease(s):")
                for issue in gaps:
                    logger.info(f"  - {issue}")
                logger.info("\n  Populate the gaps (e.g. `med-research disease refresh <id>`) or")
                logger.info("  scaffold them with `med-research disease add <id>`.")
                return 1 if args.strict else 0
            logger.info("\n[OK] All disease configs complete.")
            return 0

        try:
            disease = Disease(args.disease_id)
        except ValueError as e:
            logger.error(f"❌ {e}")
            return 1
        logger.info(f"\nValidating {disease.profile.name} ({disease.disease_id})...")
        ok = True
        for field, status in disease.validate().items():
            mark = "✅" if status == "ok" else "⚠️ "
            if status != "ok":
                ok = False
            logger.info(f"  {mark} {field}: {status}")
        if ok:
            logger.info("\n[OK] Config complete.")
        else:
            logger.warning("\n[WARN] Fill the gaps above before running the full pipeline.")
            return 1 if args.strict else 0
        return 0

    if args.disease_action == "add":
        import tempfile

        from med_research.diseases.scaffold import (
            print_scaffold_summary,
            scaffold_disease,
        )

        dry_run_dir = Path(tempfile.mkdtemp(prefix="scaffold_dryrun_")) if args.dry_run else None
        try:
            summary = scaffold_disease(
                disease_id=args.disease_id,
                name=args.name,
                efo_id=args.efo,
                max_genes=args.max_genes,
                max_drugs=args.max_drugs,
                max_pathways=args.max_pathways,
                use_gwas=not args.skip_gwas,
                use_opentargets=not args.skip_opentargets,
                use_reactome=not args.skip_reactome,
                overwrite=args.overwrite,
                use_cache=not args.no_cache,
                target_dir=dry_run_dir,
            )
        except (FileExistsError, ValueError) as e:
            logger.error(f"❌ {e}")
            return 1
        if args.dry_run:
            logger.info(
                f"\n[dry-run] Wrote scaffold to temp dir: {dry_run_dir} — nothing added to diseases/"
            )
        print_scaffold_summary(summary)
        return 0

    if args.disease_action == "refresh":
        from med_research.diseases.scaffold import (
            print_refresh_summary,
            refresh_disease,
        )

        # --yes bypasses the interactive prompt (and its skip-source warning), so
        # surface that footgun on stderr where CI logs will capture it.
        if (
            args.prune
            and args.yes
            and (args.skip_gwas or args.skip_opentargets or args.skip_reactome)
        ):
            print(
                "\n⚠️  WARNING: --prune with --yes and skipped sources (--skip-*) — entities\n"
                "    from skipped sources are treated as 'not reported' and will be removed.\n"
                "    A backup is written to data/backups/ before removal.\n",
                file=sys.stderr,
            )

        confirm: Any = None
        if args.prune and not args.yes and not args.dry_run:

            def _confirm_prune(plan: dict) -> bool:
                logger.info("\n" + "=" * 70)
                logger.warning("⚠️  PRUNE PLAN — entities no longer reported by any source")
                logger.info("=" * 70)
                logger.info(f"  Disease:        {plan['name']} ({plan['disease_id']})")
                logger.info(f"  Genes to remove: {len(plan['genes'])}")
                for gid in plan["genes"][:15]:
                    logger.info(f"    - {gid}")
                if len(plan["genes"]) > 15:
                    logger.info(f"    … and {len(plan['genes']) - 15} more")
                logger.info(f"  Drugs to remove: {len(plan['drugs'])}")
                for did in plan["drugs"][:15]:
                    logger.info(f"    - {did}")
                if len(plan["drugs"]) > 15:
                    logger.info(f"    … and {len(plan['drugs']) - 15} more")
                logger.info("\n  Removed entities are backed up to data/backups/ and can be")
                logger.info("  restored by merging them back into genes.json / drugs.json.")
                if args.skip_gwas or args.skip_opentargets or args.skip_reactome:
                    logger.warning("  ⚠️  You skipped sources (--skip-*): entities from those sources")
                    logger.info("      may be incorrectly flagged for removal.")
                if args.max_genes < 60 or args.max_drugs < 60:
                    logger.warning("  ⚠️  --max-genes/--max-drugs are below the defaults: entities")
                    logger.info("      beyond those limits are treated as 'not reported'.")
                try:
                    answer = input("  Proceed with prune? [y/N]: ").strip().lower()
                except (EOFError, KeyboardInterrupt):
                    logger.info("")
                    return False
                return answer in ("y", "yes")

            confirm = _confirm_prune

        try:
            summary = refresh_disease(
                disease_id=args.disease_id,
                efo_id=args.efo,
                max_genes=args.max_genes,
                max_drugs=args.max_drugs,
                max_pathways=args.max_pathways,
                use_gwas=not args.skip_gwas,
                use_opentargets=not args.skip_opentargets,
                use_reactome=not args.skip_reactome,
                use_cache=not args.no_cache,
                dry_run=args.dry_run,
                prune=args.prune,
                confirm=confirm,
            )
        except (FileNotFoundError, ValueError) as e:
            logger.error(f"❌ {e}")
            return 1
        print_refresh_summary(summary)
        return 0

    if args.disease_action == "restore":
        from med_research.diseases.scaffold import (
            print_restore_summary,
            restore_disease,
        )

        try:
            summary = restore_disease(
                disease_id=args.disease_id,
                backup_path=args.backup,
                dry_run=args.dry_run,
            )
        except (FileNotFoundError, ValueError) as e:
            logger.error(f"❌ {e}")
            return 1
        print_restore_summary(summary)
        return 0

    if args.disease_action == "backups":
        from med_research.diseases.scaffold import (
            list_backups,
            print_backups_summary,
            purge_backups,
        )

        if not args.purge:
            try:
                summary = list_backups(args.disease_id)
            except (FileNotFoundError, ValueError) as e:
                logger.error(f"❌ {e}")
                return 1
            print_backups_summary(summary)
            return 0

        confirm = None
        if not args.yes and not args.dry_run:

            def _confirm_purge(entries: list) -> bool:
                logger.info("\n" + "=" * 70)
                logger.info("🗑️  PURGE PLAN — deleting old pruned backups")
                logger.info("=" * 70)
                for e in entries:
                    logger.info(
                        f"    - {Path(e['path']).name}  "
                        f"({e['size_bytes']:,} bytes, {len(e['genes'])} genes, "
                        f"{len(e['drugs'])} drugs)"
                    )
                total = sum(e["size_bytes"] for e in entries)
                logger.info(f"\n  {len(entries)} backup(s), {total:,} bytes will be deleted.")
                logger.info("  The --keep newest backup(s) are retained.")
                try:
                    answer = input("  Proceed with purge? [y/N]: ").strip().lower()
                except (EOFError, KeyboardInterrupt):
                    logger.info("")
                    return False
                return answer in ("y", "yes")

            confirm = _confirm_purge

        try:
            summary = purge_backups(
                args.disease_id,
                keep=args.keep,
                dry_run=args.dry_run,
                confirm=confirm,
            )
        except (FileNotFoundError, ValueError) as e:
            logger.error(f"❌ {e}")
            return 1
        print_backups_summary(summary)
        return 0

    logger.info("Usage: med-research disease {add|refresh|restore|backups|list|validate|coverage}")
    return 0


def cmd_kg(args):
    """Build the knowledge graph for a disease."""
    from med_research.pipeline.knowledge_graph.builder import analyze_graph, export_for_web

    disease = Disease(args.disease)
    logger.info(f"\nBuilding {disease.profile.name} Knowledge Graph...")

    result = _dispatch("knowledge_graph", args.disease, args)
    if not result.success:
        return _exit_from_result(result, context="Knowledge graph")

    graph = result.data
    if graph is None:
        return _exit_from_result(result, context="Knowledge graph")

    logger.info(f"Graph: {graph.number_of_nodes()} nodes, {graph.number_of_edges()} edges")

    if args.analyze:
        analyze_graph(graph)

    if args.export or not args.analyze:
        export_for_web(graph, disease_id=args.disease)

    return 0


def cmd_repurpose(args):
    """Run drug repurposing analysis."""
    from med_research.pipeline.drug_repurposing.engine import analyze, print_top_candidates

    result = _dispatch("drug_repurposing", args.disease, args)
    if not result.success:
        return _exit_from_result(result, context="Drug repurposing")

    scored = result.data or []
    analyze(scored)
    print_top_candidates(scored, args.top)
    return 0


def cmd_bioinformatics(args):
    """Run bioinformatics pipeline (GWAS + Enrichment + PPI)."""
    exit_code = 0
    use_cache = not args.no_cache
    opts = {"use_cache": use_cache}

    if not args.skip_gwas:
        logger.info("\n[GWAS] Running GWAS analysis...")
        result = _dispatch("gwas", args.disease, args, **opts)
        if not result.success or _data_blocked(result.data):
            exit_code |= _exit_from_result(result, context="GWAS") or 1

    if not args.skip_enrichment:
        logger.info("\n[Enrichment] Running pathway enrichment...")
        result = _dispatch("enrichment", args.disease, args, **opts)
        if not result.success or _data_blocked(result.data):
            exit_code |= _exit_from_result(result, context="Enrichment") or 1

    if not args.skip_ppi:
        logger.info("\n[PPI] Running PPI network analysis...")
        result = _dispatch("ppi", args.disease, args, **opts)
        if not result.success or _data_blocked(result.data):
            exit_code |= _exit_from_result(result, context="PPI") or 1

    return exit_code


def cmd_literature(args):
    """Run literature mining."""
    import med_research.pipeline.literature_mining.miner as miner_mod
    from med_research.pipeline.literature_mining.miner import print_summary

    result = _dispatch(
        "literature_mining",
        args.disease,
        args,
        max_per_query=args.max_articles,
        use_cache=not args.no_cache,
        targeted=args.targeted,
        extract_content=args.extract,
    )
    if not result.success:
        return _exit_from_result(result, context="Literature mining")

    payload = result.data or {}
    results = payload.get("results", {})
    if _data_blocked(payload) or _data_blocked(results):
        coverage = results.get("coverage", {})
        logger.error(
            "❌ Literature analysis blocked for %s: %s",
            args.disease,
            ", ".join(coverage.get("missing_inputs", []))
            or "coverage contract not satisfied",
        )
        return _exit_from_result(result, context="Literature mining") or 1

    entities = payload.get("entities", {})
    candidates = payload.get("candidates", [])
    miner_mod.entities_hack = {
        gid: entities["genes"].get(gid, {"name": gid})
        for gid in results.get("gene_coverage", {})
    }
    print_summary(results, candidates, entities)
    return 0


def cmd_screening(args):
    """Run virtual drug screening."""
    from med_research.pipeline.virtual_screening.screening import print_summary

    result = _dispatch(
        "virtual_screening",
        args.disease,
        args,
        gene=args.gene,
        top=args.top,
        use_vina=args.use_vina,
    )
    if not result.success:
        return _exit_from_result(result, context="Virtual screening")

    results = result.data or {}
    if _data_blocked(results):
        logger.error(
            "❌ Screening blocked for %s: %s",
            args.disease,
            ", ".join(results.get("coverage", {}).get("missing_inputs", [])),
        )
        return 1

    print_summary(results)
    return 0


def cmd_trials(args):
    """Track clinical trials."""
    from med_research.pipeline.clinical_trials.tracker import print_summary

    query = _trial_query(args.disease)
    result = _dispatch(
        "clinical_trials",
        args.disease,
        args,
        query=query,
        max_results=args.top,
        use_cache=not args.no_cache,
    )
    if not result.success:
        return _exit_from_result(result, context="Clinical trials")

    results = result.data or {}
    print_summary(results.get("stats", {}), results.get("kg_crossref", {}))
    return 0


def cmd_ml(args):
    """Train ML predictor."""
    from med_research.pipeline.ml_predictor.predictor import print_summary

    result = _dispatch("ml_predictor", args.disease, args, top=args.top)
    if not result.success:
        return _exit_from_result(result, context="ML predictor")

    results = result.data or {}
    if isinstance(results, dict) and results.get("error"):
        logger.error("❌ %s", results["error"])
        return 0

    print_summary(cast(MlPredictionResult, results))
    return 0


def cmd_synergy(args):
    """Drug combination synergy."""
    from med_research.pipeline.drug_synergy.engine import analyze, print_top_pairs

    result = _dispatch("drug_synergy", args.disease, args)
    if not result.success:
        return _exit_from_result(result, context="Drug synergy")

    pairs = result.data or []
    analyze(pairs)
    print_top_pairs(pairs, args.top)
    return 0


def cmd_safety(args):
    """Adverse event safety profiling."""
    from med_research.pipeline.adverse_events.profiler import (
        get_drug_profile,
        get_safety_summary,
        print_analysis,
    )

    if args.drug:
        profile = get_drug_profile(args.drug, disease_id=args.disease)
        if not profile:
            logger.info(f"Drug '{args.drug}' not found in safety database.")
            return 1
        results = [profile]
        logger.info(f"\n🛡️  Safety Profile: {profile['drug_name']}")
        logger.info(f"   Disease:                  {args.disease}")
        logger.info(f"   Composite Safety Score:   {profile.get('composite_safety_score', 'N/A')}")
        logger.info(f"   Disease Symptom Overlap:  {profile.get('disease_symptom_overlap_score', 'N/A')}/10")
        logger.info(f"   Severity Burden:           {profile.get('severity_burden_score', 'N/A')}/10")
        logger.info(f"   Chronic Use Safety:        {profile.get('chronic_use_safety_score', 'N/A')}/10")
        logger.info(f"   Disease-Specific Risk:     {profile.get('disease_specific_risk_score', 'N/A')}/10")
        logger.info(f"   Black Box Warnings:        {profile.get('black_box_warnings', [])}")
        logger.info(f"   Disease Overlap AEs:       {profile.get('disease_overlap_ae', [])}")
    else:
        result = _dispatch("adverse_events", args.disease, args)
        if not result.success:
            return _exit_from_result(result, context="Safety analysis")
        results = result.data or []
        summary = get_safety_summary(disease_id=args.disease)
        logger.info(f"Total drugs ({args.disease}): {summary['total_drugs']}")
        logger.info(f"Avg safety score: {summary['avg_safety_score']:.1f}")
        print_analysis(results[:15])

    return 0


def cmd_network(args):
    """Network pharmacology analysis."""
    from med_research.pipeline.network_pharmacology.analyzer import print_analysis

    result = _dispatch("network_pharmacology", args.disease, args)
    if not result.success:
        return _exit_from_result(result, context="Network pharmacology")

    print_analysis(cast(NetworkAnalysis, result.data or {}))
    return 0


def cmd_expression(args):
    """Gene expression correlations."""
    from med_research.pipeline.gene_expression.correlator import (
        analyze,
        print_top_correlations,
    )

    result = _dispatch("gene_expression", args.disease, args, top=args.top)
    if not result.success:
        return _exit_from_result(result, context="Gene expression")

    results = result.data or []
    analyze(results, None, disease_id=args.disease)
    print_top_correlations(results, args.top)
    return 0


def cmd_cart(args):
    """CAR-T response prediction."""
    import med_research.pipeline.car_t_predictor.predictor as cart_predictor

    result = _dispatch("car_t_predictor", args.disease, args)
    if not result.success:
        return _exit_from_result(result, context="CAR-T predictor")

    results = result.data or []
    if (
        not results
        and cart_predictor.last_coverage
        and not cart_predictor.last_coverage.is_runnable
    ):
        logger.error(
            "❌ CAR-T analysis blocked for %s: %s",
            args.disease,
            ", ".join(cart_predictor.last_coverage.missing_inputs),
        )
        return 1

    cart_predictor.analyze(results)
    cart_predictor.print_top_genes(results, args.top)
    return 0


def cmd_biomarker(args):
    """Biomarker discovery."""
    from med_research.pipeline.biomarker_discovery.discover import (
        analyze,
        print_top_biomarkers,
    )

    result = _dispatch("biomarker_discovery", args.disease, args)
    if not result.success:
        return _exit_from_result(result, context="Biomarker discovery")

    results = result.data or []
    analyze(results)
    print_top_biomarkers(results, args.top)
    return 0


def cmd_workspace(args):
    """Build and export an evidence-to-hypothesis dossier."""
    from datetime import date

    from med_research.pipeline.evidence_workspace.report import dossier_to_json, render_html
    from med_research.pipeline.evidence_workspace.schemas import ResearchRequest

    def parse_date(value):
        return date.fromisoformat(value) if value else None

    request = ResearchRequest(
        disease_id=args.disease,
        question=args.question,
        sources=tuple(item.strip() for item in args.sources.split(",") if item.strip()),
        date_from=parse_date(args.date_from),
        date_to=parse_date(args.date_to),
        candidate_type=args.candidate_type,
        max_evidence=args.max_evidence,
        enable_llm=args.enable_llm,
        model=args.model,
    )
    result = _dispatch("evidence_workspace", args.disease, args, request=request)
    if not result.success:
        return _exit_from_result(result, context="Evidence workspace")

    dossier = result.data
    if args.json_path:
        Path(args.json_path).write_text(dossier_to_json(dossier), encoding="utf-8")
    if args.html_path:
        Path(args.html_path).write_text(render_html(dossier), encoding="utf-8")

    logger.info(f"Evidence workspace run: {dossier.run_id}")
    logger.info(f"Evidence records: {len(dossier.evidence)} | Claims: {len(dossier.claims)}")
    logger.info(
        f"Drug candidates: {len(dossier.drug_rankings)} | Target candidates: {len(dossier.target_rankings)}"
    )
    for warning in dossier.warnings:
        logger.info(f"Warning: {warning}")
    return 0


def cmd_workspace_migrate(args: Any) -> int:
    """Inspect Workspace migrations and optionally rewrite legacy SQLite rows."""
    import json

    from med_research.web.config import WORKSPACE_DB_PATH
    from med_research.web.services.workspace_store import WorkspaceRunStore

    path = args.db or WORKSPACE_DB_PATH
    if not path.exists():
        logger.error("Workspace database does not exist: %s", path)
        return 1

    try:
        report = WorkspaceRunStore(path).migrate_legacy_runs(
            dry_run=not args.apply,
            run_id=args.run_id,
            limit=args.limit,
        )
    except (OSError, ValueError) as exc:
        logger.error("Workspace migration failed: %s", exc)
        return 1

    if args.json:
        print(json.dumps(report, indent=2, sort_keys=True))
        return 1 if report["errors"] else 0

    mode = "dry-run" if report["dry_run"] else "applied"
    logger.info(
        "Workspace migration %s: scanned=%d legacy=%d migrated=%d unchanged=%d errors=%d",
        mode,
        report["scanned"],
        report["legacy"],
        report["migrated"],
        report["unchanged"],
        report["errors"],
    )
    for item in report["runs"]:
        if item.get("error"):
            logger.error("  %s: %s", item["run_id"], item["error"])
        elif item["needs_migration"]:
            action = "migrated" if item["migrated"] else "would migrate"
            logger.info("  %s: %s", item["run_id"], action)
    return 1 if report["errors"] else 0


def cmd_semantic(args):
    """Semantic search."""
    query = args.query or _default_pubmed_query(args.disease)
    result = _dispatch(
        "semantic_search",
        args.disease,
        args,
        query=query,
        top=args.top,
    )
    if not result.success:
        return _exit_from_result(result, context="Semantic search")
    return 0


def cmd_evidence(args):
    """Multi-source evidence gathering."""
    query = args.query or _default_pubmed_query(args.disease)
    sources = None if args.sources == "all" else [s.strip() for s in args.sources.split(",")]
    result = _dispatch(
        "evidence_gather",
        args.disease,
        args,
        query=query,
        sources=sources,
        max_per_source=args.max,
        use_cache=not args.no_cache,
    )
    if not result.success:
        return _exit_from_result(result, context="Evidence gathering")
    return 0


def cmd_extractor(args):
    """LLM-powered evidence extraction."""
    query = args.query or _default_pubmed_query(args.disease)
    sources = [s.strip() for s in args.sources.split(",")]
    result = _dispatch(
        "llm_extractor",
        args.disease,
        args,
        query=query,
        sources=sources,
        max_articles=args.max,
        model=args.model or None,
        use_cache=not args.no_cache,
    )
    if not result.success:
        return _exit_from_result(result, context="LLM extractor")
    return 0


def cmd_monitor(args):
    """Evidence monitoring."""
    from med_research.pipeline.evidence.monitor import list_snapshots

    sources = [s.strip() for s in args.sources.split(",")]

    if args.list_snapshots:
        snapshots = list_snapshots()
        logger.info(f"\n📂 Available snapshots ({len(snapshots)}):")
        for p in snapshots[:20]:
            logger.info(f"  {p.name}")
        return 0

    if args.diff or args.export_html:
        result = _dispatch(
            "evidence_monitor",
            args.disease,
            args,
            sources=sources,
            max_per_query=args.max,
            diff=True,
        )
        if not result.success:
            return _exit_from_result(result, context="Evidence monitor")

        if not args.export_html:
            from med_research.pipeline.evidence.monitor import print_diff_summary

            print_diff_summary((result.data or {}).get("diff", {}))
        return 0

    result = _dispatch(
        "evidence_monitor",
        args.disease,
        args,
        sources=sources,
        max_per_query=args.max,
    )
    if not result.success:
        return _exit_from_result(result, context="Evidence monitor")
    return 0


def cmd_cross_disease(args):
    """Cross-disease analysis."""
    from med_research.pipeline.cross_disease.analyzer import (
        analyze,
        print_repurposing,
        print_top_drugs,
    )

    result = _dispatch("cross_disease", args.disease, args)
    if not result.success:
        return _exit_from_result(result, context="Cross-disease analysis")

    results = result.data or {}
    analyze(results)
    print_top_drugs(results, top_n=args.top)
    print_repurposing(results, top_n=args.top)
    return 0


def _warn_config_gaps(disease: Disease) -> bool:
    """Warn loudly when a disease's critical pipeline configs are empty.

    Several modules silently degrade when these tables are missing — the
    CAR-T predictor scores every gene 0 and the adverse-event profiler
    treats every drug as zero-risk. Called at pipeline startup so a run
    over a stub module is never silent. Returns True when a gap was
    reported.
    """
    try:
        gaps = {f: s for f, s in disease.validate().items() if s != "ok"}
        name = disease.profile.name
    except Exception as e:  # noqa: BLE001 — a corrupt module must not crash startup
        logger = get_logger(__name__)
        logger.warning("⚠️  %s could not be validated: %s", disease.disease_id, e)
        return True
    if not gaps:
        return False
    logger = get_logger(__name__)
    impacts = {
        "CAR_T_SCORES": "CAR-T predictor will silently score every gene 0",
        "DRUG_INDUCED_LUPUS_RISK": "drug-safety assessment will silently treat all drugs as zero-risk",
        "SYMPTOMS": "disease symptom list is empty",
        "PUBMED_QUERIES": "disease-specific literature queries are empty",
    }
    logger.warning("=" * 72)
    logger.warning(
        "⚠️  %s (%s) is not fully configured — pipeline results will be degraded",
        name,
        disease.disease_id,
    )
    logger.warning("=" * 72)
    for field, status in gaps.items():
        impact = impacts.get(field, "")
        logger.warning("  - %-28s %-8s %s", field, status, impact)
    logger.warning("  Inspect with:   med-research disease validate %s", disease.disease_id)
    logger.warning("  Re-merge sources: med-research disease refresh %s", disease.disease_id)
    logger.warning("=" * 72)
    return True


def _get_pipeline_steps(args: Any) -> list[tuple[str, str | None]]:
    """Return ordered pipeline steps, honoring ``--full`` and skip flags."""

    steps = list(PIPELINE_STEPS)
    if getattr(args, "full", False):
        steps.extend(PIPELINE_STEPS_FULL)

    if getattr(args, "skip_trials", False):
        steps = [step for step in steps if step[1] != "clinical_trials"]
    if getattr(args, "skip_ml", False):
        steps = [step for step in steps if step[1] != "ml_predictor"]
    if getattr(args, "skip_synergy", False):
        steps = [step for step in steps if step[1] != "drug_synergy"]
    return steps


def _steps_to_parallel_modules(steps: list[tuple[str, str | None]]) -> list[str]:
    """Expand composite steps (bioinformatics) into registry module IDs."""

    modules: list[str] = []
    for _name, module_id in steps:
        if module_id is None:
            modules.extend(["gwas", "enrichment", "ppi"])
        else:
            modules.append(module_id)
    return modules


def _bioinformatics_module_ids() -> list[str]:
    return ["gwas", "enrichment", "ppi"]


def _run_all_module(module_id: str, args: Any) -> int:
    """Execute one registry module for ``run-all``."""
    from med_research.exceptions import MedResearchError
    from med_research.pipeline.gateway import pipeline_gateway
    from med_research.pipeline_errors import handle_pipeline_error

    opts = _run_all_opts(args)
    export_html = bool(getattr(args, "export_html", False))

    if module_id == "clinical_trials":
        opts["query"] = _trial_query(args.disease)
        opts["max_results"] = 20
    elif module_id == "literature_mining":
        opts["max_per_query"] = 20
    elif module_id in {"ml_predictor", "virtual_screening", "drug_synergy"}:
        opts["top"] = 10
    elif module_id == "adverse_events":
        opts["top"] = 15

    try:
        result = pipeline_gateway.execute(
            module_id,
            args.disease,
            export_html=export_html,
            **opts,
        )
    except MedResearchError as exc:
        return handle_pipeline_error(exc, logger=logger, context=module_id)

    if not result.success:
        return _exit_from_result(result, context=module_id)
    if _data_blocked(result.data):
        return 1

    if module_id == "knowledge_graph" and result.data is not None:
        from med_research.pipeline.knowledge_graph.builder import export_for_web

        export_for_web(result.data, disease_id=args.disease)

    return 0


def cmd_run_all(args):
    """Run the complete research pipeline for a disease."""
    from med_research.pipeline.scheduler import run_levels, validate_dag

    disease = Disease(args.disease)
    _warn_config_gaps(disease)
    steps = _get_pipeline_steps(args)
    parallel = bool(getattr(args, "parallel", False))

    logger.info("=" * 70)
    logger.info("MEDICAL RESEARCH PIPELINE — %s", disease.profile.name)
    logger.info("=" * 70)
    if parallel:
        logger.info(
            "Parallel DAG execution (%d modules) for %s",
            len(_steps_to_parallel_modules(steps)),
            disease.profile.name,
        )
    else:
        logger.info("%d steps for %s", len(steps), disease.profile.name)

    start_time = time.time()
    errors = 0

    if parallel:
        module_ids = _steps_to_parallel_modules(steps)
        levels = validate_dag(module_ids)

        def _runner(module_id: str) -> None:
            logger.info("[MODULE] %s", module_id)
            exit_code = _run_all_module(module_id, args)
            if exit_code:
                raise RuntimeError(f"Module '{module_id}' failed with exit code {exit_code}")

        for level_index, level in enumerate(levels, 1):
            logger.info(
                "[LEVEL %d/%d] %s",
                level_index,
                len(levels),
                ", ".join(level),
            )
            errors += run_levels([level], _runner, parallel=True)
    else:
        for i, (step_name, module_id) in enumerate(steps, 1):
            logger.info("[STEP %d/%d] %s", i, len(steps), step_name)
            try:
                if module_id is None:
                    for sub_id in _bioinformatics_module_ids():
                        errors += _run_all_module(sub_id, args)
                else:
                    errors += _run_all_module(module_id, args)
            except Exception as e:
                errors += 1
                logger.error("  %s", e)
            rate_limited_sleep(0.3)

    elapsed = time.time() - start_time
    logger.info("=" * 70)
    logger.info("Pipeline complete in %.0fs with %d error(s)", elapsed, errors)
    logger.info("=" * 70)
    return 1 if errors > 0 else 0


# (display name, registry module_id or None for bioinformatics composite).
# Evidence registry modules (evidence_workspace, semantic_search, evidence_gather,
# llm_extractor, evidence_monitor) are intentionally excluded — they need per-run
# queries/questions and are invoked via dedicated CLI commands, not run-all.
PIPELINE_STEPS = [
    ("Knowledge Graph", "knowledge_graph"),
    ("Drug Repurposing", "drug_repurposing"),
    ("Bioinformatics", None),
    ("Literature Mining", "literature_mining"),
    ("Virtual Screening", "virtual_screening"),
    ("Clinical Trials", "clinical_trials"),
    ("ML Predictor", "ml_predictor"),
    ("Drug Synergy", "drug_synergy"),
]

PIPELINE_STEPS_FULL = [
    ("Adverse Events", "adverse_events"),
    ("Network Pharmacology", "network_pharmacology"),
    ("Gene Expression", "gene_expression"),
    ("CAR-T Predictor", "car_t_predictor"),
    ("Biomarker Discovery", "biomarker_discovery"),
    ("Cross-Disease", "cross_disease"),
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
    from med_research.cache import CacheManager, migrate_legacy_caches

    cache = CacheManager()

    if args.cache_action == "stats":
        stats = cache.stats()
        logger.info(f"Total cached entries: {stats['total_entries']}")
        for ns, info in stats["namespaces"].items():
            logger.info(f"  {ns}: {info['entries']} entries, {info['size_bytes']:,} bytes")
    elif args.cache_action == "clear":
        n = cache.clear(namespace=getattr(args, "namespace", None))
        logger.info(f"Cleared {n} cache entries")
    elif args.cache_action == "cleanup":
        n = cache.cleanup(ttl_seconds=getattr(args, "ttl", None))
        logger.info(f"Removed {n} expired entries")
    elif args.cache_action == "migrate":
        summary = migrate_legacy_caches(
            cache,
            dry_run=getattr(args, "dry_run", False),
        )
        total = summary["total"]
        logger.info(
            "Migration complete: %d migrated, %d skipped, %d errors",
            total["migrated"],
            total["skipped"],
            total["error"],
        )
        for namespace, counts in sorted(summary["namespaces"].items()):
            if namespace == "total":
                continue
            migrated = counts.get("migrated", 0)
            skipped = counts.get("skipped", 0)
            if migrated or skipped:
                logger.info("  %s: %d migrated, %d skipped", namespace, migrated, skipped)
    else:
        logger.info("Usage: med-research cache {stats|clear|cleanup|migrate}")
    return 0


def cmd_test(args):
    """Run the test suite."""
    import subprocess

    cmd = [sys.executable, "-m", "pytest", args.path]
    if args.verbose:
        cmd.append("-v")
    return subprocess.run(cmd).returncode


def main():
    # Emoji/unicode output on Windows consoles (matches gwas.py/builder.py)
    if sys.platform == "win32":
        try:
            sys.stdout.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[union-attr]
            sys.stderr.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[union-attr]
        except (AttributeError, OSError):
            pass

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
        "disease": cmd_disease,
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
        "workspace": cmd_workspace,
        "workspace-migrate": cmd_workspace_migrate,
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
    if getattr(args, "registry_module_id", None):
        return cmd_registry_module(args)

    parser.print_help()
    return 0


if __name__ == "__main__":
    sys.exit(main())
