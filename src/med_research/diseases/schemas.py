"""Pydantic models for knowledge graph entity validation."""

from __future__ import annotations

import json
from enum import Enum
from pathlib import Path
from typing import Any, TypedDict, TypeVar, cast

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from med_research.exceptions import MissingDataError, SchemaValidationError


class _LosslessModel(BaseModel):
    """Base model that keeps unknown keys on ``model_dump()``.

    Disease modules legitimately carry disease-specific fields (e.g.
    ``ibd_evidence``, ``ms_evidence``) that the shared schema does not
    enumerate. Preserving extra keys on round-trip means validation never
    silently drops curated data.
    """

    model_config = ConfigDict(extra="allow")


# ── TypedDict pilots (dict-based loaders; mirror Pydantic models below) ──


class GeneDict(TypedDict, total=False):
    """Dict shape for genes.json entries — mirrors :class:`Gene`."""

    id: str
    name: str
    chromosome: str
    function: str
    lupus_evidence: str
    odds_ratio: float | None
    references: list[str]
    category: str
    sle_evidence: str
    disease_evidence: str


class DrugDict(TypedDict, total=False):
    """Dict shape for drugs.json entries — mirrors :class:`Drug`."""

    id: str
    name: str
    type: str
    target: str
    mechanism: str
    approval: str
    route: str
    efficacy: str
    references: list[str]
    category: str
    disease_evidence: str
    adverse_effects: str


class GenesFileDict(TypedDict):
    genes: list[GeneDict]


class DrugsFileDict(TypedDict):
    drugs: list[DrugDict]


class PathwayDict(TypedDict, total=False):
    id: str
    name: str
    description: str
    key_components: list[str]
    therapeutic_targets: list[str]
    references: list[str]


class PathwaysFileDict(TypedDict):
    pathways: list[PathwayDict]


class RelationshipDict(TypedDict, total=False):
    source: str
    target: str
    type: str
    description: str


class RelationshipsFileDict(TypedDict):
    relationships: list[RelationshipDict]


class RelationshipType(str, Enum):
    TARGETS = "TARGETS"
    PARTICIPATES_IN = "PARTICIPATES_IN"
    MODULATES = "MODULATES"
    DRIVES = "DRIVES"
    ASSOCIATED_WITH = "ASSOCIATED_WITH"
    TREATS = "TREATS"


class Gene(_LosslessModel):
    id: str
    name: str
    chromosome: str
    function: str
    lupus_evidence: str = ""
    odds_ratio: float | None = None
    references: list[str] = Field(default_factory=list)
    category: str = ""
    sle_evidence: str = ""
    disease_evidence: str = ""


class GenesFile(BaseModel):
    genes: list[Gene]


class Drug(_LosslessModel):
    id: str
    name: str
    type: str
    target: str
    mechanism: str
    approval: str
    route: str
    efficacy: str
    references: list[str] = Field(default_factory=list)
    category: str = ""
    disease_evidence: str = ""
    adverse_effects: str = ""


class DrugsFile(BaseModel):
    drugs: list[Drug]


class Pathway(_LosslessModel):
    id: str
    name: str
    description: str
    key_components: list[str] = Field(default_factory=list)
    therapeutic_targets: list[str] = Field(default_factory=list)
    references: list[str] = Field(default_factory=list)


class PathwaysFile(BaseModel):
    pathways: list[Pathway]


class Relationship(_LosslessModel):
    source: str
    target: str
    type: RelationshipType
    description: str


class RelationshipsFile(BaseModel):
    relationships: list[Relationship]


class DiseaseProfile(_LosslessModel):
    id: str
    name: str
    description: str = ""
    prevalence: str = ""
    female_to_male_ratio: str = ""
    peak_onset: str = ""
    primary_tissue: str = ""
    hallmark_markers: list[str] = Field(default_factory=list)
    key_pathways: list[str] = Field(default_factory=list)
    kg_node_id: str = ""


class DrugAdverseProfile(_LosslessModel):
    """Per-drug adverse-event profile; fields vary by disease curation."""

    drug_id: str = ""


class AdverseEventsFile(_LosslessModel):
    """Disease-local adverse-event profile contract (``adverse_events.json``)."""

    schema_version: str = "1"
    disease_id: str
    source: str = ""
    profiles: list[DrugAdverseProfile] = Field(default_factory=list)


# ── Validated file loading ───────────────────────────────────────────────


KG_FILE_MODELS: dict[str, type[BaseModel]] = {
    "genes.json": GenesFile,
    "drugs.json": DrugsFile,
    "pathways.json": PathwaysFile,
    "relationships.json": RelationshipsFile,
    "profile.json": DiseaseProfile,
}

_ModelT = TypeVar("_ModelT", bound=BaseModel)


try:
    import orjson

    def _parse_json(raw: bytes | str) -> dict[str, Any]:
        if isinstance(raw, str):
            raw = raw.encode("utf-8")
        return cast(dict[str, Any], orjson.loads(raw))
except ImportError:

    def _parse_json(raw: bytes | str) -> dict[str, Any]:
        if isinstance(raw, bytes):
            raw = raw.decode("utf-8")
        return cast(dict[str, Any], json.loads(raw))


_VALIDATED_CACHE: dict[tuple[str, type], tuple[float, dict[str, Any]]] = {}


def invalidate_schemas_cache() -> None:
    _VALIDATED_CACHE.clear()


def load_validated_json(path: Path | str, model_class: type[_ModelT]) -> dict[str, Any]:
    """Load a JSON file and validate it against a Pydantic model.

    Returns the validated JSON payload as a plain dict so existing
    dict-based callers keep receiving the same shape they do today.
    Results are cached by (path, model_class, mtime) to eliminate redundant
    CPU-intensive Pydantic validations on unchanged files.

    Raises:
        MissingDataError: when the file does not exist.
        SchemaValidationError: when the file is not valid JSON or its
            content does not match the model schema.
    """
    path = Path(path)
    try:
        mtime = path.stat().st_mtime
    except FileNotFoundError as exc:
        error = MissingDataError(f"Data file not found: {path}")
        error.filename = str(path)
        raise error from exc

    cache_key = (str(path.resolve()), model_class)
    cached = _VALIDATED_CACHE.get(cache_key)
    if cached is not None and cached[0] == mtime:
        return cached[1]

    raw_bytes = path.read_bytes()
    try:
        parsed: dict[str, Any] = _parse_json(raw_bytes)
    except (json.JSONDecodeError, ValueError) as exc:
        raise SchemaValidationError(f"Invalid JSON in {path}: {exc}") from exc

    try:
        model_class.model_validate(parsed)
    except ValidationError as exc:
        raise SchemaValidationError(f"Schema validation failed for {path}: {exc}") from exc

    _VALIDATED_CACHE[cache_key] = (mtime, parsed)
    return parsed


def validate_and_load(path: Path | str, model_class: type[_ModelT]) -> dict[str, Any] | None:
    """Lenient variant of :func:`load_validated_json`.

    Returns the validated payload dict, or ``None`` when the file is
    missing or fails validation (legacy compatibility; new code should
    prefer the strict :func:`load_validated_json`).
    """
    try:
        return load_validated_json(path, model_class)
    except (MissingDataError, SchemaValidationError):
        return None
