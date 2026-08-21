"""Local Open Targets bulk-data layer — DuckDB queries over parquet subsets.

Replaces per-disease GraphQL calls with fast local reads from downloaded
Open Targets Platform parquet tables (disease, associations, known drugs,
disease phenotypes).
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path
from typing import Any, Optional

from med_research.logging_config import get_logger

logger = get_logger(__name__)


def _duckdb_parquet_sql(glob: str, sql: str, **extra: str) -> str:
    """Format DuckDB SQL; parquet globs come from bulk store layout, not user input."""
    return sql.format(glob=glob, **extra)  # nosec B608


DEFAULT_VERSION = "25.03"
MANIFEST_NAME = "manifest.json"


@dataclass(frozen=True)
class ResolvedDisease:
    """A disease resolved to an Open Targets EFO identifier."""

    efo_id: str
    name: str
    description: str = ""
    synonyms: list[str] = field(default_factory=list)


def repo_root() -> Path:
    return Path(__file__).resolve().parents[3]


def default_bulk_root() -> Path:
    return repo_root() / "data" / "bulk" / "opentargets"


def manifest_path(bulk_root: Optional[Path] = None) -> Path:
    root = bulk_root or default_bulk_root()
    return root.parent / MANIFEST_NAME


class OpenTargetsBulkStore:
    """Query Open Targets parquet subsets via DuckDB without loading full tables."""

    def __init__(self, bulk_root: Optional[Path] = None, version: Optional[str] = None) -> None:
        self.bulk_root = bulk_root or default_bulk_root()
        self._manifest = self._load_manifest()
        self.version = version or self._manifest.get("version", DEFAULT_VERSION)
        self._data_dir = self.bulk_root / self.version
        self._conn: Any = None
        self._glob_cache: dict[str, Optional[str]] = {}
        self._cols_cache: dict[str, set[str]] = {}
        self._table_cache: dict[str, list[dict]] = {}

    def _load_manifest(self) -> dict:
        path = manifest_path(self.bulk_root)
        if not path.is_file():
            return {}
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            logger.warning("Could not read bulk manifest at %s", path)
            return {}

    def is_available(self) -> bool:
        """True when manifest + required parquet tables exist."""
        if not self._manifest.get("version"):
            return False
        required = ("disease", "association_overall_direct", "known_drug")
        return all(self._parquet_glob(table) for table in required)

    def _parquet_glob(self, table: str) -> Optional[str]:
        if table in self._glob_cache:
            return self._glob_cache[table]
        table_dir = self._data_dir / table
        if table_dir.is_dir():
            files = list(table_dir.glob("*.parquet"))
            if files:
                glob = str(table_dir / "*.parquet").replace("\\", "/")
                self._glob_cache[table] = glob
                return glob
        single = self._data_dir / f"{table}.parquet"
        if single.is_file():
            glob = str(single).replace("\\", "/")
            self._glob_cache[table] = glob
            return glob
        self._glob_cache[table] = None
        return None

    def _connect(self) -> Any:
        if self._conn is not None:
            return self._conn
        import duckdb

        self._conn = duckdb.connect()
        return self._conn

    def close(self) -> None:
        if self._conn is not None:
            self._conn.close()
            self._conn = None

    def _query(self, sql: str, params: list[Any] = None) -> list[dict]:
        if params is None:
            params = []
        try:
            conn = self._connect()
            result = conn.execute(sql, params)
            cols = [d[0] for d in result.description]
            return [dict(zip(cols, row, strict=False)) for row in result.fetchall()]
        except Exception as exc:
            logger.warning("Bulk store query failed: %s", exc)
            return []

    def _read_table(self, table: str, where: str = "", params: list[Any] = None) -> list[dict]:
        if params is None:
            params = []
        glob = self._parquet_glob(table)
        if not glob:
            return []
        if not where:
            cached = self._table_cache.get(table)
            if cached is not None:
                return cached
            rows = self._query(_duckdb_parquet_sql(glob, "SELECT * FROM read_parquet('{glob}')"))
            self._table_cache[table] = rows
            return rows
        sql = _duckdb_parquet_sql(glob, "SELECT * FROM read_parquet('{glob}')")
        if where:
            sql += f" WHERE {where}"
        return self._query(sql, params)

    def get_disease_info(self, disease_id: str) -> dict:
        """Return {name, synonyms, description} for an Open Targets disease id."""
        normalized = normalize_disease_id(disease_id)
        rows = self._read_table("disease", "id = ?", [normalized])
        if not rows and normalized.startswith("MONDO_"):
            mondo_curie = ot_id_to_mondo_curie(normalized)
            rows = [
                row
                for row in self._read_table("disease")
                if ot_id_to_mondo_curie(str(row.get("id") or "")) == mondo_curie
            ]
        if not rows:
            return {}
        row = rows[0]
        synonyms_raw = row.get("synonyms") or ""
        synonyms: list[str] = []
        if isinstance(synonyms_raw, str) and synonyms_raw.strip():
            try:
                parsed = json.loads(synonyms_raw)
                if isinstance(parsed, list):
                    synonyms = [s for s in parsed if isinstance(s, str)]
            except json.JSONDecodeError:
                synonyms = [synonyms_raw]
        elif isinstance(synonyms_raw, list):
            synonyms = [s for s in synonyms_raw if isinstance(s, str)]
        description = row.get("description") or ""
        if isinstance(description, dict):
            description = description.get("value", "")
        return {
            "name": row.get("name") or "",
            "synonyms": synonyms[:10],
            "description": description,
        }

    def resolve_disease(
        self,
        name: str,
        efo_id: Optional[str] = None,
        mondo_to_efo: Optional[dict[str, str]] = None,
    ) -> Optional[ResolvedDisease]:
        """Resolve a disease name or EFO id to a ResolvedDisease."""
        if efo_id:
            normalized = normalize_disease_id(efo_id)
            if is_ot_disease_id(normalized):
                info = self.get_disease_info(normalized)
                return ResolvedDisease(
                    efo_id=normalized,
                    name=info.get("name") or name,
                    description=info.get("description", ""),
                    synonyms=info.get("synonyms", []),
                )
        if not name:
            return None
        needle = name.strip().lower()
        rows = self._read_table("disease")
        for row in rows:
            row_name = (row.get("name") or "").strip().lower()
            if row_name == needle:
                resolved = _resolved_from_row(row, name, mondo_to_efo)
                if resolved:
                    return resolved
            synonyms_raw = row.get("synonyms") or ""
            syns: list[str] = []
            if isinstance(synonyms_raw, str):
                try:
                    syns = json.loads(synonyms_raw)
                except json.JSONDecodeError:
                    syns = [synonyms_raw]
            elif isinstance(synonyms_raw, dict):
                for key in (
                    "hasExactSynonym",
                    "hasRelatedSynonym",
                    "hasNarrowSynonym",
                    "hasBroadSynonym",
                ):
                    for item in synonyms_raw.get(key) or []:
                        if isinstance(item, str):
                            syns.append(item)
            elif isinstance(synonyms_raw, list):
                syns = synonyms_raw
            for syn in syns:
                if isinstance(syn, str) and syn.strip().lower() == needle:
                    resolved = _resolved_from_row(row, name, mondo_to_efo)
                    if resolved:
                        return resolved
        # Substring fallback for partial matches
        for row in rows:
            row_name = (row.get("name") or "").strip().lower()
            if needle in row_name or row_name in needle:
                resolved = _resolved_from_row(row, name, mondo_to_efo)
                if resolved:
                    return resolved
        return None

    def _glob_column_names(self, glob: Optional[str]) -> set[str]:
        if not glob:
            return set()
        if glob in self._cols_cache:
            return self._cols_cache[glob]
        rows = self._query(
            _duckdb_parquet_sql(glob, "DESCRIBE SELECT * FROM read_parquet('{glob}') LIMIT 1")
        )
        cols = {str(row.get("column_name", "")) for row in rows}
        self._cols_cache[glob] = cols
        return cols

    def _disease_row_by_id(self, disease_id: str) -> dict[str, Any]:
        normalized = normalize_disease_id(disease_id)
        rows = self._read_table("disease", "id = ?", [normalized])
        if rows:
            return rows[0]
        if normalized.startswith("MONDO_"):
            mondo_curie = ot_id_to_mondo_curie(normalized)
            for row in self._read_table("disease"):
                if ot_id_to_mondo_curie(str(row.get("id") or "")) == mondo_curie:
                    return row
        return {}

    def _association_disease_ids(self, disease_id: str) -> list[str]:
        """Return disease ids to query in association tables, with ancestor fallback."""
        normalized = normalize_disease_id(disease_id)
        if not normalized:
            return []
        candidates = [normalized]
        row = self._disease_row_by_id(normalized)
        for anc in row.get("ancestors") or []:
            anc_id = str(anc)
            if anc_id and anc_id not in candidates:
                candidates.append(anc_id)
        return candidates

    def get_targets(self, disease_id: str, limit: int = 60) -> list[dict]:
        """Return disease-associated targets as {symbol, name, score}."""
        assoc_glob = self._parquet_glob("association_overall_direct")
        if not assoc_glob:
            return []
        assoc_cols = self._glob_column_names(assoc_glob)
        target_glob = self._parquet_glob("target")
        legacy = "approvedSymbol" in assoc_cols

        for candidate_id in self._association_disease_ids(disease_id):
            if legacy:
                sql = _duckdb_parquet_sql(
                    assoc_glob,
                    "SELECT diseaseId, score, approvedSymbol, approvedName, biotype "
                    "FROM read_parquet('{glob}') WHERE diseaseId = ? ORDER BY score DESC LIMIT ?",
                )
                rows = self._query(sql, [candidate_id, limit * 2])
            elif target_glob:
                sql = _duckdb_parquet_sql(
                    assoc_glob,
                    "SELECT a.score, t.approvedSymbol, t.approvedName, t.biotype "
                    "FROM read_parquet('{glob}') a "
                    "LEFT JOIN read_parquet('{target_glob}') t ON a.targetId = t.id "
                    "WHERE a.diseaseId = ? ORDER BY a.score DESC LIMIT ?",
                    target_glob=target_glob,
                )
                rows = self._query(sql, [candidate_id, limit * 2])
            else:
                sql = _duckdb_parquet_sql(
                    assoc_glob,
                    "SELECT score, targetId AS approvedSymbol, targetId AS approvedName, '' AS biotype "
                    "FROM read_parquet('{glob}') WHERE diseaseId = ? ORDER BY score DESC LIMIT ?",
                )
                rows = self._query(sql, [candidate_id, limit * 2])

            targets: list[dict] = []
            for row in rows:
                symbol = row.get("approvedSymbol") or ""
                if not symbol:
                    continue
                biotype = row.get("biotype") or ""
                if biotype and biotype != "protein_coding":
                    continue
                targets.append(
                    {
                        "symbol": symbol,
                        "name": row.get("approvedName") or symbol,
                        "score": row.get("score"),
                    }
                )
            if targets:
                return targets[:limit]
        return self._targets_from_biomed(disease_id, limit)

    def _targets_from_biomed(self, disease_id: str, limit: int) -> list[dict]:
        """Fallback gene associations from ClinVar/biomed claims when OT bulk is empty."""
        import os

        if os.environ.get("BIOMED_LEGACY_PROJECTION") != "1":
            return []
        try:
            from med_research.biomed.models import Predicate
            from med_research.biomed.repository import BiomedicalRepository
            from med_research.web.config import BIOMEDICAL_DB_PATH

            if not BIOMEDICAL_DB_PATH.exists():
                return []
            mondo_curie = None
            normalized = normalize_disease_id(disease_id)
            if normalized.startswith("MONDO_"):
                mondo_curie = ot_id_to_mondo_curie(normalized)
            if not mondo_curie:
                return []

            repo = BiomedicalRepository(BIOMEDICAL_DB_PATH)
            repo.initialize()
            claims = repo.list_claims(mondo_curie, predicate=Predicate.ASSOCIATED_WITH_GENE)
            targets: list[dict] = []
            for claim in claims[:limit]:
                gene_curie = (
                    claim.object_curie
                    if claim.subject_curie == mondo_curie
                    else claim.subject_curie
                )
                symbol = gene_curie.split(":")[-1] if ":" in gene_curie else gene_curie
                targets.append(
                    {"symbol": symbol, "name": symbol, "score": None, "source": "biomed"}
                )
            return targets
        except Exception as exc:
            logger.debug("Biomed target fallback skipped: %s", exc)
            return []

    def get_drugs(self, disease_id: str, limit: int = 60) -> list[dict]:
        """Return known drugs as scaffold-compatible dicts."""
        glob = self._parquet_glob("known_drug")
        if not glob:
            return []
        for candidate_id in self._association_disease_ids(disease_id):
            sql = _duckdb_parquet_sql(
                glob,
                "SELECT * FROM read_parquet('{glob}') WHERE diseaseId = ? LIMIT ?",
            )
            rows = self._query(sql, [candidate_id, limit * 2])
            drugs: list[dict] = []
            for row in rows:
                drug_id = row.get("drugId") or row.get("id") or ""
                if not drug_id:
                    continue
                target = row.get("targetSymbol") or row.get("approvedSymbol") or ""
                targets = [target] if target else []
                drugs.append(
                    {
                        "id": drug_id,
                        "name": row.get("drugName")
                        or row.get("prefName")
                        or row.get("label")
                        or drug_id,
                        "type": row.get("drugType") or "",
                        "phase": row.get("phase") or row.get("maximumClinicalTrialPhase"),
                        "status": row.get("status") or "",
                        "targets": targets,
                        "mechanism": row.get("mechanism") or row.get("mechanismOfAction") or "",
                    }
                )
            if drugs:
                drugs.sort(key=lambda d: (not d["targets"], d.get("phase") is None))
                return drugs[:limit]
        return []

    def get_phenotypes(self, disease_id: str, limit: int = 15) -> list[str]:
        """Return human-readable phenotype labels for a disease."""
        glob = self._parquet_glob("disease_phenotype")
        if not glob:
            return []
        cols = self._glob_column_names(glob)
        id_param = normalize_disease_id(disease_id)
        if "phenotypeLabel" in cols:
            sql = _duckdb_parquet_sql(
                glob,
                "SELECT phenotypeLabel AS label FROM read_parquet('{glob}') "
                "WHERE diseaseId = ? ORDER BY frequency DESC LIMIT ?",
            )
            rows = self._query(sql, [id_param, limit])
            labels = [str(r["label"]) for r in rows if r.get("label")]
        else:
            sql = _duckdb_parquet_sql(
                glob,
                "SELECT phenotype FROM read_parquet('{glob}') WHERE disease = ? LIMIT ?",
            )
            rows = self._query(sql, [id_param, limit])
            hpo_labels = _hpo_label_map()
            labels = []
            for row in rows:
                hp_id = str(row.get("phenotype") or "")
                if hp_id:
                    label = hpo_labels.get(hp_id, hp_id)
                    if label not in labels:
                        labels.append(label)
        return labels

    def count_targets(self, efo_id: str) -> int:
        glob = self._parquet_glob("association_overall_direct")
        if not glob:
            return 0
        rows = self._query(
            _duckdb_parquet_sql(
                glob,
                "SELECT COUNT(*) AS n FROM read_parquet('{glob}') WHERE diseaseId = ?",
            ),
            [efo_id],
        )
        return int(rows[0]["n"]) if rows else 0

    def count_drugs(self, efo_id: str) -> int:
        glob = self._parquet_glob("known_drug")
        if not glob:
            return 0
        rows = self._query(
            _duckdb_parquet_sql(
                glob,
                "SELECT COUNT(*) AS n FROM read_parquet('{glob}') WHERE diseaseId = ?",
            ),
            [efo_id],
        )
        return int(rows[0]["n"]) if rows else 0

    def list_diseases(self, min_targets: int = 0, limit: int = 10000) -> list[dict]:
        """List diseases with optional minimum target association count."""
        disease_rows = self._read_table("disease")
        assoc_glob = self._parquet_glob("association_overall_direct")
        counts: dict[str, int] = {}
        if assoc_glob:
            count_rows = self._query(
                _duckdb_parquet_sql(
                    assoc_glob,
                    "SELECT diseaseId, COUNT(*) AS n FROM read_parquet('{glob}') GROUP BY diseaseId",
                )
            )
            counts = {r["diseaseId"]: int(r["n"]) for r in count_rows}

        drug_counts: dict[str, int] = {}
        drug_glob = self._parquet_glob("known_drug")
        if drug_glob:
            drug_rows = self._query(
                _duckdb_parquet_sql(
                    drug_glob,
                    "SELECT diseaseId, COUNT(*) AS n FROM read_parquet('{glob}') GROUP BY diseaseId",
                )
            )
            drug_counts = {r["diseaseId"]: int(r["n"]) for r in drug_rows}

        results = []
        for row in disease_rows:
            efo = row.get("id") or ""
            if not efo:
                continue
            n_targets = counts.get(efo, 0)
            if n_targets < min_targets:
                continue
            results.append(
                {
                    "efo_id": efo,
                    "name": row.get("name") or "",
                    "gene_count": n_targets,
                    "drug_count": drug_counts.get(efo, 0),
                }
            )
        return results[:limit]

    def search_disease_names(self, pattern: str, limit: int = 20) -> list[dict]:
        """Case-insensitive substring search over disease names."""
        needle = pattern.strip().lower()
        if not needle:
            return []
        matches = []
        for row in self._read_table("disease"):
            name = (row.get("name") or "").strip()
            if needle in name.lower():
                matches.append({"id": row["id"], "name": name})
        return matches[:limit]


def normalize_efo(value: str) -> str:
    """Normalize EFO identifiers to EFO_######## format."""
    value = (value or "").strip()
    if not value:
        return ""
    if value.startswith("EFO_"):
        return value
    if value.upper().startswith("EFO:"):
        return "EFO_" + value.split(":", 1)[1]
    if re.fullmatch(r"\d+", value):
        return f"EFO_{value}"
    return value


