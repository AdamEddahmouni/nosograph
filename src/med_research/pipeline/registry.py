"""Central registry for ``BasePipelineModule`` adapters.

Adapter authoring checklist
---------------------------
1. Subclass ``BasePipelineModule`` in ``pipeline/<module>/adapter.py`` (or
   ``base.py`` for tiny pilots) without rewriting engine scoring logic.
2. Implement ``module_id``, ``coverage_inputs()``, ``run()``, ``report()``, and
   ``build_provenance()`` — delegate to the existing engine and report helpers.
3. Map ``coverage_inputs()`` to keys understood by ``module_coverage()`` in
   ``diseases/coverage.py`` for the module's coverage bucket.
4. Accept ``disease_id`` on every public method; default ``"sle"`` only where
   legacy engines require it for backwards compatibility.
5. Call ``build_provenance()`` from ``pipeline/provenance.py`` inside
   ``build_provenance()``; pass optional provenance into ``report()``.
6. Add contract tests by subclassing ``ModuleAdapterContract`` in
   ``tests/test_pipeline_base.py`` or ``tests/test_<module>_adapter.py``.
7. Register with ``@register_module`` and verify ``list_modules()`` includes
   the new ``module_id``.
8. Do **not** edit ``cli.py`` from module lanes — Lane 1B wires CLI dispatch.

Lane 2 adapters add one ``register_module()`` call per module; keep registry
keys sorted alphabetically when resolving merge conflicts.
"""

from __future__ import annotations

from copy import deepcopy
from typing import TYPE_CHECKING, Any

from med_research.pipeline.results import result_contract_name, result_contract_schema

if TYPE_CHECKING:
    from med_research.pipeline.base import BasePipelineModule

MODULE_REGISTRY: dict[str, type[BasePipelineModule[Any]]] = {}
_REGISTRATION_COMPLETE = False

# External route/task aliases belong to the registry so every catalog consumer
# sees the same canonical module IDs and compatibility names.
MODULE_ALIASES: dict[str, str] = {
    "gwas": "gwas",
    "enrichment": "enrichment",
    "ppi": "ppi",
    "literature": "literature_mining",
    "screening": "virtual_screening",
    "trials": "clinical_trials",
    "ml": "ml_predictor",
    "synergy": "drug_synergy",
    "safety": "adverse_events",
    "kg": "knowledge_graph",
    "knowledge_graph": "knowledge_graph",
    "repurpose": "drug_repurposing",
    "drug_repurposing": "drug_repurposing",
    "network": "network_pharmacology",
    "network_pharmacology": "network_pharmacology",
    "expression": "gene_expression",
    "gene_expression": "gene_expression",
    "cart": "car_t_predictor",
    "car_t_predictor": "car_t_predictor",
    "biomarker": "biomarker_discovery",
    "biomarker_discovery": "biomarker_discovery",
    "cross_disease": "cross_disease",
    "semantic": "semantic_search",
    "semantic_search": "semantic_search",
    "evidence": "evidence_gather",
    "evidence_gather": "evidence_gather",
    "extractor": "llm_extractor",
    "llm_extractor": "llm_extractor",
    "monitor": "evidence_monitor",
    "evidence_monitor": "evidence_monitor",
    "workspace": "evidence_workspace",
    "evidence_workspace": "evidence_workspace",
}


