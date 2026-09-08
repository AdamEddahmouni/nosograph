"""SQLite connection and migration management for the biomedical store."""

from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator

from med_research.biomed.schema import SCHEMA_DDL, SCHEMA_VERSION


class BiomedicalDatabase:
    def __init__(self, path: Path, *, read_only: bool = False) -> None:
        self.path = Path(path)
        self.read_only = read_only

    def connect(self) -> sqlite3.Connection:
        if self.read_only:
            if not self.path.is_file():
                raise FileNotFoundError(self.path)
            connection = sqlite3.connect(
                f"file:{self.path.resolve()}?mode=ro",
                uri=True,
            )
        else:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            connection = sqlite3.connect(self.path)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        if not self.read_only:
            connection.execute("PRAGMA journal_mode = WAL")
        connection.execute("PRAGMA busy_timeout = 5000")
        return connection

    @contextmanager
    def transaction(self) -> Iterator[sqlite3.Connection]:
        with self.connect() as connection:
            try:
                yield connection
                connection.commit()
            except Exception:
                connection.rollback()
                raise

    def initialize(self) -> None:
        with self.transaction() as connection:
            current = connection.execute("PRAGMA user_version").fetchone()[0]
            if current >= SCHEMA_VERSION:
                return
            if current != 0:
                raise RuntimeError(f"Unsupported biomedical schema version: {current}")
            connection.executescript(SCHEMA_DDL)
            connection.execute(f"PRAGMA user_version = {SCHEMA_VERSION}")
