"""SQLite schema definition for the biomedical canonical store."""

SCHEMA_VERSION = 1

SCHEMA_DDL = """
CREATE TABLE IF NOT EXISTS resource_snapshots (
    id TEXT PRIMARY KEY,
    resource_name TEXT NOT NULL,
    version TEXT NOT NULL,
    checksum TEXT NOT NULL,
    name TEXT NOT NULL DEFAULT '',
    namespace_prefix TEXT NOT NULL DEFAULT '',
    source_url TEXT NOT NULL DEFAULT '',
    artifact_format TEXT NOT NULL DEFAULT '',
    upstream_version TEXT NOT NULL DEFAULT '',
    version_iri TEXT,
    artifact_size INTEGER NOT NULL DEFAULT 0,
    license_id TEXT NOT NULL DEFAULT '',
    license_url TEXT NOT NULL DEFAULT '',
    attribution TEXT NOT NULL DEFAULT '',
    redistribution_policy TEXT NOT NULL DEFAULT 'redistributable',
    retrieved_at TEXT,
    imported_at TEXT,
    importer_name TEXT NOT NULL DEFAULT '',
    importer_version TEXT NOT NULL DEFAULT '',
    counts_json TEXT NOT NULL DEFAULT '{}',
    warnings_json TEXT NOT NULL DEFAULT '[]',
    manifest_fingerprint TEXT NOT NULL DEFAULT '',
    UNIQUE (resource_name, version, checksum)
);

CREATE TABLE IF NOT EXISTS active_snapshots (
    resource_name TEXT PRIMARY KEY,
    snapshot_id TEXT NOT NULL,
    FOREIGN KEY (snapshot_id) REFERENCES resource_snapshots (id)
);

CREATE TABLE IF NOT EXISTS entities (
    id TEXT PRIMARY KEY,
    primary_curie TEXT NOT NULL UNIQUE,
    entity_type TEXT NOT NULL,
    created_in_snapshot_id TEXT NOT NULL,
    FOREIGN KEY (created_in_snapshot_id) REFERENCES resource_snapshots (id)
);

CREATE TABLE IF NOT EXISTS entity_revisions (
    id TEXT PRIMARY KEY,
    entity_id TEXT NOT NULL,
    snapshot_id TEXT NOT NULL,
    label TEXT NOT NULL DEFAULT '',
    definition TEXT NOT NULL DEFAULT '',
    synonyms_json TEXT NOT NULL DEFAULT '[]',
    alt_labels_json TEXT NOT NULL DEFAULT '[]',
    obsolete INTEGER NOT NULL DEFAULT 0 CHECK (obsolete IN (0, 1)),
    replaced_by TEXT,
    consider_json TEXT NOT NULL DEFAULT '[]',
    source_record_id TEXT NOT NULL DEFAULT '',
    audit_json TEXT NOT NULL DEFAULT '{}',
    UNIQUE (entity_id, snapshot_id),
    FOREIGN KEY (entity_id) REFERENCES entities (id),
    FOREIGN KEY (snapshot_id) REFERENCES resource_snapshots (id)
);

CREATE TABLE IF NOT EXISTS entity_names (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    entity_id TEXT NOT NULL,
    snapshot_id TEXT NOT NULL,
    name TEXT NOT NULL,
    name_normalized TEXT NOT NULL,
    FOREIGN KEY (entity_id) REFERENCES entities (id),
    FOREIGN KEY (snapshot_id) REFERENCES resource_snapshots (id)
);

CREATE TABLE IF NOT EXISTS entity_mappings (
    id TEXT PRIMARY KEY,
    subject_curie TEXT NOT NULL,
    object_curie TEXT NOT NULL,
    relation TEXT NOT NULL CHECK (relation IN ('exact', 'close', 'broad', 'narrow')),
    snapshot_id TEXT NOT NULL,
    source_record_id TEXT NOT NULL DEFAULT '',
    notes TEXT NOT NULL DEFAULT '',
    FOREIGN KEY (snapshot_id) REFERENCES resource_snapshots (id)
);

CREATE TABLE IF NOT EXISTS claims (
    id TEXT PRIMARY KEY,
    subject_curie TEXT NOT NULL,
    object_curie TEXT NOT NULL,
    predicate TEXT NOT NULL,
    qualifiers_json TEXT NOT NULL DEFAULT '{}',
    supersedes_claim_id TEXT,
    subject_entity_id TEXT,
    object_entity_id TEXT,
    FOREIGN KEY (supersedes_claim_id) REFERENCES claims (id),
    FOREIGN KEY (subject_entity_id) REFERENCES entities (id),
    FOREIGN KEY (object_entity_id) REFERENCES entities (id)
);

CREATE TABLE IF NOT EXISTS claim_evidence (
    id TEXT PRIMARY KEY,
    claim_id TEXT NOT NULL,
    snapshot_id TEXT NOT NULL,
    direction TEXT NOT NULL CHECK (direction IN ('supporting', 'contradictory')),
    source_record_id TEXT NOT NULL,
    evidence_json TEXT NOT NULL DEFAULT '{}',
    UNIQUE (claim_id, snapshot_id, direction, source_record_id),
    FOREIGN KEY (claim_id) REFERENCES claims (id),
    FOREIGN KEY (snapshot_id) REFERENCES resource_snapshots (id)
);

CREATE TABLE IF NOT EXISTS research_runs (
    id TEXT PRIMARY KEY,
    parent_run_id TEXT,
    run_type TEXT NOT NULL,
    status TEXT NOT NULL,
    fingerprint TEXT NOT NULL UNIQUE,
    algorithm_id TEXT NOT NULL,
    algorithm_version TEXT NOT NULL,
    software_version TEXT NOT NULL,
    parameters_json TEXT NOT NULL DEFAULT '{}',
    snapshot_ids_json TEXT NOT NULL DEFAULT '[]',
    claim_ids_json TEXT NOT NULL DEFAULT '[]',
    input_query TEXT NOT NULL DEFAULT '',
    result_json TEXT,
    warnings_json TEXT NOT NULL DEFAULT '[]',
    started_at TEXT,
    finished_at TEXT,
    created_at TEXT NOT NULL,
    FOREIGN KEY (parent_run_id) REFERENCES research_runs (id)
);

CREATE TABLE IF NOT EXISTS research_run_snapshots (
    run_id TEXT NOT NULL,
    snapshot_id TEXT NOT NULL,
    PRIMARY KEY (run_id, snapshot_id),
    FOREIGN KEY (run_id) REFERENCES research_runs (id),
    FOREIGN KEY (snapshot_id) REFERENCES resource_snapshots (id)
);

CREATE INDEX IF NOT EXISTS idx_entity_names_normalized
    ON entity_names (name_normalized);

CREATE INDEX IF NOT EXISTS idx_entity_revisions_entity
    ON entity_revisions (entity_id);

CREATE INDEX IF NOT EXISTS idx_entity_mappings_object
    ON entity_mappings (object_curie, relation);

CREATE INDEX IF NOT EXISTS idx_claims_subject_predicate
    ON claims (subject_curie, predicate);

CREATE INDEX IF NOT EXISTS idx_claims_object_predicate
    ON claims (object_curie, predicate);

CREATE INDEX IF NOT EXISTS idx_claim_evidence_direction
    ON claim_evidence (claim_id, direction);
"""
