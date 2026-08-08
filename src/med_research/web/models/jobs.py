"""Pydantic models for generic Celery job submission."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator

from med_research.diseases.base import Disease

INT_JOB_OPTS = frozenset({
    "max_studies",
    "top_n",
    "max_articles",
    "max_trials",
    "top_k",
    "max_per_source",
    "max_per_query",
    "max_evidence",
})
BOOL_JOB_OPTS = frozenset({
    "no_cache",
    "untargeted_only",
    "use_vina",
    "no_shap",
    "targeted",
    "use_cache",
    "enable_llm",
})
FLOAT_JOB_OPTS = frozenset({"confidence"})
STR_JOB_OPTS = frozenset({
    "query",
    "gene_id",
    "drug_id",
    "model",
    "sources",
    "signature",
    "signature_source",
    "tissue",
    "operation",
})
KNOWN_JOB_OPTION_KEYS = INT_JOB_OPTS | BOOL_JOB_OPTS | FLOAT_JOB_OPTS | STR_JOB_OPTS


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

    # Boolean options
    no_cache: bool | None = None
    untargeted_only: bool | None = None
    use_vina: bool | None = None
    no_shap: bool | None = None
    targeted: bool | None = None
    use_cache: bool | None = None
    enable_llm: bool | None = None

    # Float options
    confidence: float | None = Field(default=None, ge=0.0, le=1.0)

    # String options
    query: str | None = None
    gene_id: str | None = None
    drug_id: str | None = None
    model: str | None = None
    sources: str | None = None
    signature: str | None = None
    signature_source: str | None = None
    tissue: str | None = None
    operation: str | None = None

    @field_validator("disease_id")
    @classmethod
    def validate_disease_id(cls, value: str) -> str:
        disease_id = value.strip().lower()
        if disease_id not in Disease.list_all():
            available = ", ".join(sorted(Disease.list_all()))
            raise ValueError(
                f"Unknown disease_id '{value}'. Available diseases: {available}"
            )
        return disease_id

    def to_task_opts(self) -> dict[str, Any]:
        """Return non-null job options for Celery task kwargs."""
        return {
            key: value
            for key, value in self.model_dump(exclude={"disease_id"}, exclude_none=True).items()
        }
