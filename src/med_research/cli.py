#!/usr/bin/env python3
"""NosoGraph — The Open Computational Map of Human Disease

Unified CLI for disease modules, biomedical sources, research pipelines, and the web interface.

Usage:
    nosograph --help
    nosograph diseases
    nosograph disease validate sle --strict
    nosograph serve --host 127.0.0.1 --port 8000

Legacy alias: med-research (same implementation). Python import: med_research.
Research use only — not medical advice.
"""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path
from typing import Any, cast

from med_research.diseases.base import Disease
from med_research.diseases.identifiers import add_required_disease_cli_argument
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
            token in err.lower() for token in ("not available", "missing", "blocked", "module '")
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
    from med_research.pipeline.progress import cli_progress

    if export_html is None:
        export_html = bool(getattr(args, "export_html", False))
    return pipeline_gateway.execute(
        module_id,
        disease_id,
        export_html=export_html,
        progress_callback=cli_progress,
        **opts,
    )


def _run_module_cli(
    module_id: str,
    disease_id: str,
    args: Any,
    summary_fn: Any = None,
    *,
    context: str = "",
    **opts: Any,
) -> int:
    """Standardized CLI dispatch and exit-code mapping for module commands."""
    result = _dispatch(module_id, disease_id, args, **opts)
    if not result.success:
        return _exit_from_result(result, context=context or module_id)
    if summary_fn is not None:
        data = result.data
        if data is None or _data_blocked(data):
            return _exit_from_result(result, context=context or module_id) or 1
        summary_fn(data)
    return 0


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
        add_required_disease_cli_argument(module_parser)
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
        description="NosoGraph — The Open Computational Map of Human Disease",
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
    disease_sub.add_parser("list", help="List all available diseases").add_argument(
        "--validate", action="store_true", help="Also run config validation on every module"
    )
    dval = disease_sub.add_parser("validate", help="Validate a disease module's config")
    dval.add_argument("disease_id", nargs="?", help="Disease ID to validate (omit with --all)")
    dval.add_argument("--all", action="store_true", help="Validate every disease module")
    dval.add_argument(
        "--strict", action="store_true", help="Exit non-zero when config gaps are found (for CI)"
    )
    dvalbatch = disease_sub.add_parser(
        "validate-batch",
        help="Run strict batch validation with machine-readable failure classification",
    )
    dvalbatch.add_argument(
        "--tier",
        choices=["L2", "L3", "ci_validated", "reference", "all"],
        default="reference",
        help="Corpus slice to validate (default: reference)",
    )
    dvalbatch.add_argument(
        "--limit", type=int, help="Maximum number of diseases to validate in this run"
    )
    dvalbatch.add_argument(
        "--output",
        type=Path,
        help="Write JSON report to this path (default: data/reports/validation_batch_report.json)",
    )
    dvalbatch.add_argument(
        "--strict",
        action="store_true",
        help="Exit non-zero when any module fails validation (for CI)",
    )
    dvalbatch.add_argument(
        "disease_ids",
        nargs="*",
        help="Optional explicit disease IDs (overrides --tier when provided)",
    )
    dcoverage = disease_sub.add_parser(
        "coverage", help="Show strict data and module coverage for a disease"
    )
    dcoverage.add_argument("disease_id", help="Disease ID")
    dcoverage.add_argument("--json", dest="json_path", help="Write the complete report as JSON")
    dbatch = disease_sub.add_parser(
        "batch-add", help="Scaffold multiple diseases from the curated registry"
    )
    dbatch.add_argument(
        "--category", help="Only scaffold diseases in this therapeutic category (e.g. oncology)"
    )
    dbatch.add_argument(
        "--limit", type=int, help="Maximum number of diseases to scaffold in this run"
    )
    dbatch.add_argument("--max-genes", type=int, default=60, help="Max genes per disease")
    dbatch.add_argument("--max-drugs", type=int, default=60, help="Max drugs per disease")
    dbatch.add_argument("--max-pathways", type=int, default=30, help="Max pathways per disease")
    dbatch.add_argument("--skip-gwas", action="store_true", help="Skip GWAS Catalog fetch")
    dbatch.add_argument("--skip-opentargets", action="store_true", help="Skip Open Targets fetch")
    dbatch.add_argument("--skip-reactome", action="store_true", help="Skip Reactome fetch")
    dbatch.add_argument("--no-cache", action="store_true", help="Bypass the EFO lookup cache")
    dbatch.add_argument(
        "--delay", type=float, default=1.0, help="Seconds between scaffolds (default: 1.0)"
    )
    dbatch.add_argument(
        "--dry-run", action="store_true", help="Fetch + plan but do not write files"
    )
    dbulk = disease_sub.add_parser(
        "bulk-harvest", help="Parallel harvest from local Open Targets bulk parquet"
    )
    dbulk.add_argument("--all", action="store_true", help="Harvest all registry diseases")
    dbulk.add_argument("--category", help="Only harvest diseases in this category")
    dbulk.add_argument("--limit", type=int, help="Maximum diseases to harvest")
    dbulk.add_argument(
        "--repair", action="store_true", help="Prioritize zero/low-gene modules first"
    )
    dbulk.add_argument(
        "--only-new", action="store_true", help="Only scaffold diseases without modules"
    )
    dbulk.add_argument("--workers", type=int, default=8, help="Parallel workers (default: 8)")
    dbulk.add_argument("--max-genes", type=int, default=60)
    dbulk.add_argument("--max-drugs", type=int, default=60)
    dbulk.add_argument("--max-pathways", type=int, default=30)
    dbulk.add_argument("--use-gwas", action="store_true", help="Optional GWAS API enrichment")
    dbulk.add_argument("--skip-reactome", action="store_true", help="Skip Reactome fetch")
    dbulk.add_argument("--overwrite", action="store_true", help="Regenerate existing modules")

    dcorpus = disease_sub.add_parser("corpus-status", help="Show corpus readiness tier report")
    dcorpus.add_argument("--json", action="store_true", help="Emit JSON report")
    dcorpus.add_argument("--limit", type=int, help="Limit diseases scanned")
    dcorpus.add_argument(
        "--output",
        type=Path,
        help="Write report to file (default: data/reports/disease_batch_status.json)",
    )

    # ── Knowledge Graph ────────────────────────────────────────────────
    kg = sub.add_parser("kg", help="Build and export the knowledge graph")
    add_required_disease_cli_argument(kg, help_text="Disease ID (required)")
    kg.add_argument("--analyze", action="store_true", help="Run graph analysis")
    kg.add_argument("--export", action="store_true", help="Export for web visualization")

    # ── Core Pipeline ──────────────────────────────────────────────────
    repurpose = sub.add_parser("repurpose", help="Score drug repurposing candidates")
    add_required_disease_cli_argument(repurpose)
    repurpose.add_argument("--top", type=int, default=15, help="Top N candidates")
    repurpose.add_argument("--gene", type=str, help="Filter to specific gene")
    repurpose.add_argument("--export-html", action="store_true", help="Generate HTML report")

    bio = sub.add_parser("bioinformatics", help="Run GWAS + enrichment + PPI")
    add_required_disease_cli_argument(bio)
    bio.add_argument("--skip-gwas", action="store_true")
    bio.add_argument("--skip-enrichment", action="store_true")
    bio.add_argument("--skip-ppi", action="store_true")
    bio.add_argument("--no-cache", action="store_true")
    bio.add_argument("--export-html", action="store_true")

    lit = sub.add_parser("literature", help="Mine PubMed for disease articles")
    add_required_disease_cli_argument(lit)
    lit.add_argument("--max", dest="max_articles", type=int, default=200)
    lit.add_argument("--no-cache", action="store_true")
    lit.add_argument("--targeted", action="store_true")
    lit.add_argument("--extract", action="store_true")
    lit.add_argument("--export-html", action="store_true")

    screen = sub.add_parser("screening", help="Virtual drug screening")
    add_required_disease_cli_argument(screen)
    screen.add_argument("--gene", type=str)
    screen.add_argument("--top", type=int, default=15)
    screen.add_argument("--use-vina", action="store_true")
    screen.add_argument("--export-html", action="store_true")

    trials = sub.add_parser("trials", help="Track clinical trials")
    add_required_disease_cli_argument(trials)
    trials.add_argument("--top", type=int, default=20)
    trials.add_argument("--no-cache", action="store_true")
    trials.add_argument("--export-html", action="store_true")

    ml = sub.add_parser("ml", help="Train ML target predictor")
    add_required_disease_cli_argument(ml)
    ml.add_argument("--top", type=int, default=15)
    ml.add_argument("--export-html", action="store_true")

    # ── Advanced Analysis ──────────────────────────────────────────────
    synergy = sub.add_parser("synergy", help="Drug combination synergy scoring")
    add_required_disease_cli_argument(synergy)
    synergy.add_argument("--top", type=int, default=20)
    synergy.add_argument("--export-html", action="store_true")

    safety = sub.add_parser("safety", help="Adverse event safety profiling")
    add_required_disease_cli_argument(safety)
    safety.add_argument("--drug", type=str)
    safety.add_argument("--top", type=int, default=20)
    safety.add_argument("--export-html", action="store_true")

    network = sub.add_parser("network", help="Deep network pharmacology analysis")
    add_required_disease_cli_argument(network)
    network.add_argument("--top", type=int, default=20)
    network.add_argument("--export-html", action="store_true")

    expr = sub.add_parser("expression", help="Gene expression correlation analysis")
    add_required_disease_cli_argument(expr)
    expr.add_argument("--top", type=int, default=15)
    expr.add_argument("--export-html", action="store_true")

    cart = sub.add_parser("cart", help="CAR-T response prediction")
    add_required_disease_cli_argument(cart)
    cart.add_argument("--top", type=int, default=15)
    cart.add_argument("--export-html", action="store_true")

    biomarker = sub.add_parser("biomarker", help="Cross-module biomarker discovery")
    add_required_disease_cli_argument(biomarker)
    biomarker.add_argument("--top", type=int, default=15)
    biomarker.add_argument("--export-html", action="store_true")

    # ── Evidence & Knowledge ───────────────────────────────────────────
    workspace = sub.add_parser("workspace", help="Build a cited evidence-to-hypothesis dossier")
    add_required_disease_cli_argument(workspace, help_text="Disease ID (required)")
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

    biomed = sub.add_parser(
        "biomed",
        help="Initialize and manage the canonical biomedical knowledge store",
    )
    biomed_sub = biomed.add_subparsers(dest="biomed_action", required=True)
    biomed_init = biomed_sub.add_parser(
        "init", help="Create or migrate the biomedical SQLite store"
    )
    biomed_init.add_argument(
        "--db",
        type=Path,
        help="Biomedical SQLite path (defaults to BIOMEDICAL_DB_PATH)",
    )

    biomed_import = biomed_sub.add_parser("import", help="Import a pinned ontology artifact")
    biomed_import.add_argument(
        "biomed_import_resource",
        choices=("mondo", "hp", "hpoa", "clinvar", "openfda", "go", "reactome", "uberon"),
        help="Ontology or evidence resource to import",
    )
    biomed_import.add_argument("--artifact", type=Path, required=True, help="Local artifact path")
    biomed_import.add_argument(
        "--db",
        type=Path,
        help="Biomedical SQLite path (defaults to BIOMEDICAL_DB_PATH)",
    )
    biomed_import.add_argument(
        "--activate",
        dest="activate",
        action="store_true",
        default=True,
        help="Activate the imported snapshot (default)",
    )
    biomed_import.add_argument(
        "--no-activate",
        dest="activate",
        action="store_false",
        help="Import without activating the snapshot",
    )
    biomed_import.add_argument(
        "--slim",
        action="store_true",
        help="Pipeline-optimized import (skip hierarchy claims, filter MONDO xrefs)",
    )
    biomed_import.add_argument(
        "--full",
        dest="slim",
        action="store_false",
        help="Full ontology import including hierarchy claims",
    )
    biomed_import.set_defaults(slim=True)

    biomed_snapshots = biomed_sub.add_parser("snapshots", help="List imported resource snapshots")
    biomed_snapshots.add_argument(
        "biomed_snapshots_action",
        nargs="?",
        choices=("list",),
        default="list",
        help="Snapshots action (default: list)",
    )
    biomed_snapshots.add_argument("--resource", help="Filter by resource name")
    biomed_snapshots.add_argument(
        "--db",
        type=Path,
        help="Biomedical SQLite path (defaults to BIOMEDICAL_DB_PATH)",
    )

    from med_research.biomed.sync.registry import list_syncable_sources

    biomed_sync = biomed_sub.add_parser("sync", help="Synchronize an upstream biomedical source")
    biomed_sync.add_argument(
        "biomed_sync_source",
        choices=tuple(list_syncable_sources()),
        help="Registered sync source identifier",
    )
    biomed_sync.add_argument(
        "--dry-run",
        action="store_true",
        help="Run lifecycle without publishing canonical snapshots",
    )
    biomed_sync.add_argument(
        "--no-publish",
        dest="publish",
        action="store_false",
        default=True,
        help="Skip publish even when not in dry-run mode",
    )
    biomed_sync.add_argument(
        "--db",
        type=Path,
        help="Biomedical SQLite path (defaults to BIOMEDICAL_DB_PATH)",
    )
    biomed_sync.add_argument(
        "--json",
        action="store_true",
        help="Print the machine-readable sync report",
    )

    biomed_migrate = biomed_sub.add_parser(
        "migrate",
        help="Migrate curated legacy disease projections into the canonical store",
    )
    biomed_migrate.add_argument(
        "biomed_migrate_target",
        choices=("legacy",),
        help="Migration target",
    )
    biomed_migrate.add_argument(
        "--db",
        type=Path,
        help="Biomedical SQLite path (defaults to BIOMEDICAL_DB_PATH)",
    )
    biomed_migrate.add_argument(
        "--disease",
        action="append",
        dest="biomed_migrate_diseases",
        help="Limit migration to a specific legacy disease id (repeatable)",
    )
    biomed_migrate.add_argument(
        "--report",
        type=Path,
        help="Write a JSON parity report to this path",
    )
    biomed_migrate.add_argument(
        "--activate",
        dest="activate",
        action="store_true",
        default=True,
        help="Activate the imported snapshot (default)",
    )
    biomed_migrate.add_argument(
        "--no-activate",
        dest="activate",
        action="store_false",
        help="Import without activating the snapshot",
    )

    biomed_compare = biomed_sub.add_parser(
        "compare",
        help="Compare two condition CURIEs using HPO-aware similarity",
    )
    biomed_compare.add_argument("--left", required=True, help="Left condition CURIE")
    biomed_compare.add_argument("--right", required=True, help="Right condition CURIE")
    biomed_compare.add_argument(
        "--db",
        type=Path,
        help="Biomedical SQLite path (defaults to BIOMEDICAL_DB_PATH)",
    )
    biomed_compare.add_argument("--phenotype-weight", type=float, default=0.55)
    biomed_compare.add_argument("--gene-weight", type=float, default=0.20)
    biomed_compare.add_argument("--pathway-weight", type=float, default=0.15)
    biomed_compare.add_argument("--intervention-weight", type=float, default=0.10)
    biomed_compare.add_argument("--biomarker-weight", type=float, default=0.0)

    biomed_analytics = biomed_sub.add_parser(
        "analytics",
        help="Run DuckDB-accelerated biomedical graph analytics",
    )
    biomed_analytics.add_argument(
        "--disease", help="Target disease/condition CURIE (e.g. MONDO:0007915)"
    )
    biomed_analytics.add_argument(
        "--compare-with", help="Second condition CURIE to compute shared mechanisms"
    )
    biomed_analytics.add_argument(
        "--stats", action="store_true", help="Print overall graph statistics"
    )
    biomed_analytics.add_argument("--top", type=int, default=20, help="Top K targets")
    biomed_analytics.add_argument(
        "--db",
        type=Path,
        help="Biomedical SQLite path (defaults to BIOMEDICAL_DB_PATH)",
    )

    semantic = sub.add_parser("semantic", help="Semantic search over biomedical abstracts")
    add_required_disease_cli_argument(semantic)
    semantic.add_argument("--query", "-q", default=None, help="Search query")
    semantic.add_argument("--top", type=int, default=20)
    semantic.add_argument("--export-html", action="store_true")

    evidence = sub.add_parser("evidence", help="Multi-source evidence gathering")
    add_required_disease_cli_argument(evidence)
    evidence.add_argument("--query", "-q", default=None)
    evidence.add_argument("--sources", default="all")
    evidence.add_argument("--max", type=int, default=20)
    evidence.add_argument("--no-cache", action="store_true")
    evidence.add_argument("--top", type=int, default=15)
    evidence.add_argument("--export-html", action="store_true")

    extractor = sub.add_parser("extractor", help="LLM-powered evidence extraction")
    add_required_disease_cli_argument(extractor)
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
    add_required_disease_cli_argument(monitor)
    monitor.add_argument("--snapshot", action="store_true")
    monitor.add_argument("--diff", action="store_true")
    monitor.add_argument("--list", dest="list_snapshots", action="store_true")
    monitor.add_argument("--sources", default="pubmed,preprints,clinical_trials")
    monitor.add_argument("--max", type=int, default=10)
    monitor.add_argument("--export-html", action="store_true")

    # ── Cross-Disease ──────────────────────────────────────────────────
    cd = sub.add_parser("cross-disease", help="Cross-disease drug repurposing analysis")
    add_required_disease_cli_argument(
        cd, help_text="Disease ID for provenance/reporting (required)"
    )
    cd.add_argument("--top", type=int, default=20)
    cd.add_argument("--export-html", action="store_true")

    # ── Full Pipeline & Server ─────────────────────────────────────────
    run_all = sub.add_parser("run-all", help="Run the complete research pipeline")
    add_required_disease_cli_argument(run_all)
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
    serve.add_argument("--host", default="0.0.0.0")  # nosec B104 - overridable bind; see web/config.py
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

    live = sub.add_parser("live", help="Query live external biological databases")
    live.add_argument(
        "--target", "-t", default="JAK2", help="Target gene symbol (e.g. JAK2, STAT3, TNF)"
    )
    add_required_disease_cli_argument(
        live, help_text="Disease code (required; e.g. ra, sle, ms, ibd)"
    )
    live.add_argument(
        "--source",
        "-s",
        default="all",
        choices=["all", "opentargets", "gtex", "chembl", "uniprot", "biorxiv"],
        help="External source to query",
    )

    _add_registry_cli_commands(sub)
    return parser


