import hashlib
import json
import re
from typing import Any, Mapping
from uuid import UUID, uuid5

from med_research.biomed.models import EntityType, EvidenceDirection, MappingKind, Predicate

BIOMED_NAMESPACE = UUID("b38db2a8-67eb-5f5f-9f6d-742947426959")
_CURIE_PATTERN = re.compile(r"^[A-Za-z][A-Za-z0-9._-]*:[^\s:][^\s]*$")


def normalize_curie(value: str) -> str:
    """Normalize CURIE value (e.g. ' mondo:0007915 ' -> 'MONDO:0007915')."""
    normalized = value.strip()
    if not _CURIE_PATTERN.fullmatch(normalized):
        raise ValueError(f"Invalid CURIE: {value!r}")
    prefix, local = normalized.split(":", 1)
    return f"{prefix.upper()}:{local}"


def canonical_json(value: Any) -> str:
    """Produce deterministic canonical JSON string."""
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def fingerprint_json(value: Any) -> str:
    """Produce SHA256 hex digest of canonical JSON."""
    return hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()


def entity_uuid(entity_type: EntityType, curie: str) -> UUID:
    """Generate deterministic UUIDv5 for an entity based on type and normalized CURIE."""
    norm_curie = normalize_curie(curie)
    return uuid5(BIOMED_NAMESPACE, f"entity|{entity_type.value}|{norm_curie}")


def entity_revision_uuid(entity_id: UUID, snapshot_id: UUID) -> UUID:
    """Generate deterministic UUIDv5 for an entity revision."""
    return uuid5(BIOMED_NAMESPACE, f"entity_revision|{entity_id}|{snapshot_id}")


def mapping_uuid(
    subject_curie: str,
    object_curie: str,
    relation: MappingKind,
    snapshot_id: UUID,
) -> UUID:
    """Generate deterministic UUIDv5 for an entity mapping."""
    norm_sub = normalize_curie(subject_curie)
    norm_obj = normalize_curie(object_curie)
    return uuid5(BIOMED_NAMESPACE, f"mapping|{norm_sub}|{relation.value}|{norm_obj}|{snapshot_id}")


def claim_uuid(
    subject: str,
    predicate: Predicate,
    object_: str,
    qualifiers: Mapping[str, Any] | None = None,
) -> UUID:
    """Generate deterministic UUIDv5 for a claim based on subject, predicate, object, and qualifiers."""
    payload = {
        "subject": normalize_curie(subject),
        "predicate": predicate.value,
        "object": normalize_curie(object_),
        "qualifiers": dict(qualifiers) if qualifiers else {},
    }
    return uuid5(BIOMED_NAMESPACE, f"claim|{canonical_json(payload)}")


def claim_evidence_uuid(
    claim_id: UUID,
    snapshot_id: UUID,
    direction: EvidenceDirection,
    source_record_id: str,
) -> UUID:
    """Generate deterministic UUIDv5 for claim evidence."""
    return uuid5(BIOMED_NAMESPACE, f"claim_evidence|{claim_id}|{snapshot_id}|{direction.value}|{source_record_id}")


def snapshot_uuid(resource_name: str, version: str, checksum: str) -> UUID:
    """Generate deterministic UUIDv5 for a resource snapshot."""
    return uuid5(BIOMED_NAMESPACE, f"snapshot|{resource_name.strip().lower()}|{version.strip()}|{checksum.strip()}")


def research_run_fingerprint(create: Any) -> str:
    """Generate deterministic fingerprint hash for a research run specification (Model or dict)."""
    if isinstance(create, dict):
        name = create.get("name", "run")
        run_type = create.get("run_type", "research")
        algorithm_id = create.get("algorithm_id", "")
        algorithm_version = create.get("algorithm_version", "")
        software_version = create.get("software_version", "")
        parameters = create.get("parameters", {})
        snapshot_ids = create.get("snapshot_ids", [])
        claim_ids = create.get("claim_ids", [])
        input_query = create.get("input_query")
    else:
        name = getattr(create, "name", "run")
        run_type = getattr(create, "run_type", "research")
        algorithm_id = getattr(create, "algorithm_id", "")
        algorithm_version = getattr(create, "algorithm_version", "")
        software_version = getattr(create, "software_version", "")
        parameters = getattr(create, "parameters", {})
        snapshot_ids = getattr(create, "snapshot_ids", [])
        claim_ids = getattr(create, "claim_ids", [])
        input_query = getattr(create, "input_query", None)

    payload = {
        "name": name,
        "run_type": run_type,
        "algorithm_id": algorithm_id,
        "algorithm_version": algorithm_version,
        "software_version": software_version,
        "parameters": parameters,
        "snapshot_ids": [str(sid) for sid in sorted(snapshot_ids)],
        "claim_ids": [str(cid) for cid in sorted(claim_ids)],
        "input_query": input_query,
    }
    return fingerprint_json(payload)


def research_run_uuid(fingerprint: str) -> UUID:
    """Generate deterministic UUIDv5 for a research run from its fingerprint."""
    return uuid5(BIOMED_NAMESPACE, f"research_run|{fingerprint}")
