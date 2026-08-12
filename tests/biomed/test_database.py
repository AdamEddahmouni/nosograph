from pathlib import Path

from med_research.biomed.database import BiomedicalDatabase


def test_initialize_is_idempotent_and_enables_foreign_keys(tmp_path: Path) -> None:
    db = BiomedicalDatabase(tmp_path / "biomedical.sqlite3")
    db.initialize()
    db.initialize()
    with db.connect() as connection:
        assert connection.execute("PRAGMA user_version").fetchone()[0] == 1
        assert connection.execute("PRAGMA foreign_keys").fetchone()[0] == 1
        names = {
            row[0]
            for row in connection.execute("SELECT name FROM sqlite_master WHERE type='table'")
        }
    assert {"resource_snapshots", "entities", "claims", "claim_evidence", "research_runs"} <= names
