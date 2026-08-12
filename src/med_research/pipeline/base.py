"""Common pipeline module interface.

This module introduces a minimal ABC so future work can add centralized
caching, progress callbacks, and uniform CLI/web wiring without refactoring
every engine at once. Migrate additional modules by subclassing
``BasePipelineModule`` in ``pipeline/<module>/adapter.py`` and delegating to
existing ``run``/``report`` helpers.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Generic, TypeVar

from typing_extensions import Unpack

from med_research.pipeline.adapter_options import AdapterOptions
from med_research.pipeline.provenance import ProvenanceMetadata

ResultT = TypeVar("ResultT")


@dataclass
class PipelineRunResult(Generic[ResultT]):
    """Normalized outcome from a registry-backed module run."""

    success: bool
    data: ResultT | None
    report_path: Path | None = None
    provenance: ProvenanceMetadata | None = None
    errors: list[str] = field(default_factory=list)


class BasePipelineModule(ABC, Generic[ResultT]):
    """Minimal contract shared by disease-aware analysis modules."""

    @property
    @abstractmethod
    def module_id(self) -> str:
        """Stable module identifier used in provenance metadata."""

    @abstractmethod
    def coverage_inputs(self) -> tuple[str, ...]:
        """Curated input keys passed to ``module_coverage()``."""

    @abstractmethod
    def run(self, disease_id: str, **opts: Unpack[AdapterOptions]) -> ResultT:
        """Execute the module for a disease and return typed raw results."""

    @abstractmethod
    def report(
        self,
        results: ResultT,
        disease_id: str,
        *,
        provenance: ProvenanceMetadata | None = None,
    ) -> Path:
        """Render an HTML report from ``run()`` output and return its path."""

    @abstractmethod
    def build_provenance(self, disease_id: str, **opts: Unpack[AdapterOptions]) -> ProvenanceMetadata:
        """Build reproducibility metadata for a disease run."""

    @property
    def depends_on(self) -> tuple[str, ...]:
        """Registry module IDs that must complete before this module runs."""

        return ()
