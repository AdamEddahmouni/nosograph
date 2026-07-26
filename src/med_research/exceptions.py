class MedResearchError(Exception):
    """Base exception for all medical research platform errors."""


class ConfigurationError(MedResearchError):
    """Configuration missing or invalid."""


class DataValidationError(MedResearchError):
    """Data failed schema validation or integrity check."""


class MissingDataError(DataValidationError):
    """Required data file or field is missing."""


class SchemaValidationError(DataValidationError):
    """Data does not match expected schema."""


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
