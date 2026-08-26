"""Repository for the canonical biomedical SQLite store."""

from __future__ import annotations

import json
import sqlite3
from contextlib import AbstractContextManager
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Generic, TypeVar
from uuid import UUID

from med_research.biomed.database import BiomedicalDatabase
from med_research.biomed.errors import (
    BiomedicalValidationError,
    RunTransitionError,
    SnapshotConflictError,
)
from med_research.biomed.identifiers import (
    canonical_json,
    claim_evidence_uuid,
    entity_revision_uuid,
    mapping_uuid,
    normalize_curie,
    research_run_fingerprint,
    research_run_uuid,
)
from med_research.biomed.models import (
    Claim,
    ClaimEvidence,
    Entity,
    EntityMapping,
    EntityRevision,
    EntityType,
    EvidenceDirection,
    MappingKind,
    Predicate,
    ResearchRun,
    ResearchRunCreate,
    ResourceSnapshot,
    RunStatus,
)

T = TypeVar("T")

_TRANSITIONS: dict[RunStatus, set[RunStatus]] = {
    RunStatus.PENDING: {RunStatus.RUNNING},
    RunStatus.RUNNING: {RunStatus.COMPLETED, RunStatus.FAILED},
    RunStatus.COMPLETED: set(),
    RunStatus.FAILED: set(),
}


@dataclass(frozen=True)
class Page(Generic[T]):
    items: list[T]
    total: int
    limit: int
    offset: int


@dataclass(frozen=True)
class EntitySummary:
    entity: Entity
    label: str


@dataclass(frozen=True)
class EntityView:
    entity: Entity
    revision: EntityRevision | None
    mappings: list[EntityMapping]


@dataclass(frozen=True)
class ClaimView:
    claim: Claim
    subject_curie: str
    object_curie: str
    evidence: list[ClaimEvidence]


def _uuid_str(value: UUID | str | None) -> str | None:
    if value is None:
        return None
    return str(value)


def _parse_uuid(value: str) -> UUID:
    return UUID(value)


def _dt_to_str(value: datetime | None) -> str | None:
    if value is None:
        return None
    if value.tzinfo is None:
        value = value.replace(tzinfo=UTC)
    return value.astimezone(UTC).isoformat()


def _dt_from_str(value: str | None) -> datetime:
    if not value:
        return datetime.now(UTC)
    return datetime.fromisoformat(value)


def _json_loads(value: str, default: Any) -> Any:
    if not value:
        return default
    return json.loads(value)


def _insert_row_sql(table: str, row: dict[str, Any]) -> str:
    """Build INSERT from typed row keys; values are bound via placeholders."""
    columns = ", ".join(row)
    placeholders = ", ".join("?" for _ in row)
    return f"INSERT INTO {table} ({columns}) VALUES ({placeholders})"  # nosec B608


def _entity_search_count_sql(type_clause: str) -> str:
    return (
        f"SELECT COUNT(DISTINCT e.id) AS total FROM entities e "
        f"JOIN entity_names n ON n.entity_id = e.id "
        f"WHERE n.name_normalized LIKE ? {type_clause}"  # nosec B608
    )


def _entity_search_rows_sql(type_clause: str) -> str:
    return (
        f"SELECT DISTINCT e.id, e.primary_curie, e.entity_type, e.created_in_snapshot_id, "
        f"COALESCE(r.label, e.primary_curie) AS label FROM entities e "
        f"JOIN entity_names n ON n.entity_id = e.id "
        f"LEFT JOIN entity_revisions r ON r.entity_id = e.id "
        f"WHERE n.name_normalized LIKE ? {type_clause} "  # nosec B608
        f"ORDER BY label COLLATE NOCASE, e.primary_curie LIMIT ? OFFSET ?"
    )


def _claims_where_sql(where: str) -> str:
    return f"SELECT * FROM claims WHERE {where} ORDER BY predicate, object_curie, id"  # nosec B608


def _snapshot_count_sql(where: str) -> str:
    return f"SELECT COUNT(*) AS total FROM resource_snapshots s {where}"  # nosec B608


def _snapshot_list_sql(where: str) -> str:
    return (
        f"SELECT s.* FROM resource_snapshots s {where} "  # nosec B608
        "ORDER BY s.resource_name, s.version, s.id LIMIT ? OFFSET ?"
    )


