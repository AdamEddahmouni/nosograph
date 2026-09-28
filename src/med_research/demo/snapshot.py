"""Build a small, redistributable biomedical snapshot from checked-in CI fixtures."""

from __future__ import annotations

import contextlib
import hashlib
import json
import sqlite3
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any

from med_research.diseases.identifiers import CI_VALIDATED_DISEASES

if TYPE_CHECKING:
    from med_research.biomed.repository import BiomedicalRepository
from med_research.web.config import REPO_ROOT

DEFAULT_FIXTURE_ROOT = REPO_ROOT / "tests" / "fixtures" / "biomed"
DEFAULT_DEMO_DB_PATH = REPO_ROOT / "data" / "demo" / "biomedical.sqlite3"

SUPPORTED_DISEASE_IDS = tuple(sorted(CI_VALIDATED_DISEASES))
REQUIRED_RESOURCES = ("mondo", "hp", "hpoa")
FIXTURE_RELATIVE_PATHS = {
    "mondo": Path("mondo") / "minimal.json",
    "hp": Path("hpo") / "minimal.json",
    "hpoa": Path("hpoa") / "minimal.tsv",
}


class DemoSnapshotError(Exception):
    """Raised when the offline demo snapshot cannot be built."""


def manifest_path_for(output: Path) -> Path:
    return output.with_name(f"{output.stem}.manifest.json")


def build_demo_snapshot(output: Path, *, fixture_root: Path | None = None) -> Path:
    """Initialize the canonical store, import fixtures, and write a manifest."""
    output = Path(output)
    root = Path(fixture_root or DEFAULT_FIXTURE_ROOT)
    fixtures = _resolve_fixtures(root)
    _validate_supported_diseases()

    output.parent.mkdir(parents=True, exist_ok=True)
    _remove_previous_output(output)

    from med_research.biomed.database import BiomedicalDatabase
    from med_research.biomed.imports.hpo import HpoOntologyAdapter
    from med_research.biomed.imports.hpoa import HpoAnnotationAdapter
    from med_research.biomed.imports.mondo import MondoAdapter
    from med_research.biomed.imports.service import ImportService
    from med_research.biomed.legacy.adapter import LegacyMigrationAdapter
    from med_research.biomed.legacy.manifest import legacy_disease_ids
    from med_research.biomed.models import ResourcePolicy
    from med_research.biomed.repository import BiomedicalRepository
    from med_research.biomed.schema import SCHEMA_VERSION

    connections: list[sqlite3.Connection] = []
    original_connect = BiomedicalDatabase.connect

    def _connect(self: BiomedicalDatabase) -> sqlite3.Connection:
        connection = original_connect(self)
        connections.append(connection)
        return connection

    BiomedicalDatabase.connect = _connect  # type: ignore[method-assign]
    try:
        repository = BiomedicalRepository(output)
        repository.initialize()
        service = ImportService(repository)
        adapters: dict[str, Any] = {
            "mondo": MondoAdapter(),
            "hp": HpoOntologyAdapter(),
            "hpoa": HpoAnnotationAdapter(),
        }
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
        }

        imported: list[dict[str, str]] = []
        for resource in REQUIRED_RESOURCES:
            artifact = fixtures[resource]
            parse_kwargs: dict[str, Any] = {"slim": False} if resource in {"mondo", "hp"} else {}
            if resource == "hpoa":
                parse_kwargs["mondo_mappings"] = _mondo_exact_mappings(repository)
            bundle = _parse_fixture(
                adapters[resource], artifact, policies[resource], resource, parse_kwargs
            )
            service.import_bundle(bundle, activate=True)
            imported.append(
                {
                    "resource_name": resource,
                    "checksum": bundle.snapshot.checksum,
                    "snapshot_id": str(bundle.snapshot.id),
                }
            )

        legacy_bundle = LegacyMigrationAdapter().build_bundle(legacy_disease_ids())
        service.import_bundle(legacy_bundle, activate=True)
        imported.append(
            {
                "resource_name": legacy_bundle.snapshot.resource_name,
                "checksum": legacy_bundle.snapshot.checksum,
                "snapshot_id": str(legacy_bundle.snapshot.id),
            }
        )
    finally:
        for connection in connections:
            with contextlib.suppress(sqlite3.Error):
                connection.close()
        BiomedicalDatabase.connect = original_connect  # type: ignore[method-assign]
        _finalize_sqlite(output)

    manifest = {
        "snapshot_version": _snapshot_version(fixtures),
        "generated_at": datetime.now(tz=UTC).date().isoformat(),
        "schema_version": SCHEMA_VERSION,
        "supported_disease_ids": list(SUPPORTED_DISEASE_IDS),
        "legacy_disease_ids": legacy_disease_ids(),
        "label": "fixture-backed demo snapshot (ci_validated-focused; not live connectors)",
        "fixtures": [
            {
                "resource": resource,
                "name": fixtures[resource].name,
                "checksum": _sha256(fixtures[resource]),
            }
            for resource in REQUIRED_RESOURCES
        ],
        "resources": imported,
    }
    manifest_path_for(output).write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return output