def mondo_curie_to_ot_id(curie: str) -> str:
    if curie.startswith("MONDO:"):
        return "MONDO_" + curie.split(":", 1)[1]
    if curie.startswith("MONDO_"):
        return curie
    return ""


@lru_cache(maxsize=1)
def _hpo_label_map() -> dict[str, str]:
    """Load HP id -> label mapping from the local HPO ontology artifact."""
    path = repo_root() / "data" / "biomed" / "artifacts" / "hp.json"
    if not path.is_file():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        logger.warning("Could not load HPO label map from %s", path)
        return {}
    mapping: dict[str, str] = {}
    for graph in data.get("graphs", []):
        for node in graph.get("nodes", []):
            match = re.search(r"(HP_\d+)$", node.get("id", ""))
            if match:
                label = node.get("lbl") or ""
                if label and not label.lower().startswith("obsolete"):
                    mapping[match.group(1)] = label
    return mapping


def normalize_disease_id(value: str) -> str:
    """Normalize Open Targets disease ids (EFO_* or MONDO_*)."""
    mondo = mondo_curie_to_ot_id(value)
    if mondo:
        return mondo
    normalized = normalize_efo(value)
    if is_efo_id(normalized):
        return normalized
    return value.strip()


def is_efo_id(value: str) -> bool:
    normalized = normalize_efo(value)
    return bool(normalized) and normalized.startswith("EFO_")