# Dynamic INSERT/SELECT fragments use typed model field names, not user input.
class BiomedicalRepository:
    def __init__(self, path: Path) -> None:
        self.database = BiomedicalDatabase(path)

    def initialize(self) -> None:
        self.database.initialize()

    def transaction(self) -> AbstractContextManager[sqlite3.Connection]:
        return self.database.transaction()

    def upsert_snapshot(self, snapshot: ResourceSnapshot) -> ResourceSnapshot:
        with self.transaction() as connection:
            conflict = connection.execute(
                """
                SELECT id, checksum FROM resource_snapshots
                WHERE resource_name = ? AND version = ?
                """,
                (snapshot.resource_name, snapshot.version),
            ).fetchone()
            if conflict is not None and conflict["checksum"] != snapshot.checksum:
                raise SnapshotConflictError(
                    f"Snapshot {snapshot.resource_name}@{snapshot.version} "
                    f"already exists with checksum {conflict['checksum']}"
                )
            existing = connection.execute(
                "SELECT * FROM resource_snapshots WHERE id = ?",
                (_uuid_str(snapshot.id),),
            ).fetchone()
            row = self._snapshot_to_row(snapshot)
            if existing is None:
                connection.execute(
                    _insert_row_sql("resource_snapshots", row),
                    tuple(row.values()),
                )
            else:
                stored = self._row_to_snapshot(existing)
                if (
                    stored.resource_name != snapshot.resource_name
                    or stored.version != snapshot.version
                    or stored.checksum != snapshot.checksum
                ):
                    raise BiomedicalValidationError(
                        f"Snapshot {_uuid_str(snapshot.id)} payload differs from stored record"
                    )
            return snapshot

    def activate_snapshot(self, resource_name: str, snapshot_id: UUID) -> None:
        with self.transaction() as connection:
            exists = connection.execute(
                "SELECT id FROM resource_snapshots WHERE id = ? AND resource_name = ?",
                (_uuid_str(snapshot_id), resource_name),
            ).fetchone()
            if exists is None:
                raise BiomedicalValidationError(
                    f"Snapshot {_uuid_str(snapshot_id)} not found for resource {resource_name}"
                )
            connection.execute(
                """
                INSERT INTO active_snapshots (resource_name, snapshot_id)
                VALUES (?, ?)
                ON CONFLICT(resource_name) DO UPDATE SET snapshot_id = excluded.snapshot_id
                """,
                (resource_name, _uuid_str(snapshot_id)),
            )

    def bulk_import_bundle(self, bundle: Any, *, activate: bool = True) -> None:
        """Import an ontology bundle in a single transaction with batched writes."""
        from med_research.biomed.imports.models import ImportBundle

        if not isinstance(bundle, ImportBundle):
            raise TypeError("bundle must be an ImportBundle")

        snapshot = bundle.snapshot
        with self.transaction() as connection:
            connection.execute("PRAGMA synchronous=OFF")
            connection.execute("PRAGMA temp_store=MEMORY")

            conflict = connection.execute(
                """
                SELECT id, checksum FROM resource_snapshots
                WHERE resource_name = ? AND version = ?
                """,
                (snapshot.resource_name, snapshot.version),
            ).fetchone()
            if conflict is not None:
                if conflict["checksum"] != snapshot.checksum:
                    raise SnapshotConflictError(
                        f"Snapshot {snapshot.resource_name}@{snapshot.version} "
                        f"already exists with checksum {conflict['checksum']}"
                    )
                if activate:
                    connection.execute(
                        """
                        INSERT INTO active_snapshots (resource_name, snapshot_id)
                        VALUES (?, ?)
                        ON CONFLICT(resource_name) DO UPDATE SET snapshot_id = excluded.snapshot_id
                        """,
                        (snapshot.resource_name, conflict["id"]),
                    )
                return

            row = self._snapshot_to_row(snapshot)
            connection.execute(
                _insert_row_sql("resource_snapshots", row),
                tuple(row.values()),
            )

            self._executemany_chunked(
                connection,
                """
                INSERT OR IGNORE INTO entities (id, primary_curie, entity_type, created_in_snapshot_id)
                VALUES (?, ?, ?, ?)
                """,
                [
                    (
                        _uuid_str(entity.id),
                        entity.primary_curie,
                        entity.entity_type.value,
                        _uuid_str(entity.created_in_snapshot_id)
                        if entity.created_in_snapshot_id
                        else "",
                    )
                    for entity in bundle.entities
                ],
            )

            revision_rows = [self._revision_to_row(revision) for revision in bundle.revisions]
            if revision_rows:
                columns = list(revision_rows[0])
                self._executemany_chunked(
                    connection,
                    f"""
                    INSERT OR IGNORE INTO entity_revisions ({", ".join(columns)})
                    VALUES ({", ".join("?" for _ in columns)})
                    """,
                    [tuple(row.values()) for row in revision_rows],
                )

            name_rows: list[tuple[str, str, str, str]] = []
            for revision in bundle.revisions:
                names = [revision.label, *revision.synonyms, *revision.alt_labels]
                for name in names:
                    cleaned = (name or "").strip()
                    if not cleaned:
                        continue
                    name_rows.append(
                        (
                            str(revision.entity_id),
                            str(revision.snapshot_id),
                            cleaned,
                            cleaned.lower(),
                        )
                    )
            self._executemany_chunked(
                connection,
                """
                INSERT OR IGNORE INTO entity_names (entity_id, snapshot_id, name, name_normalized)
                VALUES (?, ?, ?, ?)
                """,
                name_rows,
            )

            mapping_rows = [
                self._mapping_to_row(
                    mapping.model_copy(
                        update={
                            "subject_curie": normalize_curie(mapping.subject_curie),
                            "object_curie": normalize_curie(mapping.object_curie),
                        }
                    )
                )
                for mapping in bundle.mappings
            ]
            if mapping_rows:
                columns = list(mapping_rows[0])
                self._executemany_chunked(
                    connection,
                    f"""
                    INSERT OR IGNORE INTO entity_mappings ({", ".join(columns)})
                    VALUES ({", ".join("?" for _ in columns)})
                    """,
                    [tuple(row.values()) for row in mapping_rows],
                )

            claim_rows = [
                self._claim_to_row(
                    claim.model_copy(
                        update={
                            "subject_curie": normalize_curie(claim.subject_curie),
                            "object_curie": normalize_curie(claim.object_curie),
                        }
                    )
                )
                for claim in bundle.claims
            ]
            if claim_rows:
                columns = list(claim_rows[0])
                self._executemany_chunked(
                    connection,
                    f"""
                    INSERT OR IGNORE INTO claims ({", ".join(columns)})
                    VALUES ({", ".join("?" for _ in columns)})
                    """,
                    [tuple(row.values()) for row in claim_rows],
                )

            evidence_rows = [self._evidence_to_row(item) for item in bundle.evidence]
            if evidence_rows:
                columns = list(evidence_rows[0])
                self._executemany_chunked(
                    connection,
                    f"""
                    INSERT OR IGNORE INTO claim_evidence ({", ".join(columns)})
                    VALUES ({", ".join("?" for _ in columns)})
                    """,
                    [tuple(row.values()) for row in evidence_rows],
                )

            if activate:
                connection.execute(
                    """
                    INSERT INTO active_snapshots (resource_name, snapshot_id)
                    VALUES (?, ?)
                    ON CONFLICT(resource_name) DO UPDATE SET snapshot_id = excluded.snapshot_id
                    """,
                    (snapshot.resource_name, _uuid_str(snapshot.id)),
                )

    @staticmethod
    def _executemany_chunked(
        connection: sqlite3.Connection,
        sql: str,
        rows: list[tuple[Any, ...]],
        *,
        chunk_size: int = 5000,
    ) -> None:
        if not rows:
            return
        for offset in range(0, len(rows), chunk_size):
            connection.executemany(sql, rows[offset : offset + chunk_size])

    def get_active_snapshot(self, resource_name: str) -> ResourceSnapshot | None:
        with self.database.connect() as connection:
            row = connection.execute(
                """
                SELECT s.* FROM resource_snapshots s
                JOIN active_snapshots a ON a.snapshot_id = s.id
                WHERE a.resource_name = ?
                """,
                (resource_name,),
            ).fetchone()
            return self._row_to_snapshot(row) if row else None

    def upsert_entity(self, entity: Entity) -> Entity:
        with self.transaction() as connection:
            existing = connection.execute(
                "SELECT * FROM entities WHERE primary_curie = ?",
                (entity.primary_curie,),
            ).fetchone()
            if existing is None:
                connection.execute(
                    """
                    INSERT INTO entities (id, primary_curie, entity_type, created_in_snapshot_id)
                    VALUES (?, ?, ?, ?)
                    """,
                    (
                        _uuid_str(entity.id),
                        entity.primary_curie,
                        entity.entity_type.value,
                        _uuid_str(entity.created_in_snapshot_id)
                        if entity.created_in_snapshot_id
                        else "",
                    ),
                )
                return entity
            stored = self._row_to_entity(existing)
            if stored.entity_type != entity.entity_type:
                raise BiomedicalValidationError(
                    f"CURIE {entity.primary_curie} is already assigned to {stored.entity_type.value}"
                )
            if (
                stored.primary_curie != entity.primary_curie
                or stored.entity_type != entity.entity_type
            ):
                raise BiomedicalValidationError(
                    f"Entity {_uuid_str(entity.id)} payload differs from stored record"
                )
            return stored

    def add_entity_revision(self, revision: EntityRevision) -> EntityRevision:
        with self.transaction() as connection:
            existing = connection.execute(
                "SELECT * FROM entity_revisions WHERE id = ?",
                (_uuid_str(revision.id),),
            ).fetchone()
            row = self._revision_to_row(revision)
            if existing is None:
                connection.execute(
                    _insert_row_sql("entity_revisions", row),
                    tuple(row.values()),
                )
                self._index_revision_names(connection, revision)
            else:
                stored = self._row_to_revision(existing)
                if stored != revision:
                    raise BiomedicalValidationError(
                        f"Revision {_uuid_str(revision.id)} payload differs from stored record"
                    )
            return revision

    def add_entity_mapping(self, mapping: EntityMapping) -> EntityMapping:
        with self.transaction() as connection:
            existing = connection.execute(
                "SELECT * FROM entity_mappings WHERE id = ?",
                (_uuid_str(mapping.id),),
            ).fetchone()
            normalized = mapping.model_copy(
                update={
                    "subject_curie": normalize_curie(mapping.subject_curie),
                    "object_curie": normalize_curie(mapping.object_curie),
                }
            )
            row = self._mapping_to_row(normalized)
            if existing is None:
                connection.execute(
                    _insert_row_sql("entity_mappings", row),
                    tuple(row.values()),
                )
            else:
                stored = self._row_to_mapping(existing)
                if stored != normalized:
                    raise BiomedicalValidationError(
                        f"Mapping {_uuid_str(mapping.id)} payload differs from stored record"
                    )
            return normalized

    def resolve_exact_curie(self, curie: str) -> str | None:
        normalized = normalize_curie(curie)
        with self.database.connect() as connection:
            row = connection.execute(
                """
                SELECT subject_curie FROM entity_mappings
                WHERE object_curie = ? AND relation = ?
                ORDER BY id
                LIMIT 1
                """,
                (normalized, MappingKind.EXACT.value),
            ).fetchone()
            return row["subject_curie"] if row else None

    def get_entity(self, curie: str) -> EntityView | None:
        normalized = normalize_curie(curie)
        with self.database.connect() as connection:
            entity_row = connection.execute(
                "SELECT * FROM entities WHERE primary_curie = ?",
                (normalized,),
            ).fetchone()
            if entity_row is None:
                return None
            entity = self._row_to_entity(entity_row)
            revision = self._latest_revision(connection, entity.id)
            mappings = self._entity_mappings(connection, normalized)
            return EntityView(entity=entity, revision=revision, mappings=mappings)

    def search_entities(
        self,
        query: str,
        *,
        entity_type: EntityType | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> Page[EntitySummary]:
        if not 1 <= limit <= 200:
            raise BiomedicalValidationError("limit must be between 1 and 200")
        if offset < 0:
            raise BiomedicalValidationError("offset must be >= 0")
        needle = query.strip().lower()
        if not needle:
            return Page(items=[], total=0, limit=limit, offset=offset)
        with self.database.connect() as connection:
            params: list[Any] = [f"%{needle}%"]
            type_clause = ""
            if entity_type is not None:
                type_clause = "AND e.entity_type = ?"
                params.append(entity_type.value)
            total = connection.execute(
                _entity_search_count_sql(type_clause),
                params,
            ).fetchone()["total"]
            rows = connection.execute(
                _entity_search_rows_sql(type_clause),
                [*params, limit, offset],
            ).fetchall()
            items = [
                EntitySummary(
                    entity=Entity(
                        id=_parse_uuid(row["id"]),
                        primary_curie=row["primary_curie"],
                        entity_type=EntityType(row["entity_type"]),
                        created_in_snapshot_id=_parse_uuid(row["created_in_snapshot_id"]),
                    ),
                    label=row["label"],
                )
                for row in rows
            ]
            return Page(items=items, total=total, limit=limit, offset=offset)

    def add_claim(self, claim: Claim) -> Claim:
        with self.transaction() as connection:
            normalized = claim.model_copy(
                update={
                    "subject_curie": normalize_curie(claim.subject_curie),
                    "object_curie": normalize_curie(claim.object_curie),
                }
            )
            existing = connection.execute(
                "SELECT * FROM claims WHERE id = ?",
                (_uuid_str(normalized.id),),
            ).fetchone()
            row = self._claim_to_row(normalized)
            if existing is None:
                connection.execute(
                    _insert_row_sql("claims", row),
                    tuple(row.values()),
                )
            else:
                stored = self._row_to_claim(existing)
                if stored != normalized:
                    raise BiomedicalValidationError(
                        f"Claim {_uuid_str(normalized.id)} payload differs from stored record"
                    )
            return normalized

    def add_claim_evidence(self, evidence: ClaimEvidence) -> ClaimEvidence:
        with self.transaction() as connection:
            existing = connection.execute(
                "SELECT * FROM claim_evidence WHERE id = ?",
                (_uuid_str(evidence.id),),
            ).fetchone()
            row = self._evidence_to_row(evidence)
            if existing is None:
                connection.execute(
                    _insert_row_sql("claim_evidence", row),
                    tuple(row.values()),
                )
            else:
                stored = self._row_to_evidence(existing)
                if stored != evidence:
                    raise BiomedicalValidationError(
                        f"Evidence {_uuid_str(evidence.id)} payload differs from stored record"
                    )
            return evidence

    def list_claims(
        self,
        subject_curie: str,
        *,
        predicate: Predicate | None = None,
    ) -> list[ClaimView]:
        return self._list_claim_rows(subject_curie=subject_curie, predicate=predicate)

    def list_claims_by_object(
        self,
        object_curie: str,
        *,
        predicate: Predicate | None = None,
    ) -> list[ClaimView]:
        return self._list_claim_rows(object_curie=object_curie, predicate=predicate)

    def get_claim_by_id(self, claim_id: UUID) -> ClaimView | None:
        with self.database.connect() as connection:
            row = connection.execute(
                "SELECT * FROM claims WHERE id = ?",
                (_uuid_str(claim_id),),
            ).fetchone()
            if row is None:
                return None
            claim = self._row_to_claim(row)
            evidence_rows = connection.execute(
                "SELECT * FROM claim_evidence WHERE claim_id = ? ORDER BY direction, id",
                (_uuid_str(claim.id),),
            ).fetchall()
            evidence = [self._row_to_evidence(item) for item in evidence_rows]
            return ClaimView(
                claim=claim,
                subject_curie=claim.subject_curie,
                object_curie=claim.object_curie,
                evidence=evidence,
            )

    def _list_claim_rows(
        self,
        *,
        subject_curie: str | None = None,
        object_curie: str | None = None,
        predicate: Predicate | None = None,
    ) -> list[ClaimView]:
        if subject_curie is None and object_curie is None:
            raise BiomedicalValidationError("subject_curie or object_curie is required")
        with self.database.connect() as connection:
            params: list[Any] = []
            clauses: list[str] = []
            if subject_curie is not None:
                clauses.append("subject_curie = ?")
                params.append(normalize_curie(subject_curie))
            if object_curie is not None:
                clauses.append("object_curie = ?")
                params.append(normalize_curie(object_curie))
            if predicate is not None:
                clauses.append("predicate = ?")
                params.append(predicate.value)
            where = " AND ".join(clauses)
            rows = connection.execute(
                _claims_where_sql(where),
                params,
            ).fetchall()
            views: list[ClaimView] = []
            for row in rows:
                claim = self._row_to_claim(row)
                evidence_rows = connection.execute(
                    "SELECT * FROM claim_evidence WHERE claim_id = ? ORDER BY direction, id",
                    (_uuid_str(claim.id),),
                ).fetchall()
                evidence = [self._row_to_evidence(item) for item in evidence_rows]
                views.append(
                    ClaimView(
                        claim=claim,
                        subject_curie=claim.subject_curie,
                        object_curie=claim.object_curie,
                        evidence=evidence,
                    )
                )
            return views

    def get_snapshot(self, snapshot_id: UUID) -> ResourceSnapshot | None:
        with self.database.connect() as connection:
            row = connection.execute(
                "SELECT * FROM resource_snapshots WHERE id = ?",
                (_uuid_str(snapshot_id),),
            ).fetchone()
            return self._row_to_snapshot(row) if row else None

    def list_snapshots(
        self,
        *,
        resource_name: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> Page[ResourceSnapshot]:
        if not 1 <= limit <= 200:
            raise BiomedicalValidationError("limit must be between 1 and 200")
        if offset < 0:
            raise BiomedicalValidationError("offset must be >= 0")
        with self.database.connect() as connection:
            params: list[Any] = []
            where = ""
            if resource_name is not None:
                where = "WHERE s.resource_name = ?"
                params.append(resource_name)
            total = connection.execute(
                _snapshot_count_sql(where),
                params,
            ).fetchone()["total"]
            rows = connection.execute(
                _snapshot_list_sql(where),
                [*params, limit, offset],
            ).fetchall()
            return Page(
                items=[self._row_to_snapshot(row) for row in rows],
                total=total,
                limit=limit,
                offset=offset,
            )

    def list_active_snapshots(self) -> list[ResourceSnapshot]:
        with self.database.connect() as connection:
            rows = connection.execute(
                """
                SELECT s.* FROM resource_snapshots s
                JOIN active_snapshots a ON a.snapshot_id = s.id
                ORDER BY s.resource_name
                """
            ).fetchall()
            return [self._row_to_snapshot(row) for row in rows]

    def claim_is_current(self, claim_id: UUID) -> bool:
        with self.database.connect() as connection:
            superseded = connection.execute(
                "SELECT id FROM claims WHERE supersedes_claim_id = ? LIMIT 1",
                (_uuid_str(claim_id),),
            ).fetchone()
            if superseded is not None:
                return False
            evidence_rows = connection.execute(
                "SELECT snapshot_id FROM claim_evidence WHERE claim_id = ?",
                (_uuid_str(claim_id),),
            ).fetchall()
            if not evidence_rows:
                return False
            for row in evidence_rows:
                active = connection.execute(
                    """
                    SELECT 1 FROM active_snapshots a
                    JOIN resource_snapshots s ON s.id = a.snapshot_id
                    WHERE a.snapshot_id = ?
                    """,
                    (row["snapshot_id"],),
                ).fetchone()
                if active is not None:
                    return True
            return False

    def create_research_run(self, spec: ResearchRunCreate) -> ResearchRun:
        fingerprint_payload = {
            "run_type": spec.run_type,
            "parent_run_id": str(spec.parent_run_id) if spec.parent_run_id else None,
            "algorithm_id": spec.algorithm_id,
            "algorithm_version": spec.algorithm_version,
            "software_version": spec.software_version,
            "parameters": spec.parameters,
            "snapshot_ids": sorted(str(item) for item in spec.snapshot_ids),
            "claim_ids": sorted(str(item) for item in spec.claim_ids),
            "input_query": spec.input_query,
        }
        fingerprint = research_run_fingerprint(fingerprint_payload)
        run_id = research_run_uuid(fingerprint)
        now = datetime.now(tz=UTC)
        run = ResearchRun(
            id=run_id,
            parent_run_id=spec.parent_run_id,
            run_type=spec.run_type,
            status=RunStatus.PENDING,
            fingerprint=fingerprint,
            algorithm_id=spec.algorithm_id,
            algorithm_version=spec.algorithm_version,
            software_version=spec.software_version,
            parameters=dict(spec.parameters),
            snapshot_ids=list(spec.snapshot_ids),
            claim_ids=list(spec.claim_ids),
            input_query=spec.input_query,
            created_at=now,
        )
        with self.transaction() as connection:
            existing = connection.execute(
                "SELECT * FROM research_runs WHERE fingerprint = ?",
                (fingerprint,),
            ).fetchone()
            if existing is not None:
                return self._row_to_run(existing)
            inserted = connection.execute(
                """
                INSERT OR IGNORE INTO research_runs (
                    id, parent_run_id, run_type, status, fingerprint,
                    algorithm_id, algorithm_version, software_version,
                    parameters_json, snapshot_ids_json, claim_ids_json,
                    input_query, result_json, warnings_json,
                    started_at, finished_at, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    _uuid_str(run.id),
                    _uuid_str(run.parent_run_id) if run.parent_run_id else None,
                    run.run_type,
                    run.status.value,
                    run.fingerprint,
                    run.algorithm_id,
                    run.algorithm_version,
                    run.software_version,
                    canonical_json(run.parameters),
                    canonical_json([str(item) for item in run.snapshot_ids]),
                    canonical_json([str(item) for item in run.claim_ids]),
                    run.input_query,
                    None,
                    canonical_json(run.warnings),
                    None,
                    None,
                    _dt_to_str(run.created_at),
                ),
            )
            if inserted.rowcount == 0:
                existing = connection.execute(
                    "SELECT * FROM research_runs WHERE fingerprint = ?",
                    (fingerprint,),
                ).fetchone()
                if existing is None:
                    raise BiomedicalValidationError(
                        f"Research run {run.id} could not be created or replayed"
                    )
                return self._row_to_run(existing)
            for snapshot_id in run.snapshot_ids:
                connection.execute(
                    "INSERT INTO research_run_snapshots (run_id, snapshot_id) VALUES (?, ?)",
                    (_uuid_str(run.id), _uuid_str(snapshot_id)),
                )
        return run

    def get_research_run(self, run_id: UUID) -> ResearchRun | None:
        with self.database.connect() as connection:
            row = connection.execute(
                "SELECT * FROM research_runs WHERE id = ?",
                (_uuid_str(run_id),),
            ).fetchone()
            return self._row_to_run(row) if row else None

    def list_research_runs(self, *, limit: int = 50, offset: int = 0) -> Page[ResearchRun]:
        if not 1 <= limit <= 200:
            raise BiomedicalValidationError("limit must be between 1 and 200")
        if offset < 0:
            raise BiomedicalValidationError("offset must be >= 0")
        with self.database.connect() as connection:
            total = connection.execute("SELECT COUNT(*) AS total FROM research_runs").fetchone()[
                "total"
            ]
            rows = connection.execute(
                """
                SELECT * FROM research_runs
                ORDER BY created_at DESC, id
                LIMIT ? OFFSET ?
                """,
                (limit, offset),
            ).fetchall()
            return Page(
                items=[self._row_to_run(row) for row in rows],
                total=total,
                limit=limit,
                offset=offset,
            )

    def transition_research_run(
        self,
        run_id: UUID,
        status: RunStatus,
        *,
        result: dict[str, Any] | None = None,
        warnings: list[str] | None = None,
    ) -> ResearchRun:
        with self.transaction() as connection:
            row = connection.execute(
                "SELECT * FROM research_runs WHERE id = ?",
                (_uuid_str(run_id),),
            ).fetchone()
            if row is None:
                raise BiomedicalValidationError(f"Research run {_uuid_str(run_id)} not found")
            current = self._row_to_run(row)
            allowed = _TRANSITIONS.get(current.status, set())
            if status not in allowed:
                if current.status in {RunStatus.COMPLETED, RunStatus.FAILED}:
                    raise RunTransitionError("Cannot transition a terminal research run")
                raise RunTransitionError(
                    f"Invalid transition from {current.status.value} to {status.value}"
                )
            started_at = current.started_at
            finished_at = current.finished_at
            result_payload = current.result
            warning_payload = list(current.warnings)
            if status is RunStatus.RUNNING:
                started_at = datetime.now(tz=UTC)
            if status is RunStatus.COMPLETED:
                if result is None:
                    raise BiomedicalValidationError("Completed runs require a result payload")
                finished_at = datetime.now(tz=UTC)
                result_payload = result
                warning_payload = list(warnings or [])
            if status is RunStatus.FAILED:
                if not warnings:
                    raise BiomedicalValidationError("Failed runs require warnings")
                finished_at = datetime.now(tz=UTC)
                warning_payload = list(warnings)
            connection.execute(
                """
                UPDATE research_runs
                SET status = ?, result_json = ?, warnings_json = ?, started_at = ?, finished_at = ?
                WHERE id = ?
                """,
                (
                    status.value,
                    canonical_json(result_payload) if result_payload is not None else None,
                    canonical_json(warning_payload),
                    _dt_to_str(started_at),
                    _dt_to_str(finished_at),
                    _uuid_str(run_id),
                ),
            )
            updated = connection.execute(
                "SELECT * FROM research_runs WHERE id = ?",
                (_uuid_str(run_id),),
            ).fetchone()
            return self._row_to_run(updated)

    def _latest_revision(
        self, connection: sqlite3.Connection, entity_id: UUID
    ) -> EntityRevision | None:
        row = connection.execute(
            """
            SELECT r.* FROM entity_revisions r
            LEFT JOIN active_snapshots a ON a.snapshot_id = r.snapshot_id
            WHERE r.entity_id = ?
            ORDER BY CASE WHEN a.snapshot_id IS NOT NULL THEN 0 ELSE 1 END, r.id DESC
            LIMIT 1
            """,
            (_uuid_str(entity_id),),
        ).fetchone()
        return self._row_to_revision(row) if row else None

    def _entity_mappings(
        self, connection: sqlite3.Connection, subject_curie: str
    ) -> list[EntityMapping]:
        rows = connection.execute(
            """
            SELECT * FROM entity_mappings
            WHERE subject_curie = ? OR object_curie = ?
            ORDER BY relation, object_curie
            """,
            (subject_curie, subject_curie),
        ).fetchall()
        return [self._row_to_mapping(row) for row in rows]

    def _index_revision_names(
        self, connection: sqlite3.Connection, revision: EntityRevision
    ) -> None:
        names = [revision.label, *revision.synonyms, *revision.alt_labels]
        connection.execute(
            "DELETE FROM entity_names WHERE entity_id = ? AND snapshot_id = ?",
            (_uuid_str(revision.entity_id), _uuid_str(revision.snapshot_id)),
        )
        for name in names:
            if not name:
                continue
            cleaned = name.strip()
            if not cleaned:
                continue
            connection.execute(
                """
                INSERT OR IGNORE INTO entity_names (entity_id, snapshot_id, name, name_normalized)
                VALUES (?, ?, ?, ?)
                """,
                (
                    _uuid_str(revision.entity_id),
                    _uuid_str(revision.snapshot_id),
                    cleaned,
                    cleaned.lower(),
                ),
            )

    def _snapshot_to_row(self, snapshot: ResourceSnapshot) -> dict[str, Any]:
        return {
            "id": _uuid_str(snapshot.id),
            "resource_name": snapshot.resource_name,
            "version": snapshot.version,
            "checksum": snapshot.checksum,
            "name": snapshot.name or "",
            "namespace_prefix": snapshot.namespace_prefix or "",
            "source_url": snapshot.source_url or "",
            "artifact_format": snapshot.artifact_format or "",
            "upstream_version": snapshot.upstream_version or "",
            "version_iri": snapshot.version_iri,
            "artifact_size": snapshot.artifact_size,
            "license_id": snapshot.license_id,
            "license_url": snapshot.license_url,
            "attribution": snapshot.attribution,
            "redistribution_policy": snapshot.redistribution_policy,
            "retrieved_at": _dt_to_str(snapshot.retrieved_at),
            "imported_at": _dt_to_str(snapshot.imported_at),
            "importer_name": snapshot.importer_name,
            "importer_version": snapshot.importer_version,
            "counts_json": canonical_json(snapshot.counts),
            "warnings_json": canonical_json(snapshot.warnings),
            "manifest_fingerprint": snapshot.manifest_fingerprint,
        }

    def _row_to_snapshot(self, row: sqlite3.Row) -> ResourceSnapshot:
        return ResourceSnapshot(
            id=_parse_uuid(row["id"]),
            resource_name=row["resource_name"],
            version=row["version"],
            checksum=row["checksum"],
            name=row["name"],
            namespace_prefix=row["namespace_prefix"],
            source_url=row["source_url"],
            artifact_format=row["artifact_format"],
            upstream_version=row["upstream_version"],
            version_iri=row["version_iri"],
            artifact_size=row["artifact_size"],
            license_id=row["license_id"],
            license_url=row["license_url"],
            attribution=row["attribution"],
            redistribution_policy=row["redistribution_policy"],
            retrieved_at=_dt_from_str(row["retrieved_at"]),
            downloaded_at=_dt_from_str(row["retrieved_at"]),
            imported_at=_dt_from_str(row["imported_at"]),
            importer_name=row["importer_name"],
            importer_version=row["importer_version"],
            counts=_json_loads(row["counts_json"], {}),
            warnings=_json_loads(row["warnings_json"], []),
            manifest_fingerprint=row["manifest_fingerprint"],
        )

    def _row_to_entity(self, row: sqlite3.Row) -> Entity:
        return Entity(
            id=_parse_uuid(row["id"]),
            primary_curie=row["primary_curie"],
            entity_type=EntityType(row["entity_type"]),
            created_in_snapshot_id=_parse_uuid(row["created_in_snapshot_id"]),
        )

    def _revision_to_row(self, revision: EntityRevision) -> dict[str, Any]:
        return {
            "id": _uuid_str(revision.id),
            "entity_id": _uuid_str(revision.entity_id),
            "snapshot_id": _uuid_str(revision.snapshot_id),
            "label": revision.label,
            "definition": revision.definition,
            "synonyms_json": canonical_json(revision.synonyms),
            "alt_labels_json": canonical_json(revision.alt_labels),
            "obsolete": 1 if revision.obsolete else 0,
            "replaced_by": revision.replaced_by,
            "consider_json": canonical_json(revision.consider),
            "source_record_id": revision.source_record_id,
            "audit_json": canonical_json(revision.audit),
        }

    def _row_to_revision(self, row: sqlite3.Row) -> EntityRevision:
        return EntityRevision(
            id=_parse_uuid(row["id"]),
            entity_id=_parse_uuid(row["entity_id"]),
            snapshot_id=_parse_uuid(row["snapshot_id"]),
            label=row["label"],
            definition=row["definition"],
            synonyms=_json_loads(row["synonyms_json"], []),
            alt_labels=_json_loads(row["alt_labels_json"], []),
            obsolete=bool(row["obsolete"]),
            replaced_by=row["replaced_by"],
            consider=_json_loads(row["consider_json"], []),
            source_record_id=row["source_record_id"],
            audit=_json_loads(row["audit_json"], {}),
        )

    def _mapping_to_row(self, mapping: EntityMapping) -> dict[str, Any]:
        return {
            "id": _uuid_str(mapping.id),
            "subject_curie": mapping.subject_curie,
            "object_curie": mapping.object_curie,
            "relation": mapping.relation.value,
            "snapshot_id": _uuid_str(mapping.snapshot_id),
            "source_record_id": mapping.source_record_id,
            "notes": mapping.notes,
        }

    def _row_to_mapping(self, row: sqlite3.Row) -> EntityMapping:
        return EntityMapping(
            id=_parse_uuid(row["id"]),
            subject_curie=row["subject_curie"],
            object_curie=row["object_curie"],
            relation=MappingKind(row["relation"]),
            snapshot_id=_parse_uuid(row["snapshot_id"]),
            source_record_id=row["source_record_id"],
            notes=row["notes"],
        )

    def _claim_to_row(self, claim: Claim) -> dict[str, Any]:
        return {
            "id": _uuid_str(claim.id),
            "subject_curie": claim.subject_curie,
            "object_curie": claim.object_curie,
            "predicate": claim.predicate.value,
            "qualifiers_json": canonical_json(claim.qualifiers),
            "supersedes_claim_id": (
                _uuid_str(claim.supersedes_claim_id) if claim.supersedes_claim_id else None
            ),
            "subject_entity_id": (
                _uuid_str(claim.subject_entity_id) if claim.subject_entity_id else None
            ),
            "object_entity_id": _uuid_str(claim.object_entity_id)
            if claim.object_entity_id
            else None,
        }

    def _row_to_claim(self, row: sqlite3.Row) -> Claim:
        return Claim(
            id=_parse_uuid(row["id"]),
            subject_curie=row["subject_curie"],
            object_curie=row["object_curie"],
            predicate=Predicate(row["predicate"]),
            qualifiers=_json_loads(row["qualifiers_json"], {}),
            supersedes_claim_id=(
                _parse_uuid(row["supersedes_claim_id"]) if row["supersedes_claim_id"] else None
            ),
            subject_entity_id=(
                _parse_uuid(row["subject_entity_id"]) if row["subject_entity_id"] else None
            ),
            object_entity_id=(
                _parse_uuid(row["object_entity_id"]) if row["object_entity_id"] else None
            ),
        )

    def _evidence_to_row(self, evidence: ClaimEvidence) -> dict[str, Any]:
        payload = {
            "citation_ids": evidence.citation_ids,
            "source_url": evidence.source_url,
            "publication_date": evidence.publication_date,
            "evidence_type": evidence.evidence_type,
            "population": evidence.population,
            "sample_size": evidence.sample_size,
            "source_evidence_code": evidence.source_evidence_code,
            "strength_label": evidence.strength_label,
            "confidence": evidence.confidence,
            "rationale": evidence.rationale,
            "curator": evidence.curator,
            "extraction_method": evidence.extraction_method,
            "importer_version": evidence.importer_version,
            "extracted_at": _dt_to_str(evidence.extracted_at),
            "limitations": evidence.limitations,
            "audit": evidence.audit,
        }
        return {
            "id": _uuid_str(evidence.id),
            "claim_id": _uuid_str(evidence.claim_id),
            "snapshot_id": _uuid_str(evidence.snapshot_id),
            "direction": evidence.direction.value,
            "source_record_id": evidence.source_record_id,
            "evidence_json": canonical_json(payload),
        }

    def _row_to_evidence(self, row: sqlite3.Row) -> ClaimEvidence:
        payload = _json_loads(row["evidence_json"], {})
        return ClaimEvidence(
            id=_parse_uuid(row["id"]),
            claim_id=_parse_uuid(row["claim_id"]),
            snapshot_id=_parse_uuid(row["snapshot_id"]),
            direction=EvidenceDirection(row["direction"]),
            source_record_id=row["source_record_id"],
            citation_ids=payload.get("citation_ids", []),
            source_url=payload.get("source_url", ""),
            publication_date=payload.get("publication_date"),
            evidence_type=payload.get("evidence_type", ""),
            population=payload.get("population", ""),
            sample_size=payload.get("sample_size"),
            source_evidence_code=payload.get("source_evidence_code", ""),
            strength_label=payload.get("strength_label", ""),
            confidence=payload.get("confidence"),
            rationale=payload.get("rationale", ""),
            curator=payload.get("curator", ""),
            extraction_method=payload.get("extraction_method", ""),
            importer_version=payload.get("importer_version", ""),
            extracted_at=_dt_from_str(payload.get("extracted_at")),
            limitations=payload.get("limitations", []),
            audit=payload.get("audit", {}),
        )

    def _row_to_run(self, row: sqlite3.Row) -> ResearchRun:
        return ResearchRun(
            id=_parse_uuid(row["id"]),
            parent_run_id=_parse_uuid(row["parent_run_id"]) if row["parent_run_id"] else None,
            run_type=row["run_type"],
            status=RunStatus(row["status"]),
            fingerprint=row["fingerprint"],
            algorithm_id=row["algorithm_id"],
            algorithm_version=row["algorithm_version"],
            software_version=row["software_version"],
            parameters=_json_loads(row["parameters_json"], {}),
            snapshot_ids=[_parse_uuid(item) for item in _json_loads(row["snapshot_ids_json"], [])],
            claim_ids=[_parse_uuid(item) for item in _json_loads(row["claim_ids_json"], [])],
            input_query=row["input_query"],
            result=_json_loads(row["result_json"], None) if row["result_json"] else None,
            warnings=_json_loads(row["warnings_json"], []),
            started_at=_dt_from_str(row["started_at"]),
            finished_at=_dt_from_str(row["finished_at"]),
            created_at=_dt_from_str(row["created_at"]),
        )


# Re-export helpers used by tests and adapters.
__all__ = [
    "BiomedicalRepository",
    "ClaimView",
    "EntitySummary",
    "EntityView",
    "Page",
    "claim_evidence_uuid",
    "entity_revision_uuid",
    "mapping_uuid",
]
