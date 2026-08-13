"""API key helpers shared by HTTP middleware and WebSocket routes."""

from __future__ import annotations

import os
from collections.abc import Mapping

API_KEY = os.environ.get("API_KEY", "")


def is_api_key_required() -> bool:
    return bool(API_KEY)


def validate_api_key(provided: str | None) -> bool:
    if not API_KEY:
        return True
    return bool(provided) and provided == API_KEY


def extract_api_key_from_headers(headers: Mapping[str, str]) -> str:
    return headers.get("X-API-Key") or headers.get("x-api-key") or ""


def extract_api_key_from_query(query_params: Mapping[str, str]) -> str:
    return query_params.get("api_key") or ""