def is_ot_disease_id(value: str) -> bool:
    normalized = normalize_disease_id(value)
    return normalized.startswith("EFO_") or normalized.startswith("MONDO_")


def ot_id_to_mondo_curie(value: str) -> str:
    if value.startswith("MONDO_"):
        return "MONDO:" + value.split("_", 1)[1]
    if value.startswith("MONDO:"):
        return value
    return ""


def efo_from_disease_row(
    row: dict[str, Any],
    mondo_to_efo: Optional[dict[str, str]] = None,
) -> str:
    """Extract an EFO id from an Open Targets disease row (25.03+ uses mixed ontology ids)."""
    row_id = str(row.get("id") or "")
    if is_efo_id(row_id):
        return normalize_efo(row_id)
    for xref in row.get("dbXRefs") or []:
        if isinstance(xref, str) and xref.upper().startswith("EFO:"):
            normalized = normalize_efo(xref)
            if is_efo_id(normalized):
                return normalized
    for anc in row.get("ancestors") or []:
        if isinstance(anc, str) and is_efo_id(anc):
            return normalize_efo(anc)
    mondo_curie = ot_id_to_mondo_curie(row_id)
    if mondo_curie and mondo_to_efo:
        return mondo_to_efo.get(mondo_curie, "")
    return ""


