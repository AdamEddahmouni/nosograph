import os
import time
from collections import defaultdict
from typing import Callable

from fastapi import Request
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp

PROTECTED_PREFIXES = (
    "/api/jobs",
    "/api/llm/extract",
    "/api/evidence/gather",
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


class RequestBodySizeLimitMiddleware(BaseHTTPMiddleware):
    """Reject oversized request bodies before handlers run."""

    def __init__(self, app: ASGIApp, max_bytes: int = MAX_REQUEST_BODY_BYTES) -> None:
        super().__init__(app)
        self.max_bytes = max_bytes

    async def dispatch(self, request: Request, call_next: Callable):
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

    async def dispatch(self, request: Request, call_next: Callable):
        if not API_KEY:
            return await call_next(request)

        if request.method in ("POST", "PUT", "PATCH", "DELETE") or any(
            request.url.path.startswith(prefix) for prefix in PROTECTED_PREFIXES
        ):
            auth_header = request.headers.get("X-API-Key", "")
            if auth_header != API_KEY:
                return JSONResponse(
                    status_code=401,
                    content={"detail": "Invalid or missing API key"},
                )

        return await call_next(request)


class RateLimitMiddleware(BaseHTTPMiddleware):
    """Simple in-memory sliding-window rate limiter per client IP."""

    def __init__(self, app: ASGIApp) -> None:
        super().__init__(app)
        self._store: dict[str, list[float]] = defaultdict(list)

    def _cleanup(self, now: float) -> None:
        threshold = now - RATE_LIMIT_WINDOW
        for key in list(self._store):
            self._store[key] = [t for t in self._store[key] if t > threshold]
            if not self._store[key]:
                del self._store[key]

    async def dispatch(self, request: Request, call_next: Callable):
        if not RATE_LIMIT_REQUESTS:
            return await call_next(request)

        ip = _get_client_ip(request)
        now = time.time()
        window_start = now - RATE_LIMIT_WINDOW

        timestamps = self._store[ip]
        timestamps = [t for t in timestamps if t > window_start]
        self._store[ip] = timestamps

        if len(timestamps) >= RATE_LIMIT_REQUESTS:
            self._cleanup(now)
            return JSONResponse(
                status_code=429,
                content={
                    "detail": "Too many requests. Please try again later.",
                    "retry_after": int(RATE_LIMIT_WINDOW),
                },
            )

        self._store[ip].append(now)
        self._cleanup(now)
        return await call_next(request)
