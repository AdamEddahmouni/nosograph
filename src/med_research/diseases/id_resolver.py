"""EFO / MONDO disease identifier resolution cascade."""

from __future__ import annotations

import json
import unicodedata
from dataclasses import dataclass, field
from difflib import SequenceMatcher
from functools import lru_cache
from pathlib import Path
from typing import Any, Optional

from med_research.diseases.bulk_store import (
    OpenTargetsBulkStore,
    efo_from_disease_row,
    is_efo_id,
    is_ot_disease_id,
    mondo_curie_to_ot_id,
    normalize_disease_id,
    normalize_efo,
)
from med_research.diseases.scaffold import _diseases_root, load_disease_registry, sanitize_id
from med_research.logging_config import get_logger

logger = get_logger(__name__)

CONFIDENCE_THRESHOLD = 0.85
FUZZY_THRESHOLD = 0.80
MONDO_NAME_FUZZY_THRESHOLD = 0.92


@dataclass
class ResolutionResult:
    """Outcome of resolving one registry or filesystem disease entry."""

    disease_id: str
    name: str
    efo_id: Optional[str] = None
    mondo_id: Optional[str] = None
    resolution_confidence: float = 0.0
    resolution_source: str = "unresolved"
    needs_review: bool = True
    category: str = ""
    notes: list[str] = field(default_factory=list)

    def to_registry_patch(self) -> dict:
        patch: dict[str, Any] = {}
        if self.efo_id:
            patch["efo_id"] = self.efo_id
        if self.mondo_id:
            patch["mondo_id"] = self.mondo_id
        if self.resolution_confidence:
            patch["resolution_confidence"] = round(self.resolution_confidence, 3)
        if self.resolution_source:
            patch["resolution_source"] = self.resolution_source
        return patch


def _fuzzy_score(a: str, b: str, min_score: float = 0.0) -> float:
    matcher = SequenceMatcher(None, a.lower(), b.lower())
    if matcher.quick_ratio() < min_score:
        return 0.0
    return matcher.ratio()


@lru_cache(maxsize=None)
def _normalize_name(value: str) -> str:
    text = unicodedata.normalize("NFKD", value.strip().lower())
    return "".join(ch for ch in text if not unicodedata.combining(ch))


def _load_mondo_efo_xrefs(
    biomed_db: Optional[Path] = None,
) -> tuple[dict[str, str], dict[str, str], dict[str, str]]:
    """Load EFO<->MONDO xref maps (exact plus close fallback)."""
    try:
        from med_research.biomed.repository import BiomedicalRepository
        from med_research.web.config import BIOMEDICAL_DB_PATH

        path = biomed_db or BIOMEDICAL_DB_PATH
        if not path.exists():
            return {}, {}, {}
        repo = BiomedicalRepository(path)
        repo.initialize()
        snapshot = repo.get_active_snapshot("mondo")
        if snapshot is None:
            return {}, {}, {}
        efo_to_mondo: dict[str, str] = {}
        mondo_to_efo_exact: dict[str, str] = {}
        mondo_to_efo_close: dict[str, str] = {}
        with repo.database.connect() as conn:
            for relation in ("exact", "close"):
                rows = conn.execute(
                    """
                    SELECT subject_curie, object_curie FROM entity_mappings
                    WHERE snapshot_id = ? AND relation = ?
                      AND (object_curie LIKE 'EFO_%' OR object_curie LIKE 'EFO:%')
                    """,
                    (str(snapshot.id), relation),
                ).fetchall()
                for row in rows:
                    mondo = row["subject_curie"]
                    efo = normalize_efo(row["object_curie"].replace("EFO:", ""))
                    if not mondo.startswith("MONDO:") or not efo:
                        continue
                    efo_to_mondo.setdefault(efo, mondo)
                    if relation == "exact":
                        mondo_to_efo_exact.setdefault(mondo, efo)
                    else:
                        mondo_to_efo_close.setdefault(mondo, efo)
        return efo_to_mondo, mondo_to_efo_exact, mondo_to_efo_close
    except Exception as exc:
        logger.debug("MONDO xref load skipped: %s", exc)
        return {}, {}, {}


def _load_mondo_labels(biomed_db: Optional[Path] = None) -> list[tuple[str, str]]:
    """Return (primary_curie, label) pairs from the active MONDO snapshot."""
    try:
        from med_research.biomed.repository import BiomedicalRepository
        from med_research.web.config import BIOMEDICAL_DB_PATH

        path = biomed_db or BIOMEDICAL_DB_PATH
        if not path.exists():
            return []
        repo = BiomedicalRepository(path)
        repo.initialize()
        snapshot = repo.get_active_snapshot("mondo")
        if snapshot is None:
            return []
        with repo.database.connect() as conn:
            rows = conn.execute(
                """
                SELECT e.primary_curie, er.label
                FROM entities e
                JOIN entity_revisions er ON er.entity_id = e.id AND er.snapshot_id = ?
                WHERE er.label IS NOT NULL
                """,
                (str(snapshot.id),),
            ).fetchall()
        return [
            (row["primary_curie"], row["label"])
            for row in rows
            if row["primary_curie"] and row["label"]
        ]
    except Exception:
        return []


