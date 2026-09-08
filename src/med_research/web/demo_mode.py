"""Centralized public-demo configuration and deny-by-default route policy."""

from __future__ import annotations

from fastapi.responses import JSONResponse

from med_research.web import config as web_config

DEMO_WS_CLOSE_CODE = 1008
DEMO_WS_CLOSE_REASON = "This operation is disabled in the public read-only demo."

BLOCKED_DEMO_PATHS = frozenset(
    {
        # Job submission / streaming
        "/api/jobs",
        "/api/stream",
        # Workspace writes
        "/api/workspace",
        # Admin lifecycle
        "/api/admin",
        # Cache administration
        "/api/system/cache",
        # Live external source/LLM/monitor operations
        "/api/llm",
        "/api/evidence/gather",
        "/api/monitor",
        "/api/agent",
        # Persisted comparison writes
        "/api/v1/nosograph/comparisons",
        "/api/v1/comparisons",
    }
)


def is_demo_mode() -> bool:
    return web_config.parse_demo_mode()


def demo_read_only_response() -> JSONResponse:
    return JSONResponse(
        status_code=403,
        content={
            "code": "demo_read_only",
            "detail": "This operation is disabled in the public read-only demo.",
        },
    )


def is_demo_allowed_path(path: str, method: str) -> bool:
    """Deny mutation-capable families by default; allow reads and known preview paths.

    The current demo policy blocks the routes that would mutate state, run async
    jobs, or invoke live external connectors. Read-only public surfaces and the
    non-persisting Compare preview/export paths remain allowed.
    """
    if not path:
        return False

    path = path.split("?", 1)[0].rstrip("/") or "/"
    method = method.upper()

    if method not in {"GET", "HEAD", "OPTIONS", "POST"}:
        return False

    if method == "POST":
        return path in {
            "/api/v1/nosograph/comparisons/preview",
            "/api/v1/nosograph/comparisons/preview/export",
        }

    for blocked in BLOCKED_DEMO_PATHS:
        if path == blocked or path.startswith(blocked + "/"):
            return False

    return True
