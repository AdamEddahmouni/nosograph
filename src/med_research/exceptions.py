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
