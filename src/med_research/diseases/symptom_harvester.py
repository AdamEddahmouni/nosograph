"""Harvest clinical symptoms from HPO / Open Targets disease phenotypes."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Optional

from med_research.diseases.bulk_store import OpenTargetsBulkStore, _hpo_label_map
from med_research.diseases.id_resolver import DiseaseIdResolver
from med_research.diseases.scaffold import _diseases_root, load_disease_registry, sanitize_id
from med_research.logging_config import get_logger

logger = get_logger(__name__)

SYMPTOMS_MAX = 15


def _read_config_symptoms(config_path: Path) -> list[str]:
    if not config_path.is_file():
        return []
    text = config_path.read_text(encoding="utf-8")
    match = re.search(r"SYMPTOMS\s*=\s*\[(.*?)\]", text, re.DOTALL)
    if not match:
        return []
    inner = match.group(1)
    return [m.strip().strip("'\"") for m in re.findall(r"['\"]([^'\"]+)['\"]", inner)]


def _write_config_symptoms(config_path: Path, symptoms: list[str]) -> None:
    text = config_path.read_text(encoding="utf-8")
    formatted = ",\n".join(f'    "{s}"' for s in symptoms)
    replacement = f"SYMPTOMS = [\n{formatted},\n]"
    new_text, n = re.subn(r"SYMPTOMS\s*=\s*\[[^\]]*\]", replacement, text, count=1, flags=re.DOTALL)
    if n == 0:
        logger.warning("Could not find SYMPTOMS block in %s", config_path)
        return
    new_text = re.sub(
        r"^[ \t]*#[^\n]*TODO: add the clinical symptoms[^\n]*\n(?=[ \t]*SYMPTOMS\s*=)",
        "",
        new_text,
        flags=re.MULTILINE,
    )
    config_path.write_text(new_text, encoding="utf-8")


def _hpo_symptoms_from_biomed(mondo_id: str, limit: int = SYMPTOMS_MAX) -> list[str]:
    try:
        from med_research.web.config import BIOMEDICAL_DB_PATH

        if not BIOMEDICAL_DB_PATH.exists():
            return []
        import sqlite3

        labels: list[str] = []
        with sqlite3.connect(BIOMEDICAL_DB_PATH) as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute(
                """
                SELECT object_curie
                FROM claims
                WHERE subject_curie = ?
                  AND predicate = 'HAS_PHENOTYPE'
                LIMIT ?
                """,
                (mondo_id, limit * 3),
            ).fetchall()
        hpo_labels = _hpo_label_map()
        for row in rows:
            hp_id = str(row["object_curie"]).replace(":", "_")
            label = hpo_labels.get(hp_id, hp_id)
            if label not in labels:
                labels.append(label)
        return labels[:limit]
    except Exception as exc:
        logger.debug("Biomed HPO symptom harvest skipped: %s", exc)
        return []


def harvest_symptoms_for_disease(
    disease_id: str,
    store: Optional[OpenTargetsBulkStore] = None,
    resolver: Optional[DiseaseIdResolver] = None,
    max_symptoms: int = SYMPTOMS_MAX,
    write: bool = False,
) -> dict:
    """Harvest symptoms for one disease module."""
    disease_id = sanitize_id(disease_id)
    root = _diseases_root() / disease_id
    config_path = root / "config.py"
    if not config_path.is_file():
        return {"disease_id": disease_id, "status": "no_config", "symptoms": []}

    existing = _read_config_symptoms(config_path)
    if existing:
        return {"disease_id": disease_id, "status": "already_populated", "symptoms": existing}

    store = store or OpenTargetsBulkStore()
    resolver = resolver or DiseaseIdResolver(bulk_store=store)
    entry = next(
        (e for e in load_disease_registry() if sanitize_id(e.get("id", "")) == disease_id),
        {"id": disease_id, "name": disease_id},
    )
    resolution = resolver.resolve_entry(entry)
    symptoms: list[str] = []

    if resolution.mondo_id:
        symptoms = _hpo_symptoms_from_biomed(resolution.mondo_id, max_symptoms)

    if not symptoms and resolution.efo_id and store.is_available():
        symptoms = store.get_phenotypes(resolution.efo_id, limit=max_symptoms)

    if write and symptoms:
        _write_config_symptoms(config_path, symptoms)

    return {
        "disease_id": disease_id,
        "status": "harvested" if symptoms else "no_symptoms",
        "efo_id": resolution.efo_id,
        "mondo_id": resolution.mondo_id,
        "symptoms": symptoms,
        "written": write and bool(symptoms),
    }


def harvest_all_symptoms(
    *,
    write: bool = False,
    limit: Optional[int] = None,
    disease_ids: Optional[list[str]] = None,
) -> dict:
    """Harvest symptoms for registry diseases (or a subset)."""
    store = OpenTargetsBulkStore()
    resolver = DiseaseIdResolver(bulk_store=store)
    entries = load_disease_registry()
    if disease_ids:
        wanted = {sanitize_id(d) for d in disease_ids}
        entries = [e for e in entries if sanitize_id(e.get("id", "")) in wanted]
    if limit:
        entries = entries[:limit]

    results = []
    for entry in entries:
        did = sanitize_id(entry.get("id", ""))
        results.append(harvest_symptoms_for_disease(did, store, resolver, write=write))

    populated = sum(1 for r in results if r["symptoms"])
    return {
        "total": len(results),
        "populated": populated,
        "results": results,
    }
