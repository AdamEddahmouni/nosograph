"""Shared FastAPI dependencies — singleton-like access to heavy resources."""

import json
from functools import lru_cache
from pathlib import Path

from web_api.config import KG_DATA_DIR


@lru_cache(maxsize=1)
def get_knowledge_graph():
    """Load the knowledge graph once and cache it in memory."""
    from knowledge_graph.build_graph import build_graph

    return build_graph()


@lru_cache(maxsize=1)
def get_kg_genes() -> dict:
    """Load gene data indexed by gene ID."""
    data = json.loads((KG_DATA_DIR / "genes.json").read_text(encoding="utf-8"))
    return {g["id"]: g for g in data["genes"]}


@lru_cache(maxsize=1)
def get_kg_drugs() -> dict:
    """Load drug data indexed by drug ID."""
    data = json.loads((KG_DATA_DIR / "drugs.json").read_text(encoding="utf-8"))
    return {d["id"]: d for d in data["drugs"]}


@lru_cache(maxsize=1)
def get_kg_pathways() -> dict:
    """Load pathway data indexed by pathway ID."""
    data = json.loads((KG_DATA_DIR / "pathways.json").read_text(encoding="utf-8"))
    return {p["id"]: p for p in data["pathways"]}


@lru_cache(maxsize=1)
def get_candidates() -> list:
    """Load repurposing candidates."""
    from web_api.config import DR_DATA_DIR

    data = json.loads((DR_DATA_DIR / "candidates.json").read_text(encoding="utf-8"))
    return data["repurposing_candidates"]


def load_json(path: Path) -> dict:
    """Safely load a JSON file. Returns empty dict on failure."""
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


def safe_serialize(obj):
    """Convert numpy types to native Python for JSON serialization.

    Used by both REST response handlers and WebSocket streaming code.
    """
    if obj is None:
        return None
    if isinstance(obj, dict):
        return {k: safe_serialize(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [safe_serialize(v) for v in obj]
    try:
        import numpy as np
        if isinstance(obj, (np.floating, np.integer)):
            return obj.item()
        if isinstance(obj, np.ndarray):
            return obj.tolist()
        if isinstance(obj, np.bool_):
            return bool(obj)
    except ImportError:
        pass
    return obj