# ── Command Handlers ────────────────────────────────────────────────────


def cmd_diseases(args):
    """List all available diseases (optionally with config validation status)."""
    logger.info("\nAvailable Diseases:")
    logger.info("-" * 60)
    if getattr(args, "validate", False):
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
    for did in Disease.list_all():
        logger.info(f"  {did}")
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

    if args.disease_action == "corpus-status":
        import json

        from med_research.diseases.corpus_status import DEFAULT_STATUS_PATH, build_corpus_status

        report = build_corpus_status(limit=args.limit, include_symptom_source=True)
        output = getattr(args, "output", None) or DEFAULT_STATUS_PATH
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
        agg = report["aggregate"]
        logger.info(
            "Corpus status: L3=%s L2=%s L1=%s L0=%s blocked=%s symptoms=%s",
            agg.get("L3", 0),
            agg.get("L2", 0),
            agg.get("L1", 0),
            agg.get("L0", 0),
            agg.get("blocked", 0),
            agg.get("symptoms_populated", 0),
        )
        if getattr(args, "json", False):
            print(json.dumps(report, indent=2))
        else:
            print(f"Report written to {output}")
        return 0

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
                except (
                    OSError,
                    ValueError,
                    KeyError,
                    TypeError,
                    AttributeError,
                    RuntimeError,
                ) as e:
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

    if args.disease_action == "validate-batch":
        from med_research.diseases.validation_batch import (
            run_strict_validation_batch,
            write_validation_report,
        )

        tier = args.tier
        explicit = list(args.disease_ids) if args.disease_ids else None
        report = run_strict_validation_batch(
            tier_filter=tier,
            limit=args.limit,
            disease_ids=explicit,
        )
        out = write_validation_report(report, args.output)
        summary = report["summary"]
        logger.info(
            "\nBatch validation (%s): %s/%s passed (%.1f%%)",
            tier,
            summary["passed"],
            summary["total"],
            summary["pass_rate"] * 100,
        )
        if summary["failed"]:
            logger.warning("  %s module(s) failed strict validation", summary["failed"])
            for failure_class, count in summary.get("failure_classes", {}).items():
                logger.info("    %s: %s", failure_class, count)
        logger.info("Report written to %s", out)
        if args.strict and summary["failed"] > 0:
            return 1
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

    if args.disease_action == "batch-add":
        from med_research.diseases.scaffold import (
            batch_scaffold,
            print_batch_summary,
        )

        report = batch_scaffold(
            category=args.category,
            limit=args.limit,
            max_genes=args.max_genes,
            max_drugs=args.max_drugs,
            max_pathways=args.max_pathways,
            use_gwas=not args.skip_gwas,
            use_opentargets=not args.skip_opentargets,
            use_reactome=not args.skip_reactome,
            use_cache=not args.no_cache,
            delay=args.delay,
            dry_run=args.dry_run,
        )
        print_batch_summary(report)
        return 1 if report["failed"] and not report["succeeded"] else 0

    if args.disease_action == "bulk-harvest":
        from med_research.diseases.bulk_scaffold import bulk_harvest, print_bulk_harvest_summary

        if not args.all and not args.category and not args.limit and not args.repair:
            logger.error("❌ bulk-harvest needs --all, --category, --limit, or --repair")
            return 2
        try:
            report = bulk_harvest(
                category=args.category,
                limit=args.limit,
                repair=args.repair,
                only_new=args.only_new,
                workers=args.workers,
                max_genes=args.max_genes,
                max_drugs=args.max_drugs,
                max_pathways=args.max_pathways,
                use_gwas=args.use_gwas,
                use_reactome=not args.skip_reactome,
                overwrite=args.overwrite,
            )
        except FileNotFoundError as exc:
            logger.error("❌ %s", exc)
            return 1
        print_bulk_harvest_summary(report)
        return 1 if report["failed"] and not report["succeeded"] else 0

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
                    logger.warning(
                        "  ⚠️  You skipped sources (--skip-*): entities from those sources"
                    )
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

    logger.info(
        "Usage: med-research disease "
        "{add|refresh|restore|backups|list|validate|validate-batch|coverage}"
    )
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

    def _summarize(data: list) -> None:
        analyze(data)
        print_top_candidates(data, args.top)

    return _run_module_cli(
        "drug_repurposing", args.disease, args, summary_fn=_summarize, context="Drug repurposing"
    )


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
    from med_research.pipeline.literature_mining.miner import EntityContext, print_summary

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
            ", ".join(coverage.get("missing_inputs", [])) or "coverage contract not satisfied",
        )
        return _exit_from_result(result, context="Literature mining") or 1

    entities = payload.get("entities", {})
    candidates = payload.get("candidates", [])
    entity_context = EntityContext.from_results(entities, results.get("gene_coverage", {}))
    print_summary(results, candidates, entities, entity_context=entity_context)
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

    def _summarize(data: list) -> None:
        analyze(data)
        print_top_pairs(data, args.top)

    return _run_module_cli(
        "drug_synergy", args.disease, args, summary_fn=_summarize, context="Drug synergy"
    )


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
        logger.info(
            f"   Disease Symptom Overlap:  {profile.get('disease_symptom_overlap_score', 'N/A')}/10"
        )
        logger.info(
            f"   Severity Burden:           {profile.get('severity_burden_score', 'N/A')}/10"
        )
        logger.info(
            f"   Chronic Use Safety:        {profile.get('chronic_use_safety_score', 'N/A')}/10"
        )
        logger.info(
            f"   Disease-Specific Risk:     {profile.get('disease_specific_risk_score', 'N/A')}/10"
        )
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

    return _run_module_cli(
        "network_pharmacology",
        args.disease,
        args,
        summary_fn=lambda d: print_analysis(cast(NetworkAnalysis, d)),
        context="Network pharmacology",
    )


