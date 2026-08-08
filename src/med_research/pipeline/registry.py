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

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from med_research.pipeline.base import BasePipelineModule

MODULE_REGISTRY: dict[str, type[BasePipelineModule]] = {}
_REGISTRATION_COMPLETE = False


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


def register_module(cls: type[BasePipelineModule]) -> type[BasePipelineModule]:
    """Decorator that records a pipeline adapter class in ``MODULE_REGISTRY``."""

    from med_research.pipeline.base import BasePipelineModule

    if not issubclass(cls, BasePipelineModule):
        raise TypeError(f"{cls.__name__} must subclass BasePipelineModule")

    module_id = cls().module_id
    if module_id in MODULE_REGISTRY:
        raise ValueError(f"Duplicate module_id registered: {module_id}")

    MODULE_REGISTRY[module_id] = cls
    return cls


def get_module(module_id: str) -> BasePipelineModule:
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