def _resolved_from_row(
    row: dict[str, Any],
    fallback_name: str,
    mondo_to_efo: Optional[dict[str, str]] = None,
) -> Optional[ResolvedDisease]:
    efo_id = efo_from_disease_row(row, mondo_to_efo)
    if not efo_id:
        return None
    synonyms_raw = row.get("synonyms") or ""
    syns: list[str] = []
    if isinstance(synonyms_raw, str) and synonyms_raw.strip():
        try:
            parsed = json.loads(synonyms_raw)
            if isinstance(parsed, list):
                syns = [s for s in parsed if isinstance(s, str)]
        except json.JSONDecodeError:
            syns = [synonyms_raw]
    elif isinstance(synonyms_raw, dict):
        for key in ("hasExactSynonym", "hasRelatedSynonym", "hasNarrowSynonym", "hasBroadSynonym"):
            for item in synonyms_raw.get(key) or []:
                if isinstance(item, str):
                    syns.append(item)
    elif isinstance(synonyms_raw, list):
        syns = [s for s in synonyms_raw if isinstance(s, str)]
    description = row.get("description") or ""
    if isinstance(description, dict):
        description = description.get("value", "")
    return ResolvedDisease(
        efo_id=efo_id,
        name=row.get("name") or fallback_name,
        description=description or "",
        synonyms=syns[:10],
    )