def cmd_expression(args):
    """Gene expression correlations."""
    from med_research.pipeline.gene_expression.correlator import (
        analyze,
        print_top_correlations,
    )

    def _summarize(data: list) -> None:
        analyze(data, None, disease_id=args.disease)
        print_top_correlations(data, args.top)

    return _run_module_cli(
        "gene_expression",
        args.disease,
        args,
        summary_fn=_summarize,
        context="Gene expression",
        top=args.top,
    )


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

    def _summarize(data: list) -> None:
        analyze(data)
        print_top_biomarkers(data, args.top)

    return _run_module_cli(
        "biomarker_discovery",
        args.disease,
        args,
        summary_fn=_summarize,
        context="Biomarker discovery",
    )


def cmd_workspace(args):
    """Build and export an evidence-to-hypothesis dossier."""
    from datetime import date

    from med_research.pipeline.evidence_workspace.report import dossier_to_json, render_html
    from med_research.pipeline.evidence_workspace.schemas import EvidenceDossier, ResearchRequest

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
    if not isinstance(dossier, EvidenceDossier):
        logger.error("Evidence workspace returned unexpected result type")
        return 1
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


def cmd_biomed(args: Any) -> int:
    """Manage the canonical biomedical knowledge store."""
    action = getattr(args, "biomed_action", None)
    if action == "init":
        return cmd_biomed_init(args)
    if action == "import":
        return cmd_biomed_import(args)
    if action == "snapshots":
        return cmd_biomed_snapshots(args)
    if action == "sync":
        return cmd_biomed_sync(args)
    if action == "migrate":
        return cmd_biomed_migrate(args)
    if action == "compare":
        return cmd_biomed_compare(args)
    if action == "analytics":
        return cmd_biomed_analytics(args)
    logger.error("Unknown biomed action: %s", action)
    return 1


