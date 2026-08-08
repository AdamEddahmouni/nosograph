import contextlib
import hashlib
import json
import os
import re
import tempfile
import time
from pathlib import Path
from typing import Any, Optional

from med_research.exceptions import CacheCorruptionError
from med_research.logging_config import get_logger

logger = get_logger(__name__)

DEFAULT_CACHE_DIR = Path(__file__).parent.parent / "data" / "cache"
DEFAULT_TTL_SECONDS = 24 * 3600  # 24 hours

_DEFAULT_MANAGER: Optional["CacheManager"] = None


def env_use_cache() -> bool:
    """Whether caching is enabled via the ``USE_CACHE`` environment variable."""
    return os.environ.get("USE_CACHE", "true").lower() == "true"


def disease_output_path(data_dir: Path, stem: str, disease_id: str) -> Path:
    """Per-disease module output path: ``{data_dir}/{stem}_{disease_id}.json``."""
    return Path(data_dir) / f"{stem}_{disease_id}.json"


def write_json_atomic(
    path: Path,
    data: Any,
    *,
    indent: int = 2,
    default: Any = str,
) -> None:
    """Atomically write JSON via a temp file and ``os.replace``."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(
        suffix=".tmp",
        prefix=f"{path.stem}.",
        dir=str(path.parent),
    )
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(data, handle, indent=indent, ensure_ascii=False, default=default)
        for attempt in range(3):
            try:
                os.replace(tmp_name, path)
                return
            except PermissionError:
                if attempt == 2:
                    raise
                if path.exists():
                    with contextlib.suppress(OSError):
                        path.unlink()
                time.sleep(0.05)
    finally:
        # On success os.replace() already moved the temp file away, so this
        # unlink is a no-op; it only cleans up on failure paths.
        with contextlib.suppress(OSError):
            os.unlink(tmp_name)

# Namespace convention: one namespace per pipeline module_id
NS_GWAS = "gwas"
NS_PPI = "ppi"
NS_ENRICHMENT = "enrichment"
NS_CLINICAL_TRIALS = "clinical_trials"
NS_LITERATURE_MINING = "literature_mining"
NS_EVIDENCE_GATHER = "evidence_gather"
NS_LLM_EXTRACTOR = "llm_extractor"
NS_GEO = "geo"


class CacheManager:
    """JSON-file-based cache with TTL support and namespace isolation.

    Usage:
        cache = CacheManager(cache_dir=Path("data/cache"), ttl_seconds=86400)
        data = cache.get("evidence", "lupus|||pubmed|||20")
        if data is None:
            data = expensive_api_call()
            cache.set("evidence", "lupus|||pubmed|||20", data)
        cache.clear("evidence")
    """

    def __init__(
        self,
        cache_dir: Path = DEFAULT_CACHE_DIR,
        ttl_seconds: int = DEFAULT_TTL_SECONDS,
        *,
        respect_env_use_cache: bool = False,
    ):
        self._dir = Path(cache_dir)
        self._ttl_seconds = ttl_seconds
        self._respect_env_use_cache = respect_env_use_cache

    def _cache_active(self) -> bool:
        return not self._respect_env_use_cache or env_use_cache()

    def _namespace_dir(self, namespace: str) -> Path:
        ns_dir = self._dir / namespace
        ns_dir.mkdir(parents=True, exist_ok=True)
        return ns_dir

    def _safe_key_filename(self, key: str) -> str:
        """Map a logical cache key to a filesystem-safe filename."""
        safe = re.sub(r'[<>:"/\\|?*]', "_", key).strip()
        safe = safe.replace(" ", "_")
        if len(safe) <= 120:
            return safe
        return hashlib.sha256(key.encode("utf-8")).hexdigest()

    def _cache_path(self, namespace: str, key: str) -> Path:
        safe_key = self._safe_key_filename(key)
        return self._namespace_dir(namespace) / f"{safe_key}.json"

    def get(self, namespace: str, key: str, ttl_seconds: Optional[int] = None) -> Optional[Any]:
        if not self._cache_active():
            return None
        cache_path = self._cache_path(namespace, key)
        ttl = ttl_seconds if ttl_seconds is not None else self._ttl_seconds

        if not cache_path.exists():
            return None

        try:
            entry = json.loads(cache_path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError) as e:
            logger.warning("Cache corrupt for %s/%s: %s", namespace, key, e)
            return None

        if not isinstance(entry, dict) or "timestamp" not in entry:
            raise CacheCorruptionError(
                f"Cache entry {cache_path} missing timestamp field"
            )

        age = time.time() - entry["timestamp"]
        if age > ttl:
            logger.debug("Cache expired for %s/%s (age=%.0fs, ttl=%ds)", namespace, key, age, ttl)
            return None

        logger.debug("Cache hit for %s/%s (age=%.0fs)", namespace, key, age)
        return entry["data"]

    def set(self, namespace: str, key: str, data: Any) -> None:
        if not self._cache_active():
            return
        cache_path = self._cache_path(namespace, key)
        entry = {
            "timestamp": time.time(),
            "data": data,
        }
        write_json_atomic(cache_path, entry)
        logger.debug("Cache set for %s/%s", namespace, key)

    def clear(self, namespace: Optional[str] = None) -> int:
        removed = 0
        if namespace:
            ns_dir = self._dir / namespace
            if ns_dir.exists():
                for f in ns_dir.glob("*.json"):
                    f.unlink()
                    removed += 1
                logger.info("Cleared %d entries from cache namespace '%s'", removed, namespace)
        else:
            if self._dir.exists():
                for f in self._dir.glob("**/*.json"):
                    f.unlink()
                    removed += 1
                logger.info("Cleared %d entries from all cache namespaces", removed)
        return removed

    def stats(self) -> dict[str, Any]:
        namespaces: dict[str, dict] = {}
        total = 0
        if self._dir.exists():
            for ns_dir in sorted(self._dir.iterdir()):
                if ns_dir.is_dir():
                    ns_entries = list(ns_dir.glob("*.json"))
                    total += len(ns_entries)
                    namespaces[ns_dir.name] = {
                        "entries": len(ns_entries),
                        "size_bytes": sum(f.stat().st_size for f in ns_entries),
                    }
        return {"total_entries": total, "namespaces": namespaces}

    def cleanup(self, ttl_seconds: Optional[int] = None) -> int:
        ttl = ttl_seconds if ttl_seconds is not None else self._ttl_seconds
        removed = 0
        if self._dir.exists():
            for cache_file in self._dir.glob("**/*.json"):
                try:
                    entry = json.loads(cache_file.read_text(encoding="utf-8"))
                    age = time.time() - entry.get("timestamp", 0)
                    if age > ttl:
                        cache_file.unlink()
                        removed += 1
                except (json.JSONDecodeError, OSError):
                    cache_file.unlink()
                    removed += 1
        logger.info("Cleaned up %d expired cache entries (TTL=%ds)", removed, ttl)
        return removed


def get_cache_manager(
    cache_dir: Optional[Path] = None,
    ttl_seconds: Optional[int] = None,
) -> CacheManager:
    """Return a shared CacheManager instance (new object, same default paths).

    The default singleton respects ``USE_CACHE`` from the environment. Instances
    created with an explicit ``cache_dir`` or ``ttl_seconds`` always allow
    cache I/O (for tests and isolated stores).
    """
    global _DEFAULT_MANAGER
    if cache_dir is not None or ttl_seconds is not None:
        return CacheManager(
            cache_dir=cache_dir or DEFAULT_CACHE_DIR,
            ttl_seconds=ttl_seconds or DEFAULT_TTL_SECONDS,
            respect_env_use_cache=False,
        )
    if _DEFAULT_MANAGER is None:
        _DEFAULT_MANAGER = CacheManager(
            cache_dir=DEFAULT_CACHE_DIR,
            respect_env_use_cache=True,
        )
    return _DEFAULT_MANAGER


def cache_get(
    namespace: str,
    key: str,
    use_cache: bool = True,
    ttl_seconds: Optional[int] = None,
    cache: Optional[CacheManager] = None,
) -> Optional[Any]:
    """Read from cache when ``use_cache`` and ``USE_CACHE`` env are enabled."""
    if not use_cache:
        return None
    if cache is None and not env_use_cache():
        return None
    mgr = cache or get_cache_manager()
    return mgr.get(namespace, key, ttl_seconds=ttl_seconds)


def cache_set(
    namespace: str,
    key: str,
    data: Any,
    use_cache: bool = True,
    cache: Optional[CacheManager] = None,
) -> None:
    """Write to cache when ``use_cache`` and ``USE_CACHE`` env are enabled."""
    if not use_cache:
        return
    if cache is None and not env_use_cache():
        return
    mgr = cache or get_cache_manager()
    mgr.set(namespace, key, data)


def load_legacy_json(path: Path) -> Optional[Any]:
    """Load raw JSON from a legacy per-module cache file (no TTL wrapper)."""
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as exc:
        logger.warning("Legacy cache corrupt at %s: %s", path, exc)
        return None


# Legacy flat-file locations (pre-CacheManager migration)
_PIPELINE_DIR = Path(__file__).parent / "pipeline"
_BIOINFORMATICS_DATA = _PIPELINE_DIR / "bioinformatics" / "data"
_LITERATURE_DATA = _PIPELINE_DIR / "literature_mining" / "data"
_CLINICAL_TRIALS_DATA = _PIPELINE_DIR / "clinical_trials" / "data"
_EVIDENCE_DATA = _PIPELINE_DIR / "evidence" / "data"
_GEO_CACHE_DIR = _PIPELINE_DIR / "gene_expression" / "data" / "geo_cache"


def _migrate_entry(
    cache: CacheManager,
    namespace: str,
    key: str,
    data: Any,
    *,
    dry_run: bool = False,
) -> str:
    """Migrate one cache entry. Returns 'migrated', 'skipped', or 'error'."""
    if cache.get(namespace, key, ttl_seconds=10**9) is not None:
        return "skipped"
    if dry_run:
        return "migrated"
    try:
        cache.set(namespace, key, data)
        return "migrated"
    except OSError as exc:
        logger.warning("Failed to migrate %s/%s: %s", namespace, key, exc)
        return "error"


def _count_result(results: dict[str, dict[str, int]], status: str) -> None:
    results["total"][status] = results["total"].get(status, 0) + 1


def _migrate_gwas(cache: CacheManager, *, dry_run: bool = False) -> dict[str, dict[str, int]]:
    counts: dict[str, dict[str, int]] = {"gwas": {}, "total": {}}
    if not _BIOINFORMATICS_DATA.exists():
        return counts

    for path in sorted(_BIOINFORMATICS_DATA.glob("gwas_cache*.json")):
        legacy = load_legacy_json(path)
        if not legacy or "gwas_results" not in legacy or "crossref" not in legacy:
            continue
        name = path.stem
        disease_id = "sle" if name == "gwas_cache" else name.removeprefix("gwas_cache_")
        payload = {
            "gwas_results": legacy["gwas_results"],
            "crossref": legacy["crossref"],
        }
        status = _migrate_entry(cache, NS_GWAS, disease_id, payload, dry_run=dry_run)
        counts["gwas"][status] = counts["gwas"].get(status, 0) + 1
        _count_result(counts, status)
    return counts


def _migrate_enrichment(cache: CacheManager, *, dry_run: bool = False) -> dict[str, dict[str, int]]:
    counts: dict[str, dict[str, int]] = {"enrichment": {}, "total": {}}
    path = _BIOINFORMATICS_DATA / "enrichment_cache.json"
    legacy = load_legacy_json(path)
    if not legacy:
        return counts

    cache_key = legacy.get("cache_key")
    libraries = legacy.get("libraries")
    top_n = legacy.get("top_n")
    results = legacy.get("results")
    if cache_key is None or libraries is None or top_n is None or results is None:
        return counts

    lookup_key = f"{cache_key}|||{json.dumps(libraries, sort_keys=True)}|||{top_n}"
    status = _migrate_entry(cache, NS_ENRICHMENT, lookup_key, results, dry_run=dry_run)
    counts["enrichment"][status] = counts["enrichment"].get(status, 0) + 1
    _count_result(counts, status)
    return counts


def _migrate_ppi(cache: CacheManager, *, dry_run: bool = False) -> dict[str, dict[str, int]]:
    counts: dict[str, dict[str, int]] = {"ppi": {}, "total": {}}
    path = _BIOINFORMATICS_DATA / "ppi_cache.json"
    legacy = load_legacy_json(path)
    if not legacy:
        return counts

    cache_key = legacy.get("cache_key")
    confidence = legacy.get("confidence")
    if cache_key is None or confidence is None:
        return counts

    lookup_key = f"{cache_key}|||{confidence}"
    status = _migrate_entry(cache, NS_PPI, lookup_key, legacy, dry_run=dry_run)
    counts["ppi"][status] = counts["ppi"].get(status, 0) + 1
    _count_result(counts, status)
    return counts


def _migrate_literature(cache: CacheManager, *, dry_run: bool = False) -> dict[str, dict[str, int]]:
    counts: dict[str, dict[str, int]] = {"literature_mining": {}, "total": {}}
    if not _LITERATURE_DATA.exists():
        return counts

    for path in sorted(_LITERATURE_DATA.glob("pubmed_cache*.json")):
        legacy = load_legacy_json(path)
        if not isinstance(legacy, list):
            continue
        name = path.stem
        disease_id = "sle" if name == "pubmed_cache" else name.removeprefix("pubmed_cache_")
        status = _migrate_entry(
            cache, NS_LITERATURE_MINING, disease_id, legacy, dry_run=dry_run
        )
        counts["literature_mining"][status] = counts["literature_mining"].get(status, 0) + 1
        _count_result(counts, status)
    return counts


def _migrate_clinical_trials(cache: CacheManager, *, dry_run: bool = False) -> dict[str, dict[str, int]]:
    counts: dict[str, dict[str, int]] = {"clinical_trials": {}, "total": {}}
    if not _CLINICAL_TRIALS_DATA.exists():
        return counts

    for path in sorted(_CLINICAL_TRIALS_DATA.glob("ct_cache_*.json")):
        legacy = load_legacy_json(path)
        if not legacy:
            continue
        parts = path.stem.removeprefix("ct_cache_").rsplit("_", 1)
        if len(parts) != 2:
            continue
        disease_id, query_key = parts
        lookup_key = f"{disease_id}|||{query_key}"
        status = _migrate_entry(
            cache, NS_CLINICAL_TRIALS, lookup_key, legacy, dry_run=dry_run
        )
        counts["clinical_trials"][status] = counts["clinical_trials"].get(status, 0) + 1
        _count_result(counts, status)
    return counts


def _migrate_dict_namespace(
    cache: CacheManager,
    namespace: str,
    path: Path,
    *,
    dry_run: bool = False,
) -> dict[str, dict[str, int]]:
    counts: dict[str, dict[str, int]] = {namespace: {}, "total": {}}
    legacy = load_legacy_json(path)
    if not isinstance(legacy, dict):
        return counts

    for key, value in legacy.items():
        status = _migrate_entry(cache, namespace, key, value, dry_run=dry_run)
        counts[namespace][status] = counts[namespace].get(status, 0) + 1
        _count_result(counts, status)
    return counts


def _migrate_geo(cache: CacheManager, *, dry_run: bool = False) -> dict[str, dict[str, int]]:
    counts: dict[str, dict[str, int]] = {"geo": {}, "total": {}}
    if not _GEO_CACHE_DIR.exists():
        return counts

    for path in sorted(_GEO_CACHE_DIR.glob("*.json")):
        legacy = load_legacy_json(path)
        if legacy is None:
            continue
        key = path.stem
        status = _migrate_entry(cache, NS_GEO, key, legacy, dry_run=dry_run)
        counts["geo"][status] = counts["geo"].get(status, 0) + 1
        _count_result(counts, status)
    return counts


def _merge_migration_counts(target: dict[str, dict[str, int]], source: dict[str, dict[str, int]]) -> None:
    for namespace, statuses in source.items():
        if namespace not in target:
            target[namespace] = {}
        for status, count in statuses.items():
            target[namespace][status] = target[namespace].get(status, 0) + count


def migrate_legacy_caches(
    cache: Optional[CacheManager] = None,
    *,
    dry_run: bool = False,
) -> dict[str, Any]:
    """One-time migration of legacy flat JSON caches into CacheManager namespaces.

    Scans module data directories for pre-v2 cache files and copies them into
    the central ``data/cache/<namespace>/`` store. Existing central entries are
    left unchanged (skipped).

    Returns a summary dict with per-namespace migrated/skipped/error counts.
    """
    mgr = cache or get_cache_manager()
    summary: dict[str, Any] = {
        "dry_run": dry_run,
        "namespaces": {},
        "total": {"migrated": 0, "skipped": 0, "error": 0},
    }

    migrators = (
        _migrate_gwas,
        _migrate_enrichment,
        _migrate_ppi,
        _migrate_literature,
        _migrate_clinical_trials,
        lambda c, **kw: _migrate_dict_namespace(
            c, NS_EVIDENCE_GATHER, _EVIDENCE_DATA / "evidence_cache.json", **kw
        ),
        lambda c, **kw: _migrate_dict_namespace(
            c, NS_LLM_EXTRACTOR, _EVIDENCE_DATA / "extraction_cache.json", **kw
        ),
        _migrate_geo,
    )

    for migrate_fn in migrators:
        result = migrate_fn(mgr, dry_run=dry_run)
        _merge_migration_counts(summary["namespaces"], result)
        for status in ("migrated", "skipped", "error"):
            summary["total"][status] += result.get("total", {}).get(status, 0)

    logger.info(
        "Legacy cache migration complete: %d migrated, %d skipped, %d errors",
        summary["total"]["migrated"],
        summary["total"]["skipped"],
        summary["total"]["error"],
    )
    return summary