def _lookup_mondo_by_name(
    name: str,
    labels: list[tuple[str, str]],
) -> tuple[Optional[str], float, str]:
    """Resolve a disease name to MONDO via exact then fuzzy label match."""
    if not name or not labels:
        return None, 0.0, "none"
    needle = _normalize_name(name)
    for curie, label in labels:
        if _normalize_name(label) == needle:
            return curie, 1.0, "exact"
    best_score = 0.0
    best_curie: Optional[str] = None
    best_label = name
    for curie, label in labels:
        score = _fuzzy_score(needle, _normalize_name(label), MONDO_NAME_FUZZY_THRESHOLD)
        if score > best_score:
            best_score = score
            best_curie = curie
            best_label = label
    if best_curie and best_score >= MONDO_NAME_FUZZY_THRESHOLD:
        return best_curie, round(best_score, 3), f"fuzzy:{best_label}"
    return None, 0.0, "none"


class DiseaseIdResolver:
    """Resolve disease identifiers via registry → MONDO xref → OT parquet → fuzzy."""

    def __init__(
        self,
        bulk_store: Optional[OpenTargetsBulkStore] = None,
        biomed_db: Optional[Path] = None,
    ) -> None:
        self.bulk_store = bulk_store or OpenTargetsBulkStore()
        self.biomed_db = biomed_db
        self._efo_to_mondo, self._mondo_to_efo_exact, self._mondo_to_efo_close = (
            _load_mondo_efo_xrefs(biomed_db)
        )
        self._mondo_labels = _load_mondo_labels(biomed_db)

    def _efo_for_mondo(self, mondo_id: str) -> tuple[Optional[str], str]:
        if mondo_id in self._mondo_to_efo_exact:
            return self._mondo_to_efo_exact[mondo_id], "exact"
        if mondo_id in self._mondo_to_efo_close:
            return self._mondo_to_efo_close[mondo_id], "close"
        return None, "none"

    def _mondo_to_efo_map(self) -> dict[str, str]:
        merged = dict(self._mondo_to_efo_close)
        merged.update(self._mondo_to_efo_exact)
        return merged

    def _resolve_via_ot(
        self,
        result: ResolutionResult,
        name: str,
        *,
        allow_fuzzy: bool = True,
    ) -> bool:
        if not self.bulk_store.is_available():
            return False

        mondo_to_efo = self._mondo_to_efo_map()
        resolved = self.bulk_store.resolve_disease(name, mondo_to_efo=mondo_to_efo)
        if resolved and is_ot_disease_id(resolved.efo_id):
            result.efo_id = normalize_disease_id(resolved.efo_id)
            result.resolution_confidence = 0.95
            result.resolution_source = "ot_disease_exact"
            result.needs_review = False
            if result.mondo_id is None:
                result.mondo_id = self._efo_to_mondo.get(result.efo_id)
            return True

        if not allow_fuzzy:
            return False

        best_score = 0.0
        best_efo: Optional[str] = None
        best_name = name
        for row in self.bulk_store._read_table("disease"):
            row_name = (row.get("name") or "").strip()
            score = _fuzzy_score(name, row_name, FUZZY_THRESHOLD)
            if score > best_score:
                candidate = efo_from_disease_row(row, mondo_to_efo)
                if candidate and is_efo_id(candidate):
                    best_score = score
                    best_efo = normalize_efo(candidate)
                    best_name = row_name
        if best_efo and best_score >= FUZZY_THRESHOLD:
            result.efo_id = normalize_disease_id(best_efo)
            result.resolution_confidence = round(best_score, 3)
            result.resolution_source = "ot_disease_fuzzy"
            result.needs_review = best_score < CONFIDENCE_THRESHOLD
            result.notes.append(f"Fuzzy matched to '{best_name}' (score={best_score:.2f})")
            if result.mondo_id is None:
                result.mondo_id = self._efo_to_mondo.get(best_efo)
            return True
        return False

    def _resolve_via_ot_api(self, result: ResolutionResult, name: str) -> bool:
        from med_research.diseases.scaffold import search_efo_id

        efo = search_efo_id(name)
        if not efo:
            return False
        normalized = normalize_disease_id(efo)
        if not is_ot_disease_id(normalized):
            return False
        result.efo_id = normalized
        result.resolution_confidence = 0.9
        result.resolution_source = "ot_api_search"
        result.needs_review = False
        if result.mondo_id is None:
            result.mondo_id = self._efo_to_mondo.get(result.efo_id)
        return True

    def resolve_entry(self, entry: dict) -> ResolutionResult:
        disease_id = sanitize_id(entry.get("id", ""))
        name = (entry.get("name") or disease_id).strip()
        category = entry.get("category") or ""
        result = ResolutionResult(disease_id=disease_id, name=name, category=category)

        existing_efo = entry.get("efo_id") or ""
        if existing_efo and is_ot_disease_id(existing_efo):
            result.efo_id = normalize_disease_id(existing_efo)
            result.resolution_confidence = 1.0
            result.resolution_source = "registry_efo"
            result.needs_review = False
            result.mondo_id = entry.get("mondo_id") or self._efo_to_mondo.get(result.efo_id)
            return result

        mondo_id = entry.get("mondo_id")
        mondo_confidence = 1.0 if mondo_id else 0.0
        if not mondo_id:
            mondo_id, mondo_confidence, mondo_match = _lookup_mondo_by_name(
                name, self._mondo_labels
            )
            if mondo_match.startswith("fuzzy:"):
                result.notes.append(f"MONDO fuzzy matched to '{mondo_match[6:]}'")

        authoritative_mondo = bool(mondo_id and mondo_confidence >= MONDO_NAME_FUZZY_THRESHOLD)

        if mondo_id:
            result.mondo_id = mondo_id
            efo_from_mondo, xref_kind = self._efo_for_mondo(mondo_id)
            if efo_from_mondo:
                result.efo_id = efo_from_mondo
                result.resolution_confidence = 0.98 if xref_kind == "exact" else 0.88
                result.resolution_source = f"mondo_xref_{xref_kind}"
                result.needs_review = xref_kind != "exact"
                return result

        if self._resolve_via_ot(result, name, allow_fuzzy=not authoritative_mondo):
            return result

        if self._resolve_via_ot_api(result, name):
            return result

        if authoritative_mondo and result.mondo_id:
            ot_id = mondo_curie_to_ot_id(result.mondo_id)
            if ot_id:
                result.efo_id = ot_id
                result.resolution_confidence = mondo_confidence
                result.resolution_source = (
                    "mondo_ot_id" if mondo_confidence >= 1.0 else "mondo_ot_id_fuzzy"
                )
                result.needs_review = mondo_confidence < 1.0
                return result

        result.resolution_source = "failed"
        result.needs_review = True
        result.notes.append("No disease identifier match found")
        return result

    def resolve_registry(
        self,
        registry_path: Optional[Path] = None,
        include_orphans: bool = True,
    ) -> list[ResolutionResult]:
        entries = load_disease_registry(registry_path)
        seen = {sanitize_id(e.get("id", "")) for e in entries}
        results = [self.resolve_entry(e) for e in entries]

        if include_orphans:
            root = _diseases_root()
            for child in sorted(root.iterdir()):
                if not child.is_dir() or child.name.startswith("_"):
                    continue
                did = sanitize_id(child.name)
                if did in seen or not (child / "data" / "profile.json").exists():
                    continue
                try:
                    profile = json.loads(
                        (child / "data" / "profile.json").read_text(encoding="utf-8")
                    )
                    name = profile.get("name") or did
                except (json.JSONDecodeError, OSError):
                    name = did
                results.append(self.resolve_entry({"id": did, "name": name, "category": "orphan"}))
        return results

    def build_report(self, results: list[ResolutionResult]) -> dict:
        resolved = [r for r in results if r.efo_id and not r.needs_review]
        ambiguous = [r for r in results if r.efo_id and r.needs_review]
        failed = [r for r in results if not r.efo_id]
        return {
            "total": len(results),
            "resolved": len(resolved),
            "ambiguous": len(ambiguous),
            "failed": len(failed),
            "resolution_rate": round(
                len([r for r in results if r.efo_id]) / max(len(results), 1), 3
            ),
            "entries": [
                {
                    "disease_id": r.disease_id,
                    "name": r.name,
                    "efo_id": r.efo_id,
                    "mondo_id": r.mondo_id,
                    "confidence": r.resolution_confidence,
                    "source": r.resolution_source,
                    "needs_review": r.needs_review,
                    "notes": r.notes,
                }
                for r in results
            ],
        }

    def apply_to_registry(
        self,
        results: list[ResolutionResult],
        registry_path: Optional[Path] = None,
        min_confidence: float = CONFIDENCE_THRESHOLD,
    ) -> int:
        path = registry_path or (_diseases_root() / "disease_registry.json")
        data = json.loads(path.read_text(encoding="utf-8"))
        by_id = {sanitize_id(e.get("id", "")): e for e in data.get("diseases", [])}
        updated = 0
        for result in results:
            patchable = result.efo_id and result.resolution_confidence >= min_confidence
            if not patchable:
                continue
            entry = by_id.get(result.disease_id)
            if entry is None:
                continue
            patch = result.to_registry_patch()
            for key, value in patch.items():
                if entry.get(key) != value:
                    entry[key] = value
                    updated += 1
        path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        return updated