def _biomed_repository(args: Any) -> Any:
    from med_research.biomed.repository import BiomedicalRepository
    from med_research.web.config import BIOMEDICAL_DB_PATH

    path = getattr(args, "db", None) or BIOMEDICAL_DB_PATH
    repository = BiomedicalRepository(path)
    repository.initialize()
    return repository


def cmd_biomed_init(args: Any) -> int:
    """Create or migrate the biomedical SQLite store."""
    from med_research.biomed.schema import SCHEMA_VERSION
    from med_research.web.config import BIOMEDICAL_DB_PATH

    path = args.db or BIOMEDICAL_DB_PATH
    _biomed_repository(args)
    resolved = path.resolve()
    message = f"Biomedical store initialized at {resolved} (schema version {SCHEMA_VERSION})"
    print(message)
    logger.info(message)
    return 0


def cmd_biomed_analytics(args: Any) -> int:
    """Execute DuckDB-accelerated biomedical graph analytics."""
    from med_research.biomed.analytics.duckdb_engine import DuckDBBiomedicalEngine
    from med_research.web.config import BIOMEDICAL_DB_PATH

    path = getattr(args, "db", None) or BIOMEDICAL_DB_PATH
    engine = DuckDBBiomedicalEngine(path)

    if getattr(args, "stats", False):
        stats = engine.get_summary_statistics()
        print("=== Biomedical Knowledge Graph Summary ===")
        for k, v in stats.items():
            print(f"  {k}: {v}")
        return 0

    if getattr(args, "disease", None) and getattr(args, "compare_with", None):
        shared = engine.compute_shared_mechanisms(args.disease, args.compare_with)
        print(f"=== Shared Mechanisms: {args.disease} vs {args.compare_with} ===")
        print(f"  Jaccard Similarity: {shared.jaccard_similarity:.4f}")
        print(f"  Shared Pathways ({len(shared.shared_pathways)}): {shared.shared_pathways[:10]}")
        print(f"  Shared Genes ({len(shared.shared_genes)}): {shared.shared_genes[:10]}")
        return 0

    if getattr(args, "disease", None):
        top_k = getattr(args, "top", 20)
        targets = engine.prioritize_targets_vectorized(args.disease, top_k=top_k)
        print(f"=== Prioritized Targets for {args.disease} (Top {len(targets)}) ===")
        for t in targets:
            print(
                f"  [{t.target_curie}] {t.target_name} ({t.target_type}) "
                f"| Score: {t.evidence_score:.2f} (Sup: {t.supporting_count}, Con: {t.contradictory_count}) "
                f"| Pathways: {t.pathway_count}"
            )
        return 0

    print("Please specify --disease, --stats, or --compare-with. Run with --help for usage.")
    return 0


