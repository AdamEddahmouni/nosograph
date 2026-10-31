"""Validation helpers for the immutable public demo biomedical snapshot."""

from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from med_research.biomed.schema import SCHEMA_VERSION

REQUIRED_TABLES = frozenset(
    {
        "resource_snapshots",
        "active_snapshots",
        "entities",
        "entity_revisions",
        "claims",
        "claim_evidence",
    }
)
REQUIRED_RESOURCES = frozenset({"mondo", "hp", "hpoa"})


class DemoSnapshotValidationError(RuntimeError):
    """Raised when the configured demo snapshot is missing or inconsistent."""


@dataclass(frozen=True)
class DemoSnapshot:
    """Validated snapshot and manifest metadata."""

    database_path: Path
    manifest_path: Path
    manifest: dict[str, Any]


def validate_demo_snapshot(database_path: Path, manifest_path: Path) -> DemoSnapshot:
    """Validate the demo database and manifest without modifying either file."""
    database_path = Path(database_path)
    manifest_path = Path(manifest_path)
    if not database_path.is_file():
        raise DemoSnapshotValidationError(f"Demo database not found: {database_path}")
    if not manifest_path.is_file():
        raise DemoSnapshotValidationError(f"Demo manifest not found: {manifest_path}")

    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise DemoSnapshotValidationError(
            f"Demo manifest could not be read: {manifest_path}: {exc}"
        ) from exc
    if not isinstance(manifest, dict):
        raise DemoSnapshotValidationError("Demo manifest must contain a JSON object")

    try:
        connection = sqlite3.connect(
            f"file:{database_path.resolve()}?mode=ro",
            uri=True,
            timeout=2,
        )
        connection.row_factory = sqlite3.Row
        try:
            schema_version = int(connection.execute("PRAGMA user_version").fetchone()[0])
            if schema_version != SCHEMA_VERSION:
                raise DemoSnapshotValidationError(
                    f"Unsupported demo database schema version: {schema_version}"
                )
            tables = {
                str(row[0])
                for row in connection.execute(
                    "SELECT name FROM sqlite_master WHERE type = 'table'"
                ).fetchall()
            }
            missing_tables = sorted(REQUIRED_TABLES - tables)
            if missing_tables:
                raise DemoSnapshotValidationError(
                    "Demo database is missing required table(s): " + ", ".join(missing_tables)
                )
            rows = connection.execute(
                """
                SELECT a.resource_name, s.id, s.checksum
                FROM active_snapshots AS a
                JOIN resource_snapshots AS s ON s.id = a.snapshot_id
                """
            ).fetchall()
        finally:
            connection.close()
    except DemoSnapshotValidationError:
        raise
    except (OSError, sqlite3.Error) as exc:
        raise DemoSnapshotValidationError(
            f"Demo database could not be read: {database_path}: {exc}"
        ) from exc

    active = {str(row["resource_name"]): row for row in rows}
    missing_resources = sorted(REQUIRED_RESOURCES - active.keys())
    if missing_resources:
        raise DemoSnapshotValidationError(
            "Demo database has no active snapshot(s) for: " + ", ".join(missing_resources)
        )

    manifest_resources = manifest.get("resources")
    if not isinstance(manifest_resources, list):
        raise DemoSnapshotValidationError("Demo manifest resources must be a list")
    expected = {
        str(item.get("resource_name")): item
        for item in manifest_resources
        if isinstance(item, dict) and item.get("resource_name")
    }
    missing_manifest_resources = sorted(REQUIRED_RESOURCES - expected.keys())
    if missing_manifest_resources:
        raise DemoSnapshotValidationError(
            "Demo manifest has no resource metadata for: " + ", ".join(missing_manifest_resources)
        )
    for resource in sorted(REQUIRED_RESOURCES):
        actual_checksum = str(active[resource]["checksum"])
        expected_checksum = str(expected[resource].get("checksum", ""))
        if actual_checksum != expected_checksum:
            raise DemoSnapshotValidationError(
                f"Demo checksum mismatch for {resource}: "
                f"database={actual_checksum}, manifest={expected_checksum}"
            )
        expected_id = str(expected[resource].get("snapshot_id", ""))
        if expected_id and str(active[resource]["id"]) != expected_id:
            raise DemoSnapshotValidationError(
                f"Demo snapshot ID mismatch for {resource}: "
                f"database={active[resource]['id']}, manifest={expected_id}"
            )

    if manifest.get("schema_version") != SCHEMA_VERSION:
        raise DemoSnapshotValidationError(
            f"Demo manifest schema version does not match {SCHEMA_VERSION}"
        )
    if not manifest.get("snapshot_version"):
        raise DemoSnapshotValidationError("Demo manifest snapshot_version is required")
    if not isinstance(manifest.get("supported_disease_ids"), list):
        raise DemoSnapshotValidationError("Demo manifest supported_disease_ids must be a list")

    return DemoSnapshot(
        database_path=database_path,
        manifest_path=manifest_path,
        manifest=manifest,
    )
