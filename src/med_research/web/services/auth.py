"""Authentication helpers for server-derived researcher principals.

The workspace never treats a browser-supplied researcher label as identity in
production. Local development uses a signed HttpOnly session cookie; deployments
behind an identity-aware reverse proxy may use a server-verified remote-user
header from a configured proxy address.
"""

from __future__ import annotations

import base64
import binascii
import hashlib
import hmac
import json
import os
import time
from typing import Any

from fastapi import HTTPException, Request, Response

SESSION_COOKIE = "med_research_session"
_SESSION_MAX_AGE = 8 * 60 * 60
_USER_PATTERN = r"^[A-Za-z0-9][A-Za-z0-9_.:@+-]{0,63}$"


def _mode() -> str:
    return os.environ.get("AUTH_MODE", "local").strip().lower()


def _debug() -> bool:
    return os.environ.get("DEBUG", "false").lower() == "true"


def _session_secret() -> bytes:
    configured = os.environ.get("AUTH_SESSION_SECRET") or os.environ.get("API_KEY")
    if configured:
        return configured.encode("utf-8")
    if _debug():
        return b"med-research-development-session-secret"
    raise HTTPException(status_code=503, detail="AUTH_SESSION_SECRET is not configured")


def _validate_user(value: str) -> str:
    import re

    normalized = value.strip()
    if not re.fullmatch(_USER_PATTERN, normalized):
        raise HTTPException(status_code=400, detail="Invalid authenticated researcher principal")
    return normalized


def _encode(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).decode("ascii").rstrip("=")


def _decode(value: str) -> bytes:
    return base64.urlsafe_b64decode(value + "=" * (-len(value) % 4))


def create_session_token(researcher_id: str, *, now: int | None = None) -> str:
    principal = _validate_user(researcher_id)
    issued_at = int(time.time() if now is None else now)
    payload = {"sub": principal, "iat": issued_at, "exp": issued_at + _SESSION_MAX_AGE}
    encoded = _encode(json.dumps(payload, separators=(",", ":")).encode("utf-8"))
    signature = hmac.new(_session_secret(), encoded.encode("ascii"), hashlib.sha256).digest()
    return f"{encoded}.{_encode(signature)}"


def verify_session_token(token: str, *, now: int | None = None) -> str | None:
    try:
        encoded, signature = token.split(".", 1)
        expected = hmac.new(_session_secret(), encoded.encode("ascii"), hashlib.sha256).digest()
        if not hmac.compare_digest(_decode(signature), expected):
            return None
        payload: dict[str, Any] = json.loads(_decode(encoded))
        current = int(time.time() if now is None else now)
        if int(payload.get("exp", 0)) < current:
            return None
        return _validate_user(str(payload["sub"]))
    except (
        ValueError,
        KeyError,
        TypeError,
        json.JSONDecodeError,
        UnicodeDecodeError,
        binascii.Error,
        HTTPException,
    ):
        return None


def set_session_cookie(response: Response, researcher_id: str) -> None:
    response.set_cookie(
        SESSION_COOKIE,
        create_session_token(researcher_id),
        max_age=_SESSION_MAX_AGE,
        httponly=True,
        secure=not _debug(),
        samesite="lax",
        path="/",
    )


def clear_session_cookie(response: Response) -> None:
    response.delete_cookie(SESSION_COOKIE, path="/")


def _local_users() -> dict[str, str]:
    """Read development users from LOCAL_AUTH_USERS JSON or ``user=password`` pairs."""
    raw = os.environ.get("LOCAL_AUTH_USERS", "").strip()
    if not raw:
        return {}
    try:
        parsed = json.loads(raw)
        if isinstance(parsed, dict):
            return {str(key): str(value) for key, value in parsed.items()}
    except json.JSONDecodeError:
        pass
    users: dict[str, str] = {}
    for item in raw.split(","):
        if "=" in item:
            username, password = item.split("=", 1)
            users[username.strip()] = password
    return users


def authenticate_local_user(username: str, password: str) -> str | None:
    principal = _validate_user(username)
    configured = _local_users().get(principal)
    if configured is None:
        return None
    if hmac.compare_digest(configured, password):
        return principal
    return None


def _trusted_proxy_addresses() -> set[str]:
    return {
        value.strip()
        for value in os.environ.get("AUTH_TRUSTED_PROXY_IPS", "").split(",")
        if value.strip()
    }


def _proxy_principal(request: Request) -> str | None:
    source = request.client.host if request.client else ""
    if not source or source not in _trusted_proxy_addresses():
        return None
    for header in ("X-Authenticated-User", "X-Auth-Request-User", "Remote-User"):
        value = request.headers.get(header)
        if value:
            return _validate_user(value)
    return None


def resolve_principal(request: Request) -> str | None:
    """Resolve a principal from a signed session or a configured trusted proxy."""
    mode = _mode()
    if mode == "proxy":
        return _proxy_principal(request)
    if mode not in {"local", "legacy"}:
        raise HTTPException(status_code=500, detail=f"Unsupported AUTH_MODE: {mode}")

    token = request.cookies.get(SESSION_COOKIE)
    if token:
        principal = verify_session_token(token)
        if principal:
            return principal
    if mode == "legacy" or (_debug() and request.headers.get("X-Researcher-ID")):
        # Compatibility is deliberately limited to DEBUG/explicit legacy mode and
        # is not an authentication mechanism for deployed environments.
        value = request.headers.get("X-Researcher-ID", "anonymous")
        return _validate_user(value)
    return None


def get_researcher_id(request: Request) -> str:
    """Return the server-derived researcher ID or reject an unauthenticated request."""
    principal = resolve_principal(request)
    if principal:
        return principal
    if _debug():
        return "anonymous"
    raise HTTPException(
        status_code=401,
        detail="Authentication required. Sign in or configure a trusted identity proxy.",
        headers={"WWW-Authenticate": "Bearer"},
    )


def require_authenticated(request: Request) -> str:
    """Alias used by routes that must not accept the debug anonymous fallback."""
    principal = resolve_principal(request)
    if not principal:
        raise HTTPException(status_code=401, detail="Authentication required")
    return principal


def auth_status(request: Request) -> dict[str, Any]:
    principal = resolve_principal(request)
    return {"authenticated": principal is not None, "researcher_id": principal}


def login_response(researcher_id: str) -> Response:
    response = Response(
        content=json.dumps({"authenticated": True, "researcher_id": researcher_id}),
        media_type="application/json",
    )
    set_session_cookie(response, researcher_id)
    return response