def cmd_biomed_import(args: Any) -> int:
    """Import a pinned ontology artifact into the biomedical store."""
    from med_research.biomed.imports.clinvar_adapter import ClinVarImportAdapter
    from med_research.biomed.imports.go_adapter import GOImportAdapter
    from med_research.biomed.imports.hpo import HpoOntologyAdapter
    from med_research.biomed.imports.hpoa import HpoAnnotationAdapter
    from med_research.biomed.imports.mondo import MondoAdapter
    from med_research.biomed.imports.openfda_adapter import OpenFDAImportAdapter
    from med_research.biomed.imports.reactome_adapter import ReactomeImportAdapter
    from med_research.biomed.imports.service import ImportService
    from med_research.biomed.imports.uberon_adapter import UberonImportAdapter
    from med_research.biomed.models import ResourcePolicy

    resource = args.biomed_import_resource
    policies = {
        "mondo": ResourcePolicy(
            resource_name="mondo",
            license_id="CC-BY-4.0",
            license_url="https://creativecommons.org/licenses/by/4.0/",
            redistribution_policy="redistributable",
        ),
        "hp": ResourcePolicy(
            resource_name="hp",
            license_id="custom",
            license_url="https://hpo.jax.org/app/license",
            redistribution_policy="user_supplied",
        ),
        "hpoa": ResourcePolicy(
            resource_name="hpoa",
            license_id="custom",
            license_url="https://hpo.jax.org/app/license",
            redistribution_policy="user_supplied",
        ),
        "clinvar": ResourcePolicy(
            resource_name="clinvar",
            license_id="Public Domain",
            license_url="https://www.ncbi.nlm.nih.gov/clinvar/",
            redistribution_policy="user_supplied",
        ),
        "openfda": ResourcePolicy(
            resource_name="openfda",
            license_id="Public Domain",
            license_url="https://open.fda.gov/",
            redistribution_policy="user_supplied",
        ),
        "go": ResourcePolicy(
            resource_name="go",
            license_id="CC-BY-4.0",
            license_url="http://geneontology.org",
            redistribution_policy="permitted",
        ),
        "reactome": ResourcePolicy(
            resource_name="reactome",
            license_id="CC-BY-4.0",
            license_url="https://reactome.org",
            redistribution_policy="permitted",
        ),
        "uberon": ResourcePolicy(
            resource_name="uberon",
            license_id="CC-BY-3.0",
            license_url="http://uberon.org",
            redistribution_policy="permitted",
        ),
    }
    adapters: dict[str, Any] = {
        "mondo": MondoAdapter(),
        "hp": HpoOntologyAdapter(),
        "hpoa": HpoAnnotationAdapter(),
        "clinvar": ClinVarImportAdapter(),
        "openfda": OpenFDAImportAdapter(),
        "go": GOImportAdapter(),
        "reactome": ReactomeImportAdapter(),
        "uberon": UberonImportAdapter(),
    }
    repository = _biomed_repository(args)
    adapter = adapters[resource]
    policy = policies[resource]
    parse_kwargs: dict[str, Any] = {}
    if resource == "hpoa":
        mondo_snapshot = repository.get_active_snapshot("mondo")
        mondo_mappings: dict[str, str] = {}
        if mondo_snapshot is not None:
            with repository.database.connect() as connection:
                rows = connection.execute(
                    """
                    SELECT subject_curie, object_curie FROM entity_mappings
                    WHERE snapshot_id = ? AND relation = 'exact'
                    """,
                    (str(mondo_snapshot.id),),
                ).fetchall()
                mondo_mappings = {row["object_curie"]: row["subject_curie"] for row in rows}
        parse_kwargs["mondo_mappings"] = mondo_mappings
    if resource in {"mondo", "hp"}:
        parse_kwargs["slim"] = args.slim
    bundle = adapter.parse(args.artifact, policy, **parse_kwargs)
    report = ImportService(repository).import_bundle(bundle, activate=args.activate)
    counts = report.counts
    message = (
        f"Imported {resource} snapshot {report.snapshot_id} "
        f"(checksum {bundle.snapshot.checksum}, "
        f"{counts.entity_revisions} revisions, {counts.claims} claims, "
        f"{counts.mappings} mappings, {len(report.warnings)} warnings)"
    )
    print(message)
    for warning in report.warnings:
        print(f"  warning [{warning.code}]: {warning.message}")
    if resource == "mondo":
        for entity in bundle.entities:
            if entity.primary_curie == "MONDO:0007915":
                print(f"  condition: {entity.primary_curie}")
    logger.info(message)
    return 0


