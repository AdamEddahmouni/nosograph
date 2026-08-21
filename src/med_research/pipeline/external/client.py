"""Base HTTP request helper for external biomedical APIs with rate limiting and retries."""

from __future__ import annotations

import json
import logging
import urllib.error
import urllib.parse
import urllib.request
from typing import Any, Dict, Optional

from med_research.rate_limiter import backoff_sleep, parse_retry_after

logger = logging.getLogger(__name__)

DEFAULT_HEADERS = {
    "User-Agent": "MedicalResearchPlatform/2.0 (Computational Research Platform)",
    "Accept": "application/json",
}


def fetch_json(
    url: str,
    params: Optional[Dict[str, Any]] = None,
    body: Optional[Dict[str, Any]] = None,
    headers: Optional[Dict[str, str]] = None,
    timeout: int = 30,
    retries: int = 3,
) -> Any:
    """Fetch JSON response from a remote URL with backoff and retries.

    Args:
        url: Destination API URL.
        params: Query string parameters.
        body: Data payload (sends POST request if provided).
        headers: Optional extra HTTP headers.
        timeout: Socket timeout in seconds.
        retries: Number of retry attempts on failure.

    Returns:
        Parsed JSON response payload (dict or list).
    """
    req_headers = {**DEFAULT_HEADERS, **(headers or {})}

    if params:
        query_str = urllib.parse.urlencode(params)
        url = f"{url}?{query_str}" if "?" not in url else f"{url}&{query_str}"

    encoded_data: Optional[bytes] = None
    if body is not None:
        encoded_data = json.dumps(body).encode("utf-8")
        req_headers["Content-Type"] = "application/json"

    for attempt in range(retries):
        try:
            req = urllib.request.Request(
                url,
                data=encoded_data,
                headers=req_headers,
                method="POST" if body is not None else "GET",
            )
            with urllib.request.urlopen(req, timeout=timeout) as resp:  # nosec B310 - curated HTTPS APIs
                resp_data = resp.read().decode("utf-8")
                return json.loads(resp_data)

        except urllib.error.HTTPError as err:
            logger.warning(
                "HTTP %s error fetching %s (attempt %d/%d): %s",
                err.code,
                url,
                attempt + 1,
                retries,
                err.reason,
            )
            if err.code in (429, 502, 503, 504) and attempt < retries - 1:
                retry_after = parse_retry_after(err.headers.get("Retry-After"))
                backoff_sleep(attempt, retry_after=retry_after)
                continue
            raise RuntimeError(f"HTTP {err.code} fetching {url}: {err.reason}") from err

        except (urllib.error.URLError, TimeoutError, OSError) as err:
            logger.warning(
                "Network error fetching %s (attempt %d/%d): %s",
                url,
                attempt + 1,
                retries,
                err,
            )
            if attempt < retries - 1:
                backoff_sleep(attempt)
                continue
            raise RuntimeError(f"Network error fetching {url}: {err}") from err

    raise RuntimeError(f"Failed to fetch {url} after {retries} retries.")
