"""Signed bearer links that open a researcher's digest review workspace."""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
from datetime import datetime, timedelta, timezone
from typing import Any
from urllib.parse import quote


def _secret() -> str:
    return (
        os.environ.get("WORKSPACE_REVIEW_LINK_SECRET", "").strip()
        or os.environ.get("API_KEY", "").strip()
    )


def _public_url() -> str:
    return os.environ.get("WORKSPACE_PUBLIC_URL", "http://127.0.0.1:8000").rstrip("/")


def _encode(payload: dict[str, Any]) -> str:
    encoded = (
        base64.urlsafe_b64encode(
            json.dumps(payload, separators=(",", ":"), sort_keys=True).encode()
        )
        .decode()
        .rstrip("=")
    )
    signature = hmac.new(_secret().encode(), encoded.encode(), hashlib.sha256).digest()
    return f"{encoded}.{base64.urlsafe_b64encode(signature).decode().rstrip('=')}"


def create_review_link(
    researcher_id: str,
    digest_key: str,
    *,
    now: datetime | None = None,
    ttl: timedelta = timedelta(days=8),
) -> str | None:
    """Create an expiring link, or return None when no deployment secret is configured."""
    if not _secret():
        return None
    current = now or datetime.now(timezone.utc)
    payload = {
        "researcher_id": researcher_id,
        "digest_key": digest_key,
        "expires_at": int((current + ttl).timestamp()),
    }
    return f"{_public_url()}/api/workspace/digest/review?token={quote(_encode(payload))}"


def verify_review_token(token: str, *, now: datetime | None = None) -> dict[str, str] | None:
    """Validate signature/expiry and return the opaque researcher/digest claims."""
    secret = _secret()
    try:
        encoded, supplied_signature = token.split(".", 1)
        expected = hmac.new(secret.encode(), encoded.encode(), hashlib.sha256).digest()
        actual = base64.urlsafe_b64decode(supplied_signature + "=" * (-len(supplied_signature) % 4))
        if not secret or not hmac.compare_digest(actual, expected):
            return None
        payload = json.loads(base64.urlsafe_b64decode(encoded + "=" * (-len(encoded) % 4)).decode())
        current_timestamp = int((now or datetime.now(timezone.utc)).timestamp())
        if int(payload["expires_at"]) < current_timestamp:
            return None
        researcher_id = str(payload["researcher_id"])
        digest_key = str(payload["digest_key"])
        if not researcher_id or not digest_key:
            return None
        return {"researcher_id": researcher_id, "digest_key": digest_key}
    except (ValueError, KeyError, TypeError, json.JSONDecodeError):
        return None
