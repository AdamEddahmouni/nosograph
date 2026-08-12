"""HPO ontology import adapter."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from med_research.biomed.errors import BiomedicalValidationError
from med_research.biomed.identifiers import claim_uuid, entity_revision_uuid, entity_uuid
from med_research.biomed.imports.models import ImportBundle, ImportWarning
from med_research.biomed.models import (
    Claim,
    Entity,
    EntityRevision,
    EntityType,
    Predicate,
    ResourcePolicy,
)

_HP_ID = re.compile(r"HP_(\d+)$")


class HpoOntologyAdapter:
    resource_name = "hp"
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
        graphs = payload.get("graphs", [])
        if not graphs:
            raise BiomedicalValidationError("HPO artifact contains no graphs")
        graph = graphs[0]
        upstream_version = str(graph.get("meta", {}).get("version", ""))
        bundle = ImportBundle.from_artifact(
            policy=policy,
            artifact_path=path,
            upstream_version=upstream_version,
            artifact_format="json",
            namespace_prefix="HP",
            name="Human Phenotype Ontology",
        )
        return self._populate(bundle, graph, slim=slim)

    def _populate(
        self,
        bundle: ImportBundle,
        graph: dict[str, Any],
        *,
        slim: bool = False,
    ) -> ImportBundle:
        snapshot_id = bundle.snapshot.id
        entities: list[Entity] = []
        revisions: list[EntityRevision] = []
        claims: list[Claim] = []
        warnings: list[ImportWarning] = []

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
            entity = Entity(
                id=entity_uuid(EntityType.PHENOTYPE, curie),
                primary_curie=curie,
                entity_type=EntityType.PHENOTYPE,
                created_in_snapshot_id=snapshot_id,
            )
            entities.append(entity)
            meta = node.get("meta", {})
            revisions.append(
                EntityRevision(
                    id=entity_revision_uuid(entity.id, snapshot_id),
                    entity_id=entity.id,
                    snapshot_id=snapshot_id,
                    label=str(node.get("lbl", "")),
                    definition=_definition(meta),
                    synonyms=_synonyms(meta),
                    obsolete=str(node.get("lbl", "")).lower().startswith("obsolete"),
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

        return ImportBundle.build(
            bundle.snapshot,
            entities=entities,
            revisions=revisions,
            claims=claims,
            warnings=warnings,
        )


def _node_to_curie(node_id: str) -> str | None:
    match = _HP_ID.search(node_id)
    if match is None:
        return None
    return f"HP:{match.group(1)}"


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
