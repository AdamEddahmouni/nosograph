"""Fast JSON loading for large ontology artifacts."""

from __future__ import annotations

from pathlib import Path
from typing import Any


def load_json(path: Path) -> Any:
    """Load JSON from disk, preferring orjson when installed."""
    data = path.read_bytes()
    try:
        import orjson

        return orjson.loads(data)
    except ImportError:
        import json

        return json.loads(data.decode("utf-8"))
