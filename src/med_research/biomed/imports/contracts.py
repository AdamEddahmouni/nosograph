"""Import adapter protocol and shared contracts."""

from __future__ import annotations

from pathlib import Path
from typing import Protocol, runtime_checkable

from med_research.biomed.imports.models import ImportBundle
from med_research.biomed.models import ResourcePolicy


@runtime_checkable
class ImportAdapter(Protocol):
    """Parse a local ontology artifact into a staging bundle."""

    @property
    def resource_name(self) -> str: ...

    @property
    def supported_formats(self) -> tuple[str, ...]: ...

    def parse(self, path: Path, policy: ResourcePolicy, **kwargs: object) -> ImportBundle: ...