def cmd_biomed_migrate(args: Any) -> int:
    """Migrate curated legacy disease projections into the canonical store."""
    import json

    from med_research.biomed.errors import BiomedicalValidationError
    from med_research.biomed.imports.service import ImportService
    from med_research.biomed.legacy.adapter import LegacyMigrationAdapter
    from med_research.biomed.legacy.manifest import legacy_disease_ids
    from med_research.biomed.legacy.report import build_parity_report

    target = getattr(args, "biomed_migrate_target", None)
    if target != "legacy":
        logger.error("Unknown migrate target: %s", target)
        return 1

    repository = _biomed_repository(args)
    if repository.get_active_snapshot("mondo") is None:
        logger.error(
            "Legacy migration requires an active Mondo snapshot. "
            "Import Mondo first: python -m med_research.cli biomed import mondo --artifact <path>"
        )
        return 1

    disease_ids = args.biomed_migrate_diseases or legacy_disease_ids()
    try:
        adapter = LegacyMigrationAdapter()
        bundle = adapter.build_bundle(disease_ids)
        report = ImportService(repository).import_bundle(bundle, activate=args.activate)
    except BiomedicalValidationError as exc:
        logger.error("Legacy migration failed: %s", exc)
        return 1

    parity_reports = [build_parity_report(disease_id) for disease_id in disease_ids]
    summary = {
        "resource_name": bundle.snapshot.resource_name,
        "snapshot_id": str(report.snapshot_id),
        "checksum": bundle.snapshot.checksum,
        "diseases": [item.to_dict() for item in parity_reports],
    }
    message = (
        f"Migrated legacy-curated snapshot {report.snapshot_id} "
        f"({len(disease_ids)} diseases, {report.counts.claims} claims, "
        f"{report.counts.entities} entities, {len(report.warnings)} warnings)"
    )
    print(message)
    for parity in parity_reports:
        print(
            f"  {parity.disease_id}: relationships "
            f"{parity.relationships.imported_count}/{parity.relationships.source_count}, "
            f"exceptions {len(parity.exceptions)}"
        )
    for warning in report.warnings:
        print(f"  warning [{warning.code}]: {warning.message}")

    if args.report:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(json.dumps(summary, indent=2), encoding="utf-8")
        print(f"Parity report written to {args.report.resolve()}")

    logger.info(message)
    return 0


