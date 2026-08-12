"""FastAPI dependencies for the canonical biomedical store."""

from __future__ import annotations

from functools import lru_cache
from typing import Annotated

from fastapi import Depends

from med_research.biomed.repository import BiomedicalRepository
from med_research.web.config import BIOMEDICAL_DB_PATH


@lru_cache(maxsize=1)
def _default_repository() -> BiomedicalRepository:
    repository = BiomedicalRepository(BIOMEDICAL_DB_PATH)
    repository.initialize()
    return repository


def get_biomedical_repository() -> BiomedicalRepository:
    return _default_repository()


def reset_biomedical_repository() -> None:
    _default_repository.cache_clear()


BiomedicalRepositoryDep = Annotated[BiomedicalRepository, Depends(get_biomedical_repository)]
