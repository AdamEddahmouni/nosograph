import json
import time
from pathlib import Path
from typing import Any, Optional

from med_research.exceptions import CacheCorruptionError
from med_research.logging_config import get_logger

logger = get_logger(__name__)

DEFAULT_CACHE_DIR = Path(__file__).parent.parent / "data" / "cache"
DEFAULT_TTL_SECONDS = 24 * 3600  # 24 hours


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
    ):
        self._dir = Path(cache_dir)
        self._ttl_seconds = ttl_seconds

    def _namespace_dir(self, namespace: str) -> Path:
        ns_dir = self._dir / namespace
        ns_dir.mkdir(parents=True, exist_ok=True)
        return ns_dir

    def _cache_path(self, namespace: str, key: str) -> Path:
        safe_key = key.replace("/", "_").replace("\\", "_").replace(" ", "_")
        return self._namespace_dir(namespace) / f"{safe_key}.json"

    def get(self, namespace: str, key: str, ttl_seconds: Optional[int] = None) -> Optional[Any]:
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
        cache_path = self._cache_path(namespace, key)
        entry = {
            "timestamp": time.time(),
            "data": data,
        }
        cache_path.write_text(json.dumps(entry, indent=2, ensure_ascii=False), encoding="utf-8")
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