def cmd_biomed_sync(args: Any) -> int:
    """Run the biomedical source synchronization lifecycle."""
    import json

    from med_research.biomed.sync.lifecycle import SyncService
    from med_research.biomed.sync.models import SyncStatus

    repository = _biomed_repository(args)
    report = SyncService(repository).run(
        args.biomed_sync_source,
        dry_run=bool(args.dry_run),
        publish=bool(args.publish),
    )
    if args.json:
        print(json.dumps(report.model_dump(mode="json"), indent=2, default=str))
    else:
        logger.info("Sync %s: %s", report.source_id, report.status.value)
        for stage in report.stages:
            logger.info("  %s: %s", stage.stage.value, stage.status.value)
        if report.error:
            logger.error("Sync error: %s", report.error)
    return 0 if report.status is SyncStatus.COMPLETED else 1


def cmd_biomed_compare(args: Any) -> int:
    """Compare two conditions and persist a research run."""
    from med_research.biomed.comparison.models import SimilarityConfig
    from med_research.biomed.comparison.service import ConditionComparisonService
    from med_research.biomed.errors import BiomedicalValidationError

    try:
        config = SimilarityConfig(
            phenotype_weight=args.phenotype_weight,
            gene_weight=args.gene_weight,
            pathway_weight=args.pathway_weight,
            intervention_weight=args.intervention_weight,
            biomarker_weight=args.biomarker_weight,
        )
    except ValueError as exc:
        logger.error("%s", exc)
        return 1

    repository = _biomed_repository(args)
    try:
        result = ConditionComparisonService(repository).compare(args.left, args.right, config)
    except BiomedicalValidationError as exc:
        logger.error("%s", exc)
        return 1

    print(f"run_id={result.run_id}")
    print(f"status={result.status}")
    if result.overall_score is not None:
        print(f"overall_score={result.overall_score:.4f}")
    else:
        print("overall_score=insufficient_data")
    print(f"left_curie={result.left_curie}")
    print(f"right_curie={result.right_curie}")
    return 0


def cmd_biomed_snapshots(args: Any) -> int:
    """List imported biomedical resource snapshots."""
    action = getattr(args, "biomed_snapshots_action", None)
    if action != "list":
        logger.error("Unknown snapshots action: %s", action)
        return 1
    repository = _biomed_repository(args)
    with repository.database.connect() as connection:
        params: list[Any] = []
        where = ""
        if getattr(args, "resource", None):
            where = "WHERE resource_name = ?"
            params.append(args.resource)
        rows = connection.execute(
            f"""
            SELECT s.resource_name, s.version, s.checksum, s.id,
                   CASE WHEN a.snapshot_id IS NOT NULL THEN 1 ELSE 0 END AS active
            FROM resource_snapshots s
            LEFT JOIN active_snapshots a
              ON a.resource_name = s.resource_name AND a.snapshot_id = s.id
            {where}
            ORDER BY s.resource_name, s.version
            """,  # nosec B608 - optional WHERE uses a static fragment; value is bound
            params,
        ).fetchall()
    for row in rows:
        active = "active" if row["active"] else "inactive"
        print(f"{row['resource_name']}\t{row['version']}\t{row['checksum']}\t{active}")
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
    return _run_module_cli(
        "semantic_search",
        args.disease,
        args,
        query=query,
        top=args.top,
        context="Semantic search",
    )


def cmd_evidence(args):
    """Multi-source evidence gathering."""
    query = args.query or _default_pubmed_query(args.disease)
    sources = None if args.sources == "all" else [s.strip() for s in args.sources.split(",")]
    return _run_module_cli(
        "evidence_gather",
        args.disease,
        args,
        query=query,
        sources=sources,
        max_per_source=args.max,
        use_cache=not args.no_cache,
        context="Evidence gathering",
    )


def cmd_extractor(args):
    """LLM-powered evidence extraction."""
    query = args.query or _default_pubmed_query(args.disease)
    sources = [s.strip() for s in args.sources.split(",")]
    return _run_module_cli(
        "llm_extractor",
        args.disease,
        args,
        query=query,
        sources=sources,
        max_articles=args.max,
        model=args.model or None,
        use_cache=not args.no_cache,
        context="LLM extractor",
    )


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

    return _run_module_cli(
        "evidence_monitor",
        args.disease,
        args,
        sources=sources,
        max_per_query=args.max,
        context="Evidence monitor",
    )


