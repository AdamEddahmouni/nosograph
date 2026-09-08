"""FastAPI dependencies for the canonical biomedical store."""

from __future__ import annotations

from functools import lru_cache
from typing import Annotated

from fastapi import Depends

from med_research.biomed.repository import BiomedicalRepository
from med_research.web.config import BIOMEDICAL_DB_PATH, parse_demo_snapshot_path
from med_research.web.demo_mode import is_demo_mode


@lru_cache(maxsize=1)
def _default_repository() -> BiomedicalRepository:
    demo = is_demo_mode()
    database_path = parse_demo_snapshot_path() if demo else BIOMEDICAL_DB_PATH
    repository = BiomedicalRepository(database_path, read_only=demo)
    if not demo:
        repository.initialize()
    return repository


def get_biomedical_repository() -> BiomedicalRepository:
    return _default_repository()


def reset_biomedical_repository() -> None:
    _default_repository.cache_clear()


BiomedicalRepositoryDep = Annotated[BiomedicalRepository, Depends(get_biomedical_repository)]
