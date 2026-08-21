"""FastAPI disease parameter helpers — no implicit SLE defaults."""

from __future__ import annotations

from typing import Annotated

from fastapi import HTTPException, Query

from med_research.diseases.identifiers import (
    default_disease_for_selection,
    resolve_disease_identifier,
)

RequiredDiseaseId = Annotated[
    str,
    Query(..., description="Disease ID (required; slug, alias, MONDO, or EFO)"),
]


def resolve_query_disease(disease: RequiredDiseaseId) -> str:
    """Resolve and validate a required disease query parameter."""
    try:
        return resolve_disease_identifier(disease)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


def resolve_optional_query_disease(
    disease: str | None = Query(
        None,
        description="Disease ID; when omitted the first CI-validated module is used",
    ),
    disease_id: str | None = Query(
        None,
        description="Alias for disease (legacy parameter name)",
    ),
) -> str:
    """Resolve an optional disease param using generic selection when absent."""
    raw = disease if disease not in (None, "") else disease_id
    if raw is None or not str(raw).strip():
        return default_disease_for_selection()
    try:
        return resolve_disease_identifier(raw)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
