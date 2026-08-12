"""Pydantic models for generic Celery job submission."""

from __future__ import annotations

from datetime import date
from enum import Enum
from functools import lru_cache
from typing import Any, Literal, Optional, cast

from pydantic import BaseModel, ConfigDict, Field, create_model, field_validator

from med_research.diseases.base import Disease
from med_research.pipeline.registry import module_request_schema

INT_JOB_OPTS = frozenset(
    {
        "max_studies",
        "top_n",
        "max_articles",
        "max_trials",
        "top_k",
        "max_per_source",
        "max_per_query",
        "max_evidence",
        "expand_neighbors",
        "top_synergy",
    }
)
BOOL_JOB_OPTS = frozenset(
    {
        "no_cache",
        "untargeted_only",
        "use_vina",
        "no_shap",
        "targeted",
        "use_cache",
        "enable_llm",
        "export_html",
        "full",
        "parallel",
        "skip_ml",
        "resolve_snps",
        "extract_content",
        "cross_reference",
        "comparative",
        "save",
        "diff",
    }
)
FLOAT_JOB_OPTS = frozenset({"confidence"})
STR_JOB_OPTS = frozenset(
    {
        "query",
        "question",
        "gene_id",
        "drug_id",
        "model",
        "sources",
        "signature",
        "signature_source",
        "tissue",
        "operation",
        "candidate_type",
        "date_from",
        "date_to",
        "email",
        "queries",
    }
)
KNOWN_JOB_OPTION_KEYS = INT_JOB_OPTS | BOOL_JOB_OPTS | FLOAT_JOB_OPTS | STR_JOB_OPTS


class CatalogModuleJobRequest(BaseModel):
    """Base model used to generate per-module OpenAPI query contracts."""

    model_config = ConfigDict(extra="forbid")

    disease_id: str = "sle"

    @field_validator("disease_id")
    @classmethod
    def validate_disease_id(cls, value: str) -> str:
        disease_id = value.strip().lower()
        if disease_id not in Disease.list_all():
            available = ", ".join(sorted(Disease.list_all()))
            raise ValueError(f"Unknown disease_id '{value}'. Available diseases: {available}")
        return disease_id

    def to_task_opts(self) -> dict[str, Any]:
        """Return non-null generated request options for Celery."""
        return {
            key: value
            for key, value in self.model_dump(
                mode="json", exclude={"disease_id"}, exclude_none=True
            ).items()
        }


def _build_module_request_model(
    module_id: str,
    *,
    body: bool = False,
) -> type[CatalogModuleJobRequest]:
    """Build a Pydantic model from a registry request schema."""
    schema = module_request_schema(module_id)
    required = set(schema.get("required", [])) if body else set()
    fields: dict[str, tuple[Any, Any]] = {}
    for name, definition in schema["properties"].items():
        type_name = definition.get("type")
        if body and definition.get("body_type") == "array":
            item_schema = definition.get("items", {})
            item_enum = item_schema.get("enum")
            item_annotation: Any = Literal[tuple(item_enum)] if item_enum else str
            annotation: Any = list[item_annotation]
        elif body and definition.get("format") == "date":
            annotation = date
        elif type_name == "integer":
            annotation = int
        elif type_name == "number":
            annotation = float
        elif type_name == "boolean":
            annotation = bool
        else:
            annotation = str

        enum_values = definition.get("enum")
        if enum_values:
            if body:
                annotation = Literal[tuple(enum_values)]
            else:
                enum_type = Enum(  # type: ignore[misc]
                    f"{module_id}_{name}_Enum",
                    {str(value).upper(): value for value in enum_values},
                )
                annotation = enum_type

        if not body:
            field_default = None
        elif definition.get("body_type") == "array":
            field_default = definition.get("body_default", definition.get("default", None))
        else:
            field_default = definition.get("default", None)
        field_kwargs: dict[str, Any] = {
            "default": ... if name in required else field_default,
        }
        if "minimum" in definition:
            field_kwargs["ge"] = definition["minimum"]
        if "maximum" in definition:
            field_kwargs["le"] = definition["maximum"]
        if "minLength" in definition:
            field_kwargs["min_length"] = definition["minLength"]
        if "maxLength" in definition:
            field_kwargs["max_length"] = definition["maxLength"]
        if body and definition.get("body_type") == "array":
            field_kwargs["min_length"] = definition.get("minItems", 1)
        if "format" in definition:
            field_kwargs["json_schema_extra"] = {"format": definition["format"]}
        if "description" in definition:
            field_kwargs["description"] = definition["description"]
        if not body and "default" in definition:
            # Keep omitted query options as None at runtime while retaining
            # catalog defaults in generated OpenAPI schemas.
            field_kwargs["json_schema_extra"] = {
                **field_kwargs.get("json_schema_extra", {}),
                "default": definition["default"],
            }
        fields[name] = (
            annotation
            if body and (name in required or field_default is not None)
            else Optional[annotation],
            Field(**field_kwargs),
        )

    model_name = (
        f"{module_id.replace('_', ' ').title().replace(' ', '')}"
        f"{'Request' if body else 'JobRequest'}"
    )
    model = create_model(  # type: ignore[call-overload]
        model_name,
        __base__=CatalogModuleJobRequest,
        __module__=__name__,
        **fields,
    )
    return cast(type[CatalogModuleJobRequest], model)