# Public request options are deliberately kept separate from internal adapter
# wiring (graphs, callbacks, clients, and typed request objects). These
# definitions are shared by the catalog, generic CLI, and generic web job API.
_REQUEST_OPTION_DEFINITIONS: dict[str, dict[str, Any]] = {
    "max_studies": {"type": "integer", "minimum": 1, "default": 30},
    "untargeted_only": {"type": "boolean", "default": False},
    "confidence": {"type": "number", "minimum": 0, "maximum": 1, "default": 0.4},
    "expand_neighbors": {"type": "integer", "minimum": 0, "default": 0},
    "resolve_snps": {"type": "boolean", "default": True},
    "max_articles": {"type": "integer", "minimum": 1, "default": 30},
    "targeted": {"type": "boolean", "default": False},
    "extract_content": {"type": "boolean", "default": False},
    "no_cache": {"type": "boolean", "default": False},
    "use_cache": {"type": "boolean", "default": True},
    "email": {"type": "string"},
    "queries": {"type": "string", "description": "Comma-separated queries"},
    "gene_id": {"type": "string"},
    "top_n": {"type": "integer", "minimum": 1, "default": 15},
    "top_k": {"type": "integer", "minimum": 1, "default": 20},
    "use_vina": {"type": "boolean", "default": False},
    "max_trials": {"type": "integer", "minimum": 1, "default": 100},
    "query": {"type": "string"},
    "no_shap": {"type": "boolean", "default": False},
    "save": {"type": "boolean", "default": True},
    "comparative": {"type": "boolean", "default": False},
    "top_synergy": {"type": "integer", "minimum": 1, "default": 5},
    "operation": {
        "type": "string",
        "enum": ["centrality", "communities", "metrics", "untargeted_genes"],
    },
    "metric": {"type": "string", "default": "betweenness"},
    "signature": {"type": "string"},
    "signature_source": {"type": "string", "default": "auto"},
    "tissue": {"type": "string"},
    "sources": {
        "type": "string",
        "body_type": "array",
        "items": {
            "type": "string",
            "enum": ["pubmed", "clinical_trials", "gwas", "fda_labels"],
        },
        "minItems": 1,
        "body_default": ["pubmed", "clinical_trials"],
    },
    "cross_reference": {"type": "boolean", "default": True},
    "max_per_source": {"type": "integer", "minimum": 1, "default": 20},
    "model": {"type": "string"},
    "max_per_query": {"type": "integer", "minimum": 1, "default": 10},
    "diff": {"type": "boolean", "default": False},
    "question": {"type": "string", "minLength": 2, "maxLength": 500},
    "candidate_type": {
        "type": "string",
        "enum": ["drugs", "targets", "both"],
        "default": "both",
    },
    "max_evidence": {"type": "integer", "minimum": 1, "maximum": 200, "default": 50},
    "enable_llm": {"type": "boolean", "default": True},
    "date_from": {"type": "string", "format": "date"},
    "date_to": {"type": "string", "format": "date"},
    "drug_id": {"type": "string"},
}

# Names are the external request contract. Internal options such as
# ``progress_callback`` and ``graph`` intentionally never appear here.
# Rules that cannot be represented by individual JSON Schema properties.
# Keep these JSON-compatible so catalogs can be consumed by clients, CLI
# generators, and documentation tooling without importing Pydantic models.
_REQUEST_VALIDATOR_DEFINITIONS: dict[str, list[dict[str, Any]]] = {
    "evidence_workspace": [
        {
            "id": "sources_non_empty",
            "type": "min_items",
            "field": "sources",
            "value": 1,
            "message": "at least one evidence source is required",
        },
        {
            "id": "date_range_order",
            "type": "field_comparison",
            "fields": ["date_from", "date_to"],
            "operator": "<=",
            "allow_missing": True,
            "message": "date_from must be on or before date_to",
        },
    ],
}


_MODULE_REQUEST_OPTION_NAMES: dict[str, tuple[str, ...]] = {
    "adverse_events": ("drug_id",),
    "biomarker_discovery": ("save",),
    "car_t_predictor": (),
    "clinical_trials": ("query", "max_trials", "no_cache", "use_cache"),
    "cross_disease": ("comparative", "top_synergy"),
    "drug_repurposing": ("gene_id", "untargeted_only", "save"),
    "drug_synergy": ("top_n", "save"),
    "enrichment": ("untargeted_only", "no_cache", "use_cache"),
    "evidence_gather": (
        "query", "sources", "max_per_source", "use_cache", "cross_reference"
    ),
    "evidence_monitor": ("sources", "max_per_query", "diff"),
    "evidence_workspace": (
        "question", "sources", "date_from", "date_to", "candidate_type",
        "max_evidence", "enable_llm", "model",
    ),
    "gene_expression": ("signature", "signature_source", "tissue", "save"),
    "gwas": ("max_studies", "use_cache", "no_cache", "resolve_snps"),
    "knowledge_graph": (),
    "literature_mining": (
        "query", "sources", "queries", "max_articles", "targeted",
        "extract_content", "use_cache", "no_cache", "email",
    ),
    "llm_extractor": ("query", "sources", "max_articles", "model", "use_cache"),
    "ml_predictor": ("top_n", "no_shap"),
    "network_pharmacology": ("operation", "metric", "top_n"),
    "ppi": ("confidence", "expand_neighbors", "use_cache", "no_cache"),
    "semantic_search": ("query", "top_k"),
    "virtual_screening": ("gene_id", "top_n", "use_vina", "operation"),
}


