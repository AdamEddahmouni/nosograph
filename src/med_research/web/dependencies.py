"""Shared FastAPI dependencies — singleton-like access to heavy resources."""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any

from med_research.pipeline.knowledge_graph.config import load_drugs, load_genes, load_pathways


@lru_cache(maxsize=1)
def get_knowledge_graph():
    """Load the knowledge graph once and cache it in memory."""
    from med_research.pipeline.knowledge_graph.builder import build_graph

    return build_graph()


@lru_cache(maxsize=1)
def get_kg_genes() -> dict[str, Any]:
    """Load gene data indexed by gene ID."""
    data = load_genes()
    return {g["id"]: g for g in data["genes"]}


@lru_cache(maxsize=1)
def get_kg_drugs() -> dict[str, Any]:
    """Load drug data indexed by drug ID."""
    data = load_drugs()
    return {d["id"]: d for d in data["drugs"]}


@lru_cache(maxsize=1)
def get_kg_pathways() -> dict[str, Any]:
    """Load pathway data indexed by pathway ID."""
    data = load_pathways()
    return {p["id"]: p for p in data["pathways"]}


@lru_cache(maxsize=1)
def get_candidates() -> list[dict[str, Any]]:
    """Load repurposing candidates."""
    from med_research.web.config import DR_DATA_DIR

    data = json.loads((DR_DATA_DIR / "candidates.json").read_text(encoding="utf-8"))
    return data["repurposing_candidates"]


def load_json(path: Path) -> dict[str, Any]:
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
