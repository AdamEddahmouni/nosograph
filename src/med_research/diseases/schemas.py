"""Pydantic models for knowledge graph entity validation."""

from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, Field


class RelationshipType(str, Enum):
    TARGETS = "TARGETS"
    PARTICIPATES_IN = "PARTICIPATES_IN"
    MODULATES = "MODULATES"
    DRIVES = "DRIVES"
    ASSOCIATED_WITH = "ASSOCIATED_WITH"
    TREATS = "TREATS"


class Gene(BaseModel):
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


class Drug(BaseModel):
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


class Pathway(BaseModel):
    id: str
    name: str
    description: str
    key_components: list[str] = Field(default_factory=list)
    therapeutic_targets: list[str] = Field(default_factory=list)
    references: list[str] = Field(default_factory=list)


class PathwaysFile(BaseModel):
    pathways: list[Pathway]


class Relationship(BaseModel):
    source: str
    target: str
    type: RelationshipType
    description: str


class RelationshipsFile(BaseModel):
    relationships: list[Relationship]


class DiseaseProfile(BaseModel):
    id: str
    name: str
    description: str
    prevalence: str = ""
    female_to_male_ratio: str = ""
    peak_onset: str = ""
    primary_tissue: str = ""
    hallmark_markers: list[str] = Field(default_factory=list)
    key_pathways: list[str] = Field(default_factory=list)
    kg_node_id: str = ""


def validate_and_load(path, model_class):
    """Load a JSON file and validate it against a Pydantic model.

    Returns the model instance on success, or a dict with an error key on failure.
    """
    import json

    from med_research.logging_config import get_logger

    logger = get_logger(__name__)

    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return model_class.model_validate(data)
    except FileNotFoundError:
        logger.warning("Data file not found: %s", path)
        return None
    except Exception as e:
        logger.warning("Validation failed for %s: %s", path, e)
        return None
