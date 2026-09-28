"""Helpers for detecting whether the canonical biomedical SQLite store is initialized."""

from __future__ import annotations

import sqlite3
from typing import TYPE_CHECKING

from med_research.biomed.database import BiomedicalDatabase
from med_research.biomed.errors import BiomedicalStoreNotReadyError
from med_research.biomed.schema import SCHEMA_VERSION

if TYPE_CHECKING:
    from med_research.biomed.repository import BiomedicalRepository

BIOMED_STORE_INIT_HINT = (
    "Initialize the canonical biomedical store with "
    "`python -m med_research.cli biomed init` "
    "(optional: `--db $BIOMEDICAL_DB_PATH`), then import fixtures or run source sync."
)


def is_schema_initialized(database: BiomedicalDatabase) -> bool:
    """Return True when the database file exists and schema migration has been applied."""
    path = database.path
    if not path.is_file():
        return False
    try:
        with database.connect() as connection:
            version = connection.execute("PRAGMA user_version").fetchone()[0]
    except sqlite3.Error:
        return False
    return int(version) >= SCHEMA_VERSION


def repository_is_initialized(repository: BiomedicalRepository) -> bool:
    return is_schema_initialized(repository.database)


def require_schema_initialized(repository: BiomedicalRepository) -> None:
    if not repository_is_initialized(repository):
        raise BiomedicalStoreNotReadyError(BIOMED_STORE_INIT_HINT)