def cmd_cross_disease(args):
    """Cross-disease analysis."""
    from med_research.pipeline.cross_disease.analyzer import (
        analyze,
        print_repurposing,
        print_top_drugs,
    )

    def _summarize(results: dict) -> None:
        analyze(results)
        print_top_drugs(results, top_n=args.top)
        print_repurposing(results, top_n=args.top)

    return _run_module_cli(
        "cross_disease", args.disease, args, summary_fn=_summarize, context="Cross-disease analysis"
    )


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
    except (OSError, ValueError, KeyError, TypeError, AttributeError) as e:
        logger = get_logger(__name__)
        logger.warning("⚠️  %s could not be validated: %s", disease.disease_id, e)
        return True
    if not gaps:
        return False
    logger = get_logger(__name__)
    impacts = {
        "CAR_T_SCORES": "CAR-T predictor will silently score every gene 0",
        "DRUG_SAFETY_RISK": "drug-safety assessment will silently treat all drugs as zero-risk",
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
            except (RuntimeError, OSError, ValueError, KeyError, TypeError) as e:
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


def cmd_live(args):
    """Query live external biomedical APIs (Open Targets, GTEx, ChEMBL, UniProt, bioRxiv)."""
    target = args.target.upper()
    disease = args.disease.lower()
    source = args.source.lower()

    msg = f"==================================================\nLive External Database Query: Target={target}, Disease={disease}, Source={source}\n=================================================="
    logger.info(msg)
    print(msg)

    if source in ("all", "opentargets"):
        try:
            from med_research.pipeline.external import OpenTargetsClient

            ot_client = OpenTargetsClient()
            target_info = ot_client.get_target_details(target)
            print(f"\n[Open Targets] Target Info: {target_info}")
            if "ensembl_id" in target_info and target_info["ensembl_id"]:
                from med_research.pipeline.external.opentargets import DISEASE_EFO_MAP

                efo = DISEASE_EFO_MAP.get(disease, disease)
                ev = ot_client.get_target_disease_evidence(target_info["ensembl_id"], efo)
                print(
                    f"[Open Targets] Association Score ({disease.upper()}): {ev.get('overall_score', 0.0):.3f}"
                )
        except Exception as err:
            logger.warning("[Open Targets] Failed: %s", err)
            print(f"[Open Targets] Failed: {err}")

    if source in ("all", "gtex"):
        try:
            from med_research.pipeline.external import GTExClient

            gtex_client = GTExClient()
            exp = gtex_client.get_median_tissue_expression(target)
            print("\n[GTEx] Top 3 Median Expression Tissues:")
            for item in exp[:3]:
                print(f"  - {item['tissue_name']}: {item['median_tpm']:.2f} TPM")
        except Exception as err:
            logger.warning("[GTEx] Failed: %s", err)
            print(f"[GTEx] Failed: {err}")

    if source in ("all", "chembl"):
        try:
            from med_research.pipeline.external import ChEMBLClient

            chembl = ChEMBLClient()
            t_res = chembl.search_target(target)
            if t_res and t_res.get("target_chembl_id"):
                target_id = str(t_res.get("target_chembl_id"))
                print(f"\n[ChEMBL] Target ID: {target_id} ({t_res.get('pref_name')})")
                acts = chembl.get_target_bioactivities(target_id, limit=3)
                print("[ChEMBL] Top Bioactivities:")
                for a in acts:
                    print(
                        f"  - Molecule {a.get('molecule_chembl_id')}: {a.get('activity_type')} = {a.get('value')} {a.get('units')}"
                    )
        except Exception as err:
            logger.warning("[ChEMBL] Failed: %s", err)
            print(f"[ChEMBL] Failed: {err}")

    if source in ("all", "uniprot"):
        try:
            from med_research.pipeline.external import UniProtClient

            uniprot = UniProtClient()
            prot = uniprot.get_protein_by_gene(target)
            if prot:
                print(
                    f"\n[UniProt] Accession: {prot.get('accession')}, Length: {prot.get('sequence_length')} AA"
                )
                print(f"[UniProt] Domains: {', '.join(prot.get('domains', []))}")
        except Exception as err:
            logger.warning("[UniProt] Failed: %s", err)
            print(f"[UniProt] Failed: {err}")

    if source in ("all", "biorxiv"):
        try:
            from med_research.pipeline.external import BioRxivClient

            biorxiv = BioRxivClient()
            preprints = biorxiv.search_preprints_by_keyword(target, limit=2)
            print("\n[bioRxiv/medRxiv] Recent Preprints:")
            for p in preprints:
                print(f"  - {p.get('title')} (DOI: {p.get('doi')})")
        except Exception as err:
            logger.warning("[bioRxiv] Failed: %s", err)
            print(f"[bioRxiv] Failed: {err}")

    return 0


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
        "biomed": cmd_biomed,
        "semantic": cmd_semantic,
        "evidence": cmd_evidence,
        "extractor": cmd_extractor,
        "monitor": cmd_monitor,
        "cross-disease": cmd_cross_disease,
        "run-all": cmd_run_all,
        "serve": cmd_serve,
        "test": cmd_test,
        "cache": cmd_cache,
        "live": cmd_live,
    }

    handler = handlers.get(args.command)
    if handler:
        return handler(args)
    if getattr(args, "registry_module_id", None):
        return cmd_registry_module(args)

    parser.print_help()
    return 0


def nosograph_main() -> int:
    """Entry point alias for the ``nosograph`` console script."""
    return main()


if __name__ == "__main__":
    sys.exit(main())