def _ensure_registered() -> None:
    """Import adapter modules so ``@register_module`` decorators run."""
    global _REGISTRATION_COMPLETE

    if _REGISTRATION_COMPLETE:
        return
    import med_research.pipeline.adverse_events.adapter  # noqa: F401
    import med_research.pipeline.bioinformatics.adapter  # noqa: F401
    import med_research.pipeline.biomarker_discovery.adapter  # noqa: F401
    import med_research.pipeline.car_t_predictor.adapter  # noqa: F401
    import med_research.pipeline.clinical_trials.adapter  # noqa: F401
    import med_research.pipeline.cross_disease.adapter  # noqa: F401
    import med_research.pipeline.drug_repurposing.adapter  # noqa: F401
    import med_research.pipeline.drug_synergy.adapter  # noqa: F401
    import med_research.pipeline.evidence.adapter  # noqa: F401
    import med_research.pipeline.evidence_workspace.adapter  # noqa: F401
    import med_research.pipeline.gene_expression.adapter  # noqa: F401
    import med_research.pipeline.knowledge_graph.adapter  # noqa: F401
    import med_research.pipeline.literature_mining.adapter  # noqa: F401
    import med_research.pipeline.ml_predictor.adapter  # noqa: F401
    import med_research.pipeline.network_pharmacology.adapter  # noqa: F401
    import med_research.pipeline.semantic_search.adapter  # noqa: F401
    import med_research.pipeline.virtual_screening.adapter  # noqa: F401

    _REGISTRATION_COMPLETE = True


def register_module(
    cls: type[BasePipelineModule[Any]],
) -> type[BasePipelineModule[Any]]:
    """Decorator that records a pipeline adapter class in ``MODULE_REGISTRY``."""

    from med_research.pipeline.base import BasePipelineModule

    if not issubclass(cls, BasePipelineModule):
        raise TypeError(f"{cls.__name__} must subclass BasePipelineModule")

    module_id = cls().module_id
    if module_id in MODULE_REGISTRY:
        raise ValueError(f"Duplicate module_id registered: {module_id}")

    MODULE_REGISTRY[module_id] = cls
    return cls


def get_module(module_id: str) -> BasePipelineModule[Any]:
    """Return a fresh adapter instance for ``module_id``."""

    _ensure_registered()
    if module_id not in MODULE_REGISTRY:
        registered = ", ".join(sorted(MODULE_REGISTRY)) or "none"
        raise KeyError(
            f"Unknown pipeline module '{module_id}'. Registered modules: {registered}"
        )
    return MODULE_REGISTRY[module_id]()


def list_modules() -> list[str]:
    """Return registered module identifiers in stable sorted order."""

    _ensure_registered()
    return sorted(MODULE_REGISTRY)


def module_aliases(module_id: str) -> list[str]:
    """Return compatibility aliases for one canonical module identifier."""
    return sorted(
        alias
        for alias, target in MODULE_ALIASES.items()
        if target == module_id and alias != module_id
    )


def module_request_schema(module_id: str) -> dict[str, Any]:
    """Build the public request-option JSON schema for a registered module."""
    if module_id not in list_modules():
        raise KeyError(f"Unknown pipeline module: {module_id}")

    # A new adapter gets all public, JSON-compatible options by convention;
    # established modules narrow this to their actual request surface below.
    names = _MODULE_REQUEST_OPTION_NAMES.get(
        module_id, tuple(_REQUEST_OPTION_DEFINITIONS)
    )
    properties = {
        name: dict(_REQUEST_OPTION_DEFINITIONS[name])
        for name in names
        if name in _REQUEST_OPTION_DEFINITIONS
    }
    return {
        "title": f"{module_id.replace('_', ' ').title()}Request",
        "type": "object",
        "properties": properties,
        "required": ["question"] if module_id == "evidence_workspace" else [],
        "additionalProperties": False,
        "validators": deepcopy(_REQUEST_VALIDATOR_DEFINITIONS.get(module_id, [])),
    }


