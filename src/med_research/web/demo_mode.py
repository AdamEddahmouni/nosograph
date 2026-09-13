"""Centralized public-demo configuration and deny-by-default route policy.

DEMO_MODE is an explicit opt-in. There is no hosted public app on GitHub Pages
or in v0.2.1. Default is off so local/self-host cannot activate a read-only
demo by accident.

Ported from PR #103 (feat/public-demo-mode) without snapshot datasets,
preview-export machinery, or any deploy workflow.
"""

from __future__ import annotations

from fastapi.responses import JSONResponse

from med_research.web import config as web_config

DEMO_WS_CLOSE_CODE = 1008
DEMO_WS_CLOSE_REASON = "This operation is disabled in the public read-only demo."

BLOCKED_DEMO_PATHS = frozenset(
    {
        "/api/jobs",
        "/api/stream",
        "/api/workspace",
        "/api/admin",
        "/api/system/cache",
        "/api/llm",
        "/api/evidence/gather",
        "/api/monitor",
        "/api/agent",
        "/api/v1/nosograph/comparisons",
        "/api/v1/comparisons",
    }
)

_DEMO_POST_ALLOW = frozenset(
    {
        "/api/v1/nosograph/comparisons/preview",
        "/api/v1/nosograph/comparisons/preview/export",
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
    """Deny mutation-capable families; allow ordinary reads.

    POST is allowed only for non-persisting Compare preview paths (when those
    routes exist). Everything else must be GET/HEAD/OPTIONS.
    """
    if not path:
        return False

    path = path.split("?", 1)[0].rstrip("/") or "/"
    method = method.upper()

    if method not in {"GET", "HEAD", "OPTIONS", "POST"}:
        return False

    if method == "POST":
        return path in _DEMO_POST_ALLOW

    for blocked in BLOCKED_DEMO_PATHS:
        if path == blocked or path.startswith(blocked + "/"):
            return False

    return True
