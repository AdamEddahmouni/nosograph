class BiomedicalError(Exception):
    """Base exception for all biomedical canonical store errors."""


class BiomedicalValidationError(BiomedicalError):
    """Raised when domain validation or CURIE formatting fails."""


class SnapshotConflictError(BiomedicalError):
    """Raised when resource snapshot version or checksum conflicts occur."""


class RunTransitionError(BiomedicalError):
    """Raised when an invalid ResearchRun status state transition is attempted."""


class EntityNotFoundError(BiomedicalError):
    """Raised when an entity CURIE or UUID cannot be found."""
