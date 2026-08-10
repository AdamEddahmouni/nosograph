import asyncio
import os
from typing import Awaitable, Callable

from fastapi import Request
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response
from starlette.types import ASGIApp

from med_research.web.config import DASHBOARD_CSP_MODE, DASHBOARD_CSP_POLICY
from med_research.web.rate_limit import (
    InMemoryRateLimitStore,
    RateLimitStore,
    create_rate_limit_store,
)

PROTECTED_PREFIXES = (
    "/api/jobs",
    "/api/llm/extract",
    "/api/evidence/gather",
    "/api/system/cache",
)

API_KEY = os.environ.get("API_KEY", "")

RATE_LIMIT_REQUESTS = int(os.environ.get("RATE_LIMIT_REQUESTS", "60"))
RATE_LIMIT_WINDOW = int(os.environ.get("RATE_LIMIT_WINDOW", "60"))


def _get_client_ip(request: Request) -> str:
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


MAX_REQUEST_BODY_BYTES = int(os.environ.get("MAX_REQUEST_BODY_BYTES", str(1024 * 1024)))


class DashboardCSPMiddleware(BaseHTTPMiddleware):
    """Attach the opt-in CSP to the dashboard document only.

    API responses and downloaded reports keep their existing headers. The
    policy blocks inline script/event attributes while allowing the dashboard's
    external local JavaScript, WebSocket progress stream, and Google font CSS.
    """

    async def dispatch(
        self, request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        response = await call_next(request)
        if DASHBOARD_CSP_MODE in {"enforce", "report-only"} and request.url.path in {"/", "/index.html"}:
            header = (
                "Content-Security-Policy"
                if DASHBOARD_CSP_MODE == "enforce"
                else "Content-Security-Policy-Report-Only"
            )
            response.headers[header] = DASHBOARD_CSP_POLICY
        return response


class RequestBodySizeLimitMiddleware(BaseHTTPMiddleware):
    """Reject oversized request bodies before handlers run."""

    def __init__(self, app: ASGIApp, max_bytes: int = MAX_REQUEST_BODY_BYTES) -> None:
        super().__init__(app)
        self.max_bytes = max_bytes

    async def dispatch(
        self, request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        if request.method in ("POST", "PUT", "PATCH"):
            content_length = request.headers.get("content-length")
            if content_length and int(content_length) > self.max_bytes:
                return JSONResponse(
                    status_code=413,
                    content={"detail": "Request body too large"},
                )
        return await call_next(request)


class AuthMiddleware(BaseHTTPMiddleware):
    """Simple API key check on protected write/mutation endpoints.

    If API_KEY is not set, authentication is disabled (dev mode).
    All GET/read endpoints remain public regardless.
    """

    def __init__(self, app: ASGIApp) -> None:
        super().__init__(app)

    async def dispatch(
        self, request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        if not API_KEY:
            return await call_next(request)

        is_auth_endpoint = request.url.path.startswith("/api/auth/")
        if not is_auth_endpoint and (
            request.method in ("POST", "PUT", "PATCH", "DELETE")
            or any(request.url.path.startswith(prefix) for prefix in PROTECTED_PREFIXES)
        ):
            auth_header = request.headers.get("X-API-Key", "")
            if auth_header != API_KEY:
                return JSONResponse(
                    status_code=401,
                    content={"detail": "Invalid or missing API key"},
                )

        return await call_next(request)


class RateLimitMiddleware(BaseHTTPMiddleware):
    """Sliding-window rate limiter per client IP.

    Uses a :class:`RateLimitStore` — Redis-backed when reachable (shared
    across app instances), in-memory otherwise. The store check runs off
    the event loop so a slow Redis call cannot stall the server.
    """

    def __init__(self, app: ASGIApp, store: RateLimitStore | None = None) -> None:
        super().__init__(app)
        if store is not None:
            self._store = store
        elif not RATE_LIMIT_REQUESTS:
            self._store = InMemoryRateLimitStore()
        else:
            self._store = create_rate_limit_store()

    async def dispatch(
        self, request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        if not RATE_LIMIT_REQUESTS:
            return await call_next(request)

        ip = _get_client_ip(request)
        allowed, retry_after = await asyncio.to_thread(
            self._store.check, ip, RATE_LIMIT_REQUESTS, RATE_LIMIT_WINDOW
        )
        if not allowed:
            return JSONResponse(
                status_code=429,
                content={
                    "detail": "Too many requests. Please try again later.",
                    "retry_after": int(retry_after) or int(RATE_LIMIT_WINDOW),
                },
            )

        return await call_next(request)
