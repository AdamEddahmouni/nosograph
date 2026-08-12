"""Server-derived researcher identity for Evidence Workspace ownership."""

from __future__ import annotations

import re

from fastapi import HTTPException, Request

from med_research.web.services.auth import get_researcher_id as _get_authenticated_researcher_id

DEFAULT_RESEARCHER_ID = "anonymous"
# Retained only so old clients can receive a clear migration error and debug tests
# can use the explicitly documented compatibility path.
RESEARCHER_ID_HEADER = "X-Researcher-ID"
_MAX_RESEARCHER_ID_LENGTH = 64
_RESEARCHER_ID_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.:@+-]{0,63}$")


def validate_researcher_id(value: str) -> str:
    """Validate a principal after it has been resolved by the auth layer."""
    normalized = value.strip()
    if (
        not normalized
        or len(normalized) > _MAX_RESEARCHER_ID_LENGTH
        or not _RESEARCHER_ID_PATTERN.fullmatch(normalized)
    ):
        raise HTTPException(
            status_code=400,
            detail="Authenticated researcher principal must be 1-64 safe identifier characters",
        )
    return normalized


def get_researcher_id(request: Request) -> str:
    """Return the authenticated principal, never a client-controlled identity label."""
    return validate_researcher_id(_get_authenticated_researcher_id(request))
