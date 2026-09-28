"""FastAPI dependencies for the canonical biomedical store."""

from __future__ import annotations

from functools import lru_cache
from typing import Annotated

from fastapi import Depends

from med_research.biomed.repository import BiomedicalRepository
from med_research.web.config import BIOMEDICAL_DB_PATH


@lru_cache(maxsize=1)
def _default_repository() -> BiomedicalRepository:
    """Open the configured store path without auto-initializing schema.

    Operators run ``biomed init`` explicitly; read routes degrade to empty states
    until the store file and schema exist (see issue #65 / Phase 4 WS3).
    """
    return BiomedicalRepository(BIOMEDICAL_DB_PATH)


def get_biomedical_repository() -> BiomedicalRepository:
    return _default_repository()


def reset_biomedical_repository() -> None:
    _default_repository.cache_clear()


BiomedicalRepositoryDep = Annotated[BiomedicalRepository, Depends(get_biomedical_repository)]
