"""Shared provenance and reproducibility metadata helpers."""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from importlib.metadata import PackageNotFoundError, version
from typing import Any

SCHEMA_VERSION = "1.0"


def utc_now_iso() -> str:
    """Return the current timestamp as an explicit UTC ISO-8601 string."""
    return datetime.now(timezone.utc).isoformat()


def package_version() -> str:
    try:
        return version("med-research")
    except PackageNotFoundError:
        return "2.0.0"


def _json_safe(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(key): _json_safe(value[key]) for key in sorted(value)}
    if isinstance(value, (list, tuple, set)):
        return [_json_safe(item) for item in value]
    if hasattr(value, "model_dump"):
        return _json_safe(value.model_dump(mode="json"))
    if hasattr(value, "isoformat"):
        return value.isoformat()
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    return str(value)


def reproducibility_fingerprint(inputs: dict[str, Any]) -> str:
    """Hash normalized inputs while excluding volatile runtime fields."""
    stable = _json_safe(inputs)
    if isinstance(stable, dict):
        for key in ("run_id", "started_at", "completed_at", "retrieval_time", "extracted_at"):
            stable.pop(key, None)
    payload = json.dumps(stable, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:20]


def build_provenance(
    *,
    disease_id: str,
    module: str,
    sources: list[str] | tuple[str, ...] = (),
    query: str | None = None,
    filters: dict[str, Any] | None = None,
    cache_or_live: str = "unknown",
    model: str | None = None,
    scoring: dict[str, Any] | None = None,
    inputs: dict[str, Any] | None = None,
    run_id: str | None = None,
    retrieval_times: dict[str, str] | None = None,
) -> dict[str, Any]:
    """Build deterministic, secret-free metadata for a computation or report."""
    stable_inputs = {
        "disease_id": disease_id,
        "module": module,
        "sources": sorted(str(source) for source in sources),
        "query": query or "",
        "filters": filters or {},
        "cache_or_live": cache_or_live,
        "model": model,
        "scoring": scoring or {},
        **(inputs or {}),
    }
    payload = {
        "schema_version": SCHEMA_VERSION,
        "run_id": run_id,
        "disease_id": disease_id,
        "module": module,
        "package_version": package_version(),
        "module_version": package_version(),
        "sources": stable_inputs["sources"],
        "query": query or "",
        "filters": _json_safe(filters or {}),
        "cache_or_live": cache_or_live,
        "model": model,
        "scoring": _json_safe(scoring or {}),
        "retrieval_times": _json_safe(retrieval_times or {}),
        "fingerprint": reproducibility_fingerprint(stable_inputs),
        "generated_at": utc_now_iso(),
    }
    return {key: value for key, value in payload.items() if value is not None}
