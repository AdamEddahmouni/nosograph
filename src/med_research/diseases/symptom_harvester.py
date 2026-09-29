"""Harvest clinical symptoms from HPO / Open Targets disease phenotypes."""

from __future__ import annotations

import json
import re
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Optional

from med_research.diseases.bulk_store import OpenTargetsBulkStore, _hpo_label_map
from med_research.diseases.id_resolver import DiseaseIdResolver
from med_research.diseases.scaffold import _diseases_root, load_disease_registry, sanitize_id
from med_research.logging_config import get_logger

logger = get_logger(__name__)

SYMPTOMS_MAX = 15
HPOA_RELEASE = "2026-06-23"
HPO_LICENSE_URL = "https://human-phenotype-ontology.github.io/license.html"


def _read_config_symptoms(config_path: Path) -> list[str]:
    if not config_path.is_file():
        return []
    text = config_path.read_text(encoding="utf-8")
    match = re.search(r"SYMPTOMS\s*=\s*\[(.*?)\]", text, re.DOTALL)
    if not match:
        return []
    inner = match.group(1)
    return [m.strip().strip("'\"") for m in re.findall(r"['\"]([^'\"]+)['\"]", inner)]


def _write_config_symptoms(
    config_path: Path,
    symptoms: list[str],
    source_comments: list[str] | None = None,
) -> None:
    text = config_path.read_text(encoding="utf-8")
    text = re.sub(
        r"^[ \t]*#[^\n]*TODO: add the clinical symptoms[^\n]*\n(?=[ \t]*SYMPTOMS\s*=)",
        "",
        text,
        flags=re.MULTILINE,
    )
    formatted = ",\n".join(f'    "{s}"' for s in symptoms)
    comments = "\n".join(source_comments or [])
    prefix = f"{comments}\n" if comments else ""
    replacement = f"{prefix}SYMPTOMS = [\n{formatted},\n]"
    new_text, n = re.subn(r"SYMPTOMS\s*=\s*\[[^\]]*\]", replacement, text, count=1, flags=re.DOTALL)
    if n == 0:
        logger.warning("Could not find SYMPTOMS block in %s", config_path)
        return
    config_path.write_text(new_text, encoding="utf-8")


def _frequency_score(value: object) -> float | None:
    """Parse an HPOA frequency fraction, if present."""
    match = re.fullmatch(r"\s*(\d+)\s*/\s*(\d+)\s*", str(value or ""))
    if match is None or int(match.group(2)) == 0:
        return None
    denominator = int(match.group(2))
    if denominator == 0:
        return None
    return int(match.group(1)) / denominator


def _symptom_source_comments(symptom_source: str, mondo_id: str | None) -> list[str]:
    """Build the HPO attribution required for public symptom labels."""
    if symptom_source != "biomed_hpoa" or not mondo_id:
        return []
    mondo_curie = (
        "MONDO:" + mondo_id.removeprefix("MONDO_") if mondo_id.startswith("MONDO_") else mondo_id
    )
    return [
        f"# Source: HPOA (HPO release {HPOA_RELEASE}); disease annotation {mondo_curie}.",
        "# Phenotype labels are reproduced verbatim from positive HPO annotations.",
        "# Attribution: Human Phenotype Ontology Consortium.",
        "# Citation: Köhler S, et al. The Human Phenotype Ontology project. Nucleic Acids Res.",
        "# 2014;42(D1):D966-D974. doi:10.1093/nar/gkt1026.",
        f"# HPO license and use terms: {HPO_LICENSE_URL}",
    ]


def _hpo_symptoms_from_biomed(
    mondo_id: str, limit: int = SYMPTOMS_MAX, *, raise_on_error: bool = False
) -> list[str]:
    """Read labeled, positive phenotypes from the *active* HPOA snapshot only."""
    if limit <= 0:
        return []
    try:
        from med_research.web.config import BIOMEDICAL_DB_PATH

        if not BIOMEDICAL_DB_PATH.is_file():
            if raise_on_error:
                raise FileNotFoundError(BIOMEDICAL_DB_PATH)
            return []
        import sqlite3

        normalized_mondo_id = (
            "MONDO:" + mondo_id.removeprefix("MONDO_")
            if mondo_id.startswith("MONDO_")
            else mondo_id
        )
        database_uri = f"{BIOMEDICAL_DB_PATH.resolve().as_uri()}?mode=ro"
        with sqlite3.connect(database_uri, uri=True) as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute(
                """
                SELECT DISTINCT c.object_curie, c.qualifiers_json
                FROM claims c
                JOIN claim_evidence ce ON ce.claim_id = c.id
                JOIN active_snapshots active ON active.snapshot_id = ce.snapshot_id
                WHERE active.resource_name = 'hpoa'
                  AND c.subject_curie = ?
                  AND c.predicate = 'HAS_PHENOTYPE'
                  AND ce.direction = 'supporting'
                  AND NOT EXISTS (
                      SELECT 1 FROM claims newer WHERE newer.supersedes_claim_id = c.id
                  )
                """,
                (normalized_mondo_id,),
            ).fetchall()

        hpo_labels = _hpo_label_map()
        symptom_scores: dict[str, float | None] = {}
        for row in rows:
            try:
                qualifiers = json.loads(row["qualifiers_json"] or "{}")
            except (TypeError, json.JSONDecodeError):
                continue
            if qualifiers.get("negated"):
                continue

            hp_id = str(row["object_curie"]).replace(":", "_")
            label = hpo_labels.get(hp_id)
            if not label:
                continue
            normalized_label = label.casefold()
            if "inheritance" in normalized_label or "onset" in normalized_label:
                continue
            if normalized_label == "sporadic":
                continue

            score = _frequency_score(qualifiers.get("frequency"))
            if score == 0:
                continue
            current_score = symptom_scores.get(label)
            if label not in symptom_scores or (
                score is not None and (current_score is None or score > current_score)
            ):
                symptom_scores[label] = score

        return sorted(
            symptom_scores,
            key=lambda label: (
                symptom_scores[label] is None,
                -(symptom_scores[label] or 0),
                label.casefold(),
            ),
        )[:limit]
    except Exception as exc:
        if raise_on_error:
            raise
        logger.debug("Biomed HPO symptom harvest skipped: %s", exc)
        return []