def _resolve_fixtures(fixture_root: Path) -> dict[str, Path]:
    resolved: dict[str, Path] = {}
    missing: list[str] = []
    for resource in REQUIRED_RESOURCES:
        path = fixture_root / FIXTURE_RELATIVE_PATHS[resource]
        if not path.is_file():
            missing.append(f"{resource} ({path})")
            continue
        resolved[resource] = path
    if missing:
        raise DemoSnapshotError("Missing required fixture(s): " + ", ".join(missing))
    return resolved


def _validate_supported_diseases() -> None:
    from med_research.diseases.base import Disease

    kg_fields = ("genes", "drugs", "pathways", "relationships", "profile")
    failures: list[str] = []
    for disease_id in SUPPORTED_DISEASE_IDS:
        try:
            disease = Disease(disease_id)
            checks = disease.validate()
        except (OSError, ValueError, KeyError, TypeError, AttributeError, RuntimeError) as exc:
            failures.append(f"{disease_id}: {exc}")
            continue
        bad = [f"{field}={checks.get(field)}" for field in kg_fields if checks.get(field) != "ok"]
        if bad:
            failures.append(f"{disease_id}: " + ", ".join(bad))
    if failures:
        raise DemoSnapshotError(
            "Supported disease module validation failed: " + "; ".join(failures)
        )


def _parse_fixture(
    adapter: Any, path: Path, policy: Any, resource: str, parse_kwargs: dict[str, Any]
):
    from med_research.biomed.errors import BiomedicalValidationError

    try:
        return adapter.parse(path, policy, **parse_kwargs)
    except BiomedicalValidationError as exc:
        raise DemoSnapshotError(f"Invalid {resource} fixture {path}: {exc}") from exc
    except (ValueError, OSError, json.JSONDecodeError) as exc:
        raise DemoSnapshotError(f"Malformed {resource} fixture {path}: {exc}") from exc


def _mondo_exact_mappings(repository: BiomedicalRepository) -> dict[str, str]:
    snapshot = repository.get_active_snapshot("mondo")
    if snapshot is None:
        return {}
    with repository.database.connect() as connection:
        rows = connection.execute(
            """
            SELECT subject_curie, object_curie FROM entity_mappings
            WHERE snapshot_id = ? AND relation = 'exact'
            """,
            (str(snapshot.id),),
        ).fetchall()
    return {row["object_curie"]: row["subject_curie"] for row in rows}


def _snapshot_version(fixtures: dict[str, Path]) -> str:
    digest = hashlib.sha256()
    for resource in REQUIRED_RESOURCES:
        digest.update(resource.encode("utf-8"))
        digest.update(b"\0")
        digest.update(_sha256(fixtures[resource]).encode("utf-8"))
        digest.update(b"\0")
    return f"demo-{digest.hexdigest()[:16]}"


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return f"sha256:{digest.hexdigest()}"


def _remove_previous_output(output: Path) -> None:
    for path in (output, manifest_path_for(output), Path(f"{output}-wal"), Path(f"{output}-shm")):
        if path.is_file():
            path.unlink()


def _finalize_sqlite(path: Path) -> None:
    if not path.is_file():
        return
    connection = sqlite3.connect(str(path), timeout=30)
    try:
        connection.execute("PRAGMA wal_checkpoint(TRUNCATE)")
        connection.execute("PRAGMA journal_mode = DELETE")
        connection.commit()
    finally:
        connection.close()
    for extra in (Path(f"{path}-wal"), Path(f"{path}-shm")):
        if extra.is_file():
            extra.unlink()
