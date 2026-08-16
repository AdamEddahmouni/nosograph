from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from med_research.biomed.imports.hpo import HpoOntologyAdapter
from med_research.biomed.imports.hpoa import HpoAnnotationAdapter
from med_research.biomed.imports.mondo import MondoAdapter
from med_research.biomed.imports.service import ImportService
from med_research.biomed.legacy.adapter import LegacyMigrationAdapter
from med_research.biomed.models import ResourcePolicy
from med_research.biomed.repository import BiomedicalRepository
from med_research.web.dependencies_biomed import (
    get_biomedical_repository,
    reset_biomedical_repository,
)
from med_research.web.main import app

FIXTURES = Path("tests/fixtures/biomed")


@pytest.fixture(scope="module")
def biomed_repository(tmp_path_factory) -> BiomedicalRepository:
    tmp_path = tmp_path_factory.mktemp("biomed")
    repository = BiomedicalRepository(tmp_path / "biomedical.sqlite3")
    repository.initialize()
    service = ImportService(repository)

    mondo_policy = ResourcePolicy(
        resource_name="mondo",
        license_id="CC-BY-4.0",
        license_url="https://creativecommons.org/licenses/by/4.0/",
        redistribution_policy="redistributable",
    )
    mondo_bundle = MondoAdapter().parse(FIXTURES / "mondo" / "minimal.json", policy=mondo_policy)
    service.import_bundle(mondo_bundle)

    hpo_policy = ResourcePolicy(
        resource_name="hp",
        license_id="custom",
        license_url="https://hpo.jax.org/app/license",
        redistribution_policy="user_supplied",
    )
    hpo_bundle = HpoOntologyAdapter().parse(FIXTURES / "hpo" / "minimal.json", policy=hpo_policy)
    service.import_bundle(hpo_bundle)

    hpoa_policy = ResourcePolicy(
        resource_name="hpoa",
        license_id="custom",
        license_url="https://hpo.jax.org/app/license",
        redistribution_policy="user_supplied",
    )
    hpoa_bundle = HpoAnnotationAdapter().parse(
        FIXTURES / "hpoa" / "minimal.tsv",
        policy=hpoa_policy,
        mondo_mappings={"OMIM:152700": "MONDO:0007915"},
    )
    service.import_bundle(hpoa_bundle)

    legacy_bundle = LegacyMigrationAdapter().build_bundle(["sle", "ra"])
    service.import_bundle(legacy_bundle)
    return repository


@pytest.fixture
def seeded_biomed_db(biomed_repository: BiomedicalRepository):
    reset_biomedical_repository()
    app.dependency_overrides[get_biomedical_repository] = lambda: biomed_repository
    yield biomed_repository
    app.dependency_overrides.pop(get_biomedical_repository, None)
    reset_biomedical_repository()


@pytest.fixture
def client(seeded_biomed_db):
    with TestClient(app) as test_client:
        yield test_client
