"""Mondo disease ontology import adapter."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from med_research.biomed.errors import BiomedicalValidationError
from med_research.biomed.identifiers import (
    claim_uuid,
    entity_revision_uuid,
    entity_uuid,
    mapping_uuid,
    normalize_curie,
)
from med_research.biomed.imports.models import ImportBundle, ImportWarning
from med_research.biomed.models import (
    Claim,
    Entity,
    EntityMapping,
    EntityRevision,
    EntityType,
    MappingKind,
    Predicate,
    ResourcePolicy,
)

_OBO_ID = re.compile(r"MONDO_(\d+)$")
_XREF = re.compile(r"^[A-Za-z][A-Za-z0-9._-]*:[^\s:][^\s]*$")

_MAPPING_KINDS: dict[str, MappingKind] = {
    "exactmatch": MappingKind.EXACT,
    "exact": MappingKind.EXACT,
    "closematch": MappingKind.CLOSE,
    "close": MappingKind.CLOSE,
    "broadmatch": MappingKind.BROAD,
    "broad": MappingKind.BROAD,
    "narrowmatch": MappingKind.NARROW,
    "narrow": MappingKind.NARROW,
}

# Cross-refs needed for disease pipeline ID resolution and HPOA joins.
_PIPELINE_XREF_PREFIXES = (
    "EFO:",
    "EFO_",
    "OMIM:",
    "DOID:",
    "ICD10:",
    "ORPHANET:",
    "NCIT:",
    "UMLS:",
)


class MondoAdapter:
    resource_name = "mondo"
    supported_formats = ("json",)

    def parse(
        self,
        path: Path,
        policy: ResourcePolicy,
        *,
        slim: bool = False,
        **kwargs: object,
    ) -> ImportBundle:
        from med_research.biomed.imports.json_io import load_json

        payload = load_json(path)
        upstream_version = str(payload.get("meta", {}).get("version", ""))
        bundle = ImportBundle.from_artifact(
            policy=policy,
            artifact_path=path,
            upstream_version=upstream_version,
            artifact_format="json",
            namespace_prefix="MONDO",
            name="Mondo Disease Ontology",
        )
        return self._populate(bundle, payload, slim=slim)

    def _populate(
        self,
        bundle: ImportBundle,
        payload: dict[str, Any],
        *,
        slim: bool = False,
    ) -> ImportBundle:
        graphs = payload.get("graphs", [])
        if not graphs:
            raise BiomedicalValidationError("Mondo artifact contains no graphs")
        graph = graphs[0]
        snapshot_id = bundle.snapshot.id

        entities: list[Entity] = []
        revisions: list[EntityRevision] = []
        mappings: list[EntityMapping] = []
        claims: list[Claim] = []
        warnings: list[ImportWarning] = []

        node_by_id: dict[str, dict[str, Any]] = {}
        for node in graph.get("nodes", []):
            node_id = str(node.get("id", ""))
            curie = _node_to_curie(node_id)
            if curie is None:
                warnings.append(
                    ImportWarning(
                        code="skipped_node",
                        message=f"Could not resolve CURIE for node {node_id}",
                        source_record_id=node_id,
                    )
                )
                continue
            node_by_id[node_id] = node
            entity = Entity(
                id=entity_uuid(EntityType.CONDITION, curie),
                primary_curie=curie,
                entity_type=EntityType.CONDITION,
                created_in_snapshot_id=snapshot_id,
            )
            entities.append(entity)
            meta = node.get("meta", {})
            obsolete = _is_obsolete(node)
            replaced_by = _replaced_by(meta) if obsolete else None
            consider = _consider_terms(meta) if obsolete else []
            synonyms = _synonyms(meta)
            revisions.append(
                EntityRevision(
                    id=entity_revision_uuid(entity.id, snapshot_id),
                    entity_id=entity.id,
                    snapshot_id=snapshot_id,
                    label=str(node.get("lbl", "")),
                    definition=_definition(meta),
                    synonyms=synonyms,
                    obsolete=obsolete,
                    replaced_by=replaced_by,
                    consider=consider,
                    source_record_id=node_id,
                )
            )
            for xref in _node_xrefs(meta):
                if slim and not _is_pipeline_xref(xref):
                    continue
                relation = _xref_relation(xref)
                mappings.append(
                    EntityMapping(
                        id=mapping_uuid(curie, xref, relation, snapshot_id),
                        subject_curie=curie,
                        object_curie=xref,
                        relation=relation,
                        snapshot_id=snapshot_id,
                        source_record_id=node_id,
                    )
                )

        if not slim:
            for edge in graph.get("edges", []):
                sub_curie = _node_to_curie(str(edge.get("sub", "")))
                obj_curie = _node_to_curie(str(edge.get("obj", "")))
                if sub_curie is None or obj_curie is None:
                    continue
                if str(edge.get("pred", "")).lower() in {"is_a", "subclassof"}:
                    claims.append(
                        Claim(
                            id=claim_uuid(sub_curie, Predicate.IS_A, obj_curie, {}),
                            subject_curie=sub_curie,
                            object_curie=obj_curie,
                            predicate=Predicate.IS_A,
                        )
                    )

        graph_meta = graph.get("meta", {})
        for xref_entry in graph_meta.get("xrefs", []):
            subject_curie = _node_to_curie(str(xref_entry.get("subject", "")))
            object_curie = str(xref_entry.get("object", ""))
            predicate = str(xref_entry.get("predicate", ""))
            if subject_curie is None or not _XREF.fullmatch(object_curie):
                continue
            relation = _mapping_kind_from_predicate(predicate)
            mappings.append(
                EntityMapping(
                    id=mapping_uuid(subject_curie, object_curie, relation, snapshot_id),
                    subject_curie=subject_curie,
                    object_curie=normalize_curie(object_curie),
                    relation=relation,
                    snapshot_id=snapshot_id,
                    source_record_id=f"{subject_curie}|{object_curie}",
                )
            )

        return ImportBundle.build(
            bundle.snapshot,
            entities=entities,
            revisions=revisions,
            mappings=_dedupe_mappings(mappings),
            claims=claims,
            warnings=warnings,
        )


def _node_to_curie(node_id: str) -> str | None:
    match = _OBO_ID.search(node_id)
    if match is None:
        return None
    return f"MONDO:{match.group(1)}"


def _definition(meta: dict[str, Any]) -> str:
    definition = meta.get("definition")
    if isinstance(definition, dict):
        return str(definition.get("val", ""))
    return str(definition or "")


def _synonyms(meta: dict[str, Any]) -> list[str]:
    values: list[str] = []
    for item in meta.get("synonyms", []):
        if isinstance(item, dict) and item.get("val"):
            values.append(str(item["val"]))
    return values


def _node_xrefs(meta: dict[str, Any]) -> list[str]:
    values: list[str] = []
    for item in meta.get("xrefs", []):
        if isinstance(item, dict) and item.get("val"):
            candidate = str(item["val"])
            if _XREF.fullmatch(candidate):
                values.append(normalize_curie(candidate))
    for item in meta.get("basicPropertyValues", []):
        if not isinstance(item, dict):
            continue
        candidate = str(item.get("val", ""))
        if _XREF.fullmatch(candidate):
            values.append(normalize_curie(candidate))
    return list(dict.fromkeys(values))


def _is_obsolete(node: dict[str, Any]) -> bool:
    label = str(node.get("lbl", "")).lower()
    return label.startswith("obsolete")


def _replaced_by(meta: dict[str, Any]) -> str | None:
    for item in meta.get("basicPropertyValues", []):
        if not isinstance(item, dict):
            continue
        predicate = str(item.get("pred", ""))
        if predicate.endswith("termReplacedBy"):
            return normalize_curie(str(item.get("val", "")))
    for item in meta.get("basicPropertyValues", []):
        if not isinstance(item, dict):
            continue
        predicate = str(item.get("pred", ""))
        if predicate.endswith("consider"):
            return normalize_curie(str(item.get("val", "")))
    return None


def _consider_terms(meta: dict[str, Any]) -> list[str]:
    values: list[str] = []
    for item in meta.get("basicPropertyValues", []):
        if not isinstance(item, dict):
            continue
        predicate = str(item.get("pred", ""))
        if predicate.endswith("consider"):
            values.append(normalize_curie(str(item.get("val", ""))))
    return values


def _mapping_kind_from_predicate(predicate: str) -> MappingKind:
    normalized = predicate.split(":")[-1].lower()
    return _MAPPING_KINDS.get(normalized, MappingKind.CLOSE)


def _is_pipeline_xref(xref: str) -> bool:
    upper = xref.upper()
    return any(upper.startswith(prefix) for prefix in _PIPELINE_XREF_PREFIXES)


def _xref_relation(xref: str) -> MappingKind:
    upper = xref.upper()
    if upper.startswith("EFO:") or upper.startswith("EFO_"):
        return MappingKind.EXACT
    if upper.startswith("OMIM:"):
        return MappingKind.EXACT
    if xref == "DOID:9074":
        return MappingKind.CLOSE
    return MappingKind.CLOSE


def _dedupe_mappings(mappings: list[EntityMapping]) -> list[EntityMapping]:
    seen: set[str] = set()
    unique: list[EntityMapping] = []
    for mapping in mappings:
        key = f"{mapping.subject_curie}|{mapping.object_curie}|{mapping.relation.value}"
        if key in seen:
            continue
        seen.add(key)
        unique.append(mapping)
    return unique
