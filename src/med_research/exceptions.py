import json


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
                return APIQuotaError(f"{prefix}{exc}")
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
            return APIQuotaError(f"{prefix}{exc}")
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
