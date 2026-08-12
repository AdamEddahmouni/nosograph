from __future__ import annotations

from pathlib import Path

import pytest

from med_research.biomed.imports.hpo import HpoOntologyAdapter
from med_research.biomed.imports.hpoa import HpoAnnotationAdapter
from med_research.biomed.imports.mondo import MondoAdapter
from med_research.biomed.imports.service import ImportService
from med_research.biomed.legacy.adapter import LegacyMigrationAdapter
from med_research.biomed.models import ResourcePolicy
from med_research.biomed.repository import BiomedicalRepository

FIXTURES = Path("tests/fixtures/biomed")


@pytest.fixture
def biomed_repository(tmp_path) -> BiomedicalRepository:
    repository = BiomedicalRepository(tmp_path / "biomedical.sqlite3")
    repository.initialize()
    service = ImportService(repository)

    mondo_policy = ResourcePolicy(
        resource_name="mondo",
        license_id="CC-BY-4.0",
        license_url="https://creativecommons.org/licenses/by/4.0/",
        redistribution_policy="redistributable",
    )
    service.import_bundle(
        MondoAdapter().parse(FIXTURES / "mondo" / "minimal.json", policy=mondo_policy)
    )

    hpo_policy = ResourcePolicy(
        resource_name="hp",
        license_id="custom",
        license_url="https://hpo.jax.org/app/license",
        redistribution_policy="user_supplied",
    )
    service.import_bundle(
        HpoOntologyAdapter().parse(FIXTURES / "hpo" / "minimal.json", policy=hpo_policy)
    )

    hpoa_policy = ResourcePolicy(
        resource_name="hpoa",
        license_id="custom",
        license_url="https://hpo.jax.org/app/license",
        redistribution_policy="user_supplied",
    )
    service.import_bundle(
        HpoAnnotationAdapter().parse(
            FIXTURES / "hpoa" / "minimal.tsv",
            policy=hpoa_policy,
            mondo_mappings={"OMIM:152700": "MONDO:0007915"},
        )
    )

    legacy_bundle = LegacyMigrationAdapter().build_bundle(["sle", "ra"])
    service.import_bundle(legacy_bundle)
    return repository