def local_symptom_source_availability(
    store: OpenTargetsBulkStore | None = None,
    biomedical_db_path: Path | None = None,
) -> dict[str, bool]:
    """Report whether each local phenotype source can be queried."""
    import sqlite3

    if biomedical_db_path is None:
        from med_research.web.config import BIOMEDICAL_DB_PATH

        biomedical_db_path = BIOMEDICAL_DB_PATH

    biomed_hpoa = False
    try:
        if biomedical_db_path.is_file():
            database_uri = f"{biomedical_db_path.resolve().as_uri()}?mode=ro"
            with sqlite3.connect(database_uri, uri=True) as conn:
                tables = {
                    str(row[0])
                    for row in conn.execute(
                        "SELECT name FROM sqlite_master WHERE type = 'table'"
                    ).fetchall()
                }
                required_tables = {"active_snapshots", "claims", "claim_evidence"}
                if required_tables <= tables:
                    columns = {
                        str(row[1]) for row in conn.execute("PRAGMA table_info(active_snapshots)")
                    }
                    biomed_hpoa = {"resource_name", "snapshot_id"} <= columns and conn.execute(
                        "SELECT 1 FROM active_snapshots WHERE resource_name = 'hpoa' LIMIT 1"
                    ).fetchone() is not None
    except Exception:
        logger.debug("Local HPOA source availability check failed", exc_info=True)

    try:
        if store is None:
            store = OpenTargetsBulkStore()
        phenotype_glob = store._parquet_glob("disease_phenotype")
        ot_phenotype = bool(phenotype_glob and store._glob_column_names(phenotype_glob))
    except Exception:
        logger.debug("Local Open Targets phenotype availability check failed", exc_info=True)
        ot_phenotype = False

    return {"biomed_hpoa": biomed_hpoa, "ot_phenotype": ot_phenotype}


def _resolve_symptoms(
    resolution: object,
    store: OpenTargetsBulkStore,
    max_symptoms: int,
) -> tuple[list[str], str]:
    """Return (symptoms, symptom_source)."""
    mondo_id = getattr(resolution, "mondo_id", None)
    efo_id = getattr(resolution, "efo_id", None)

    if mondo_id:
        symptoms = _hpo_symptoms_from_biomed(mondo_id, max_symptoms)
        if symptoms:
            return symptoms, "biomed_hpoa"

    if efo_id and store.is_available():
        symptoms = store.get_phenotypes(efo_id, limit=max_symptoms)
        if symptoms:
            return symptoms, "ot_phenotype"

    return [], "none"


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
        return {
            "disease_id": disease_id,
            "status": "no_config",
            "symptoms": [],
            "symptom_source": "none",
        }

    existing = _read_config_symptoms(config_path)
    if existing:
        return {
            "disease_id": disease_id,
            "status": "already_populated",
            "symptoms": existing,
            "symptom_source": "config",
        }

    store = store or OpenTargetsBulkStore()
    resolver = resolver or DiseaseIdResolver(bulk_store=store)
    entry = next(
        (e for e in load_disease_registry() if sanitize_id(e.get("id", "")) == disease_id),
        {"id": disease_id, "name": disease_id},
    )
    resolution = resolver.resolve_entry(entry)
    symptoms, symptom_source = _resolve_symptoms(resolution, store, max_symptoms)

    if write and symptoms:
        _write_config_symptoms(
            config_path,
            symptoms,
            source_comments=_symptom_source_comments(symptom_source, resolution.mondo_id),
        )

    return {
        "disease_id": disease_id,
        "status": "harvested" if symptoms else "no_symptoms",
        "efo_id": resolution.efo_id,
        "mondo_id": resolution.mondo_id,
        "symptoms": symptoms,
        "symptom_source": symptom_source,
        "written": write and bool(symptoms),
    }


def harvest_all_symptoms(
    *,
    write: bool = False,
    limit: Optional[int] = None,
    disease_ids: Optional[list[str]] = None,
    workers: int = 1,
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

    ids = [sanitize_id(e.get("id", "")) for e in entries]

    def _one(did: str) -> dict:
        return harvest_symptoms_for_disease(did, store, resolver, write=write)

    results: list[dict] = []
    if workers > 1:
        with ThreadPoolExecutor(max_workers=workers) as pool:
            futures = {pool.submit(_one, did): did for did in ids}
            for future in as_completed(futures):
                results.append(future.result())
    else:
        results = [_one(did) for did in ids]

    populated = sum(1 for r in results if r["symptoms"])
    by_source: dict[str, int] = {}
    for row in results:
        source = row.get("symptom_source", "none")
        by_source[source] = by_source.get(source, 0) + 1

    return {
        "total": len(results),
        "populated": populated,
        "by_source": by_source,
        "results": results,
    }
