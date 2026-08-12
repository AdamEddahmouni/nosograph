from __future__ import annotations

from pathlib import Path

import pytest

from med_research.biomed.imports.mondo import MondoAdapter
from med_research.biomed.models import ResourcePolicy


@pytest.fixture
def mondo_policy() -> ResourcePolicy:
    return ResourcePolicy(
        resource_name="mondo",
        license_id="CC-BY-4.0",
        license_url="https://creativecommons.org/licenses/by/4.0/",
        redistribution_policy="redistributable",
    )


@pytest.fixture
def mondo_bundle(mondo_policy: ResourcePolicy):
    return MondoAdapter().parse(
        Path("tests/fixtures/biomed/mondo/minimal.json"),
        policy=mondo_policy,
    )
