from __future__ import annotations

import io
from contextlib import redirect_stdout
from dataclasses import dataclass
from pathlib import Path

from med_research.biomed.imports.hpo import HpoOntologyAdapter
from med_research.biomed.imports.hpoa import HpoAnnotationAdapter
from med_research.biomed.imports.mondo import MondoAdapter
from med_research.biomed.imports.service import ImportService
from med_research.biomed.legacy.adapter import LegacyMigrationAdapter
from med_research.biomed.models import ResourcePolicy
from med_research.biomed.repository import BiomedicalRepository
from med_research.cli import _build_parser, cmd_biomed

FIXTURES = Path("tests/fixtures/biomed")


@dataclass
class CliResult:
    exit_code: int
    output: str


def run_cli(*argv: str) -> CliResult:
    parser = _build_parser()
    stdout = io.StringIO()
    with redirect_stdout(stdout):
        args = parser.parse_args(list(argv))
        exit_code = cmd_biomed(args)
    return CliResult(exit_code=exit_code, output=stdout.getvalue())


def seed_biomed_db(db: Path) -> None:
    repository = BiomedicalRepository(db)
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
    service.import_bundle(LegacyMigrationAdapter().build_bundle(["sle", "ra"]))


def test_biomed_compare_cli_writes_run_id(tmp_path: Path) -> None:
    db = tmp_path / "biomedical.sqlite3"
    seed_biomed_db(db)
    result = run_cli(
        "biomed",
        "compare",
        "--left",
        "MONDO:0007915",
        "--right",
        "MONDO:0008390",
        "--db",
        str(db),
    )
    assert result.exit_code == 0
    assert "run_id" in result.output.lower()