@lru_cache(maxsize=None)
def module_job_request_model(module_id: str) -> type[CatalogModuleJobRequest]:
    """Create and cache the query model represented by a catalog schema."""
    return _build_module_request_model(module_id)


@lru_cache(maxsize=None)
def module_body_request_model(module_id: str) -> type[CatalogModuleJobRequest]:
    """Create and cache a JSON body model represented by a catalog schema."""
    return _build_module_request_model(module_id, body=True)


class GenericModuleJobRequest(BaseModel):
    """Validated query parameters for POST /api/jobs/{module_id}."""

    model_config = ConfigDict(extra="forbid")

    disease_id: str = "sle"

    # Integer options
    max_studies: int | None = Field(default=None, ge=1)
    top_n: int | None = Field(default=None, ge=1)
    max_articles: int | None = Field(default=None, ge=1)
    max_trials: int | None = Field(default=None, ge=1)
    top_k: int | None = Field(default=None, ge=1)
    max_per_source: int | None = Field(default=None, ge=1)
    max_per_query: int | None = Field(default=None, ge=1)
    max_evidence: int | None = Field(default=None, ge=1)
    expand_neighbors: int | None = Field(default=None, ge=0)
    top_synergy: int | None = Field(default=None, ge=1)

    # Boolean options
    no_cache: bool | None = None
    untargeted_only: bool | None = None
    use_vina: bool | None = None
    no_shap: bool | None = None
    targeted: bool | None = None
    use_cache: bool | None = None
    enable_llm: bool | None = None
    export_html: bool | None = None
    full: bool | None = None
    parallel: bool | None = None
    skip_ml: bool | None = None
    resolve_snps: bool | None = None
    extract_content: bool | None = None
    cross_reference: bool | None = None
    comparative: bool | None = None
    save: bool | None = None
    diff: bool | None = None

    # Float options
    confidence: float | None = Field(default=None, ge=0.0, le=1.0)

    # String options
    query: str | None = None
    question: str | None = None
    gene_id: str | None = None
    drug_id: str | None = None
    model: str | None = None
    sources: str | None = None
    signature: str | None = None
    signature_source: str | None = None
    tissue: str | None = None
    operation: str | None = None
    candidate_type: str | None = None
    date_from: str | None = None
    date_to: str | None = None
    email: str | None = None
    queries: str | None = None

    @field_validator("disease_id")
    @classmethod
    def validate_disease_id(cls, value: str) -> str:
        disease_id = value.strip().lower()
        if disease_id not in Disease.list_all():
            available = ", ".join(sorted(Disease.list_all()))
            raise ValueError(f"Unknown disease_id '{value}'. Available diseases: {available}")
        return disease_id

    def to_task_opts(self) -> dict[str, Any]:
        """Return non-null job options for Celery task kwargs."""
        return {
            key: value
            for key, value in self.model_dump(exclude={"disease_id"}, exclude_none=True).items()
        }

    def validate_for_module(self, module_id: str) -> None:
        """Reject options that are not part of the registered module contract."""
        allowed = set(module_request_schema(module_id)["properties"])
        supplied = set(self.to_task_opts())
        unsupported = sorted(supplied - allowed)
        if unsupported:
            names = ", ".join(unsupported)
            raise ValueError(f"Options not supported by module '{module_id}': {names}")


class RunAllJobRequest(BaseModel):
    """Validated query parameters for POST /api/jobs/run-all."""

    model_config = ConfigDict(extra="forbid")

    disease_id: str = "sle"
    full: bool = False
    parallel: bool = False
    skip_ml: bool = False
    export_html: bool = False
    no_cache: bool = False

    @field_validator("disease_id")
    @classmethod
    def validate_disease_id(cls, value: str) -> str:
        disease_id = value.strip().lower()
        if disease_id not in Disease.list_all():
            available = ", ".join(sorted(Disease.list_all()))
            raise ValueError(f"Unknown disease_id '{value}'. Available diseases: {available}")
        return disease_id

    def to_task_opts(self) -> dict[str, Any]:
        return self.model_dump(exclude={"disease_id"}, exclude_defaults=True)
