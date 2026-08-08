import json
import logging
from collections.abc import Callable
from typing import TypeVar

from med_research.rate_limiter import backoff_sleep

logger = logging.getLogger(__name__)

T = TypeVar("T")


class MedResearchError(Exception):
    """Base exception for all medical research platform errors."""


class ConfigurationError(MedResearchError):
    """Configuration missing or invalid."""


class DataValidationError(MedResearchError):
    """Data failed schema validation or integrity check."""


class MissingDataError(DataValidationError, FileNotFoundError):
    """Required data file or field is missing.

    Also derives from ``FileNotFoundError`` so existing callers that
    gracefully degrade on missing files keep working unchanged.  The
    custom ``__str__`` keeps the human-readable message (OSError would
    otherwise render ``[Errno None] ...`` when a filename is attached).
    """

    def __str__(self) -> str:
        if self.args:
            return str(self.args[0])
        return "Required data file or field is missing"


class SchemaValidationError(DataValidationError, ValueError):
    """Data does not match expected schema.

    Also derives from ``ValueError`` (the base of both
    ``json.JSONDecodeError`` and pydantic's ``ValidationError``) so
    existing tolerant catch sites keep working unchanged.
    """


class CacheCorruptionError(MedResearchError):
    """Cached data is corrupt or incompatible."""


class ExternalAPIError(MedResearchError):
    """An external API call failed."""


class APITimeoutError(ExternalAPIError):
    """External API request timed out."""


class APIQuotaError(ExternalAPIError):
    """External API quota exceeded or rate limited."""

    def __init__(
        self,
        message: str = "",
        *,
        retry_after_seconds: float | None = None,
    ) -> None:
        super().__init__(message)
        self.retry_after_seconds = retry_after_seconds


class APIParseError(ExternalAPIError):
    """Failed to parse response from external API."""


class PipelineExecutionError(MedResearchError):
    """A pipeline module failed during execution."""


class ModuleNotAvailableError(PipelineExecutionError):
    """An optional pipeline module or dependency is not available."""


def classify_api_error(exc: BaseException, source: str = "") -> ExternalAPIError:
    """Map a network or parse exception to a typed :class:`ExternalAPIError`."""
    prefix = f"{source}: " if source else ""

    if isinstance(exc, ExternalAPIError):
        return exc

    if isinstance(exc, json.JSONDecodeError):
        return APIParseError(f"{prefix}{exc}")

    try:
        import requests

        if isinstance(exc, requests.exceptions.Timeout):
            return APITimeoutError(f"{prefix}{exc}")
        if isinstance(exc, requests.exceptions.HTTPError):
            response = exc.response
            if response is not None and response.status_code in (429, 503):
                from med_research.rate_limiter import parse_retry_after

                retry_after = parse_retry_after(response.headers.get("Retry-After"))
                return APIQuotaError(f"{prefix}{exc}", retry_after_seconds=retry_after)
            return ExternalAPIError(f"{prefix}{exc}")
        if isinstance(exc, requests.exceptions.ConnectionError):
            return APITimeoutError(f"{prefix}{exc}")
        if isinstance(exc, requests.exceptions.RequestException):
            return ExternalAPIError(f"{prefix}{exc}")
    except ImportError:
        pass

    import urllib.error

    if isinstance(exc, urllib.error.HTTPError):
        if exc.code in (429, 503):
            from med_research.rate_limiter import parse_retry_after

            retry_after = parse_retry_after(exc.headers.get("Retry-After"))
            return APIQuotaError(f"{prefix}{exc}", retry_after_seconds=retry_after)
        return ExternalAPIError(f"{prefix}{exc}")

    if isinstance(exc, urllib.error.URLError):
        reason = exc.reason
        if isinstance(reason, TimeoutError) or "timed out" in str(exc).lower():
            return APITimeoutError(f"{prefix}{exc}")
        return ExternalAPIError(f"{prefix}{exc}")

    if isinstance(exc, TimeoutError):
        return APITimeoutError(f"{prefix}{exc}")

    return ExternalAPIError(f"{prefix}{exc}")


def raise_api_error(exc: BaseException, source: str = "") -> None:
    """Re-raise *exc* as a typed :class:`ExternalAPIError`."""
    raise classify_api_error(exc, source) from exc


def retry_with_backoff(
    func: Callable[[], T],
    *,
    max_attempts: int = 3,
    source: str = "",
) -> T:
    """Call *func*, retrying transient timeout/quota errors with backoff."""
    last_error: ExternalAPIError | None = None
    label = source or "API call"

    for attempt in range(max_attempts):
        try:
            return func()
        except (KeyboardInterrupt, SystemExit):
            raise
        except ExternalAPIError as exc:
            err = exc
        except BaseException as exc:
            err = classify_api_error(exc, source)

        if isinstance(err, (APITimeoutError, APIQuotaError)) and attempt < max_attempts - 1:
            retry_after = (
                err.retry_after_seconds
                if isinstance(err, APIQuotaError)
                else None
            )
            logger.info(
                "Retrying %s after %s (attempt %d/%d)",
                label,
                err,
                attempt + 1,
                max_attempts,
            )
            backoff_sleep(attempt, retry_after=retry_after)
            last_error = err
            continue

        raise err

    if last_error is not None:
        raise last_error
    raise RuntimeError(f"retry_with_backoff exhausted attempts for {label}")