# Existing Celery task names are compatibility-sensitive public routes.
# The registry owns the small set of names that cannot follow ``run_<module_id>``.
# New modules use the convention automatically and need no second route map.
_CELERY_TASK_NAME_OVERRIDES: dict[str, str] = {
    "adverse_events": "run_safety",
    "biomarker_discovery": "run_biomarker_discovery",
    "car_t_predictor": "run_car_t_predictor",
    "drug_repurposing": "run_drug_repurposing",
    "evidence_gather": "run_evidence_gather",
    "evidence_monitor": "run_evidence_monitor",
    "evidence_workspace": "run_workspace",
    "gene_expression": "run_gene_expression",
    "knowledge_graph": "run_knowledge_graph",
    "literature_mining": "run_literature",
    "llm_extractor": "run_llm_extractor",
    "ml_predictor": "run_ml",
    "network_pharmacology": "run_network_pharmacology",
    "semantic_search": "run_semantic_search",
    "virtual_screening": "run_screening",
}


def _preferred_alias(module_id: str) -> str:
    """Return the stable human-facing route for a registered module."""
    aliases = module_aliases(module_id)
    return aliases[0] if aliases else module_id.replace("_", "-")


def module_job_aliases() -> dict[str, str]:
    """Return canonical IDs and compatibility aliases for job submission."""
    aliases: dict[str, str] = {}
    for module_id in list_modules():
        aliases[module_id] = module_id
        aliases.update({alias: module_id for alias in module_aliases(module_id)})
    return aliases


def module_route_metadata(module_id: str) -> dict[str, Any]:
    """Return generated CLI, Celery, and web route metadata for one module."""
    if module_id not in list_modules():
        raise KeyError(f"Unknown pipeline module: {module_id}")
    command = _preferred_alias(module_id)
    display_name = module_id.replace("_", " ").title()
    return {
        "cli_command": command,
        "cli_help": f"Run the {display_name} pipeline module",
        "celery_task": _CELERY_TASK_NAME_OVERRIDES.get(
            module_id, f"run_{module_id}"
        ),
        "job_aliases": sorted({module_id, *module_aliases(module_id)}),
    }


def _persisted_schema_metadata(module_id: str) -> dict[str, Any]:
    """Return versioned persisted schemas for modules that have run storage."""
    metadata: dict[str, Any] = {
        "persisted_request_schema_version": None,
        "persisted_result_schema_version": None,
        "persisted_request_schema": None,
        "persisted_result_schema": None,
    }
    if module_id != "evidence_workspace":
        return metadata

    from med_research.pipeline.evidence_workspace.schemas import (
        WORKSPACE_REQUEST_SCHEMA_VERSION,
        WORKSPACE_RESULT_SCHEMA_VERSION,
        WorkspaceRequestV1,
        WorkspaceResultV1,
    )

    return {
        "persisted_request_schema_version": WORKSPACE_REQUEST_SCHEMA_VERSION,
        "persisted_result_schema_version": WORKSPACE_RESULT_SCHEMA_VERSION,
        "persisted_request_schema": WorkspaceRequestV1.model_json_schema(),
        "persisted_result_schema": WorkspaceResultV1.model_json_schema(),
    }


def celery_task_routes() -> dict[str, dict[str, str]]:
    """Build Celery task routing metadata from the registered module catalog."""
    return {
        entry["celery_task"]: {
            "queue": "pipeline",
            "routing_key": f"pipeline.{entry['module_id']}",
        }
        for entry in module_catalog()
    }


def module_catalog() -> list[dict[str, Any]]:
    """Build the canonical system catalog from registered adapter metadata."""
    return [
        {
            "module_id": module_id,
            "aliases": module_aliases(module_id),
            "depends_on": list(module.depends_on),
            "coverage_inputs": list(module.coverage_inputs()),
            "coverage_module": getattr(module, "_COVERAGE_MODULE", module_id),
            "result_contract": result_contract_name(module_id),
            "response_schema": result_contract_schema(module_id),
            "request_schema": module_request_schema(module_id),
            "request_validators": module_request_schema(module_id)["validators"],
            **_persisted_schema_metadata(module_id),
            **module_route_metadata(module_id),
        }
        for module_id in list_modules()
        for module in [get_module(module_id)]
    ]
