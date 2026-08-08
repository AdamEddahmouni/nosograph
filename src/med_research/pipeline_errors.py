"""Pipeline error handling and CLI exit code constants.

Standalone helper for mapping pipeline exceptions to process exit codes.
Lane 1 CLI unification imports this module; it is not wired into cli.py yet.
"""

from __future__ import annotations

import logging
from typing import Optional

from med_research.exceptions import (
    ConfigurationError,
    MedResearchError,
    ModuleNotAvailableError,
    PipelineExecutionError,
)

# CLI exit codes
EXIT_RUNTIME = 1
EXIT_CONFIG = 2
EXIT_COVERAGE_BLOCKED = 3


def pipeline_exit_code(exc: BaseException) -> int:
    """Map an exception to a CLI exit code."""
    if isinstance(exc, ModuleNotAvailableError):
        return EXIT_COVERAGE_BLOCKED
    if isinstance(exc, ConfigurationError):
        return EXIT_CONFIG
    if isinstance(exc, (PipelineExecutionError, MedResearchError)):
        return EXIT_RUNTIME
    return EXIT_RUNTIME


def handle_pipeline_error(
    exc: BaseException,
    *,
    logger: Optional[logging.Logger] = None,
    context: str = "",
) -> int:
    """Log a user-facing pipeline error and return the appropriate exit code."""
    log = logger or logging.getLogger(__name__)
    prefix = f"{context}: " if context else ""

    if isinstance(exc, ModuleNotAvailableError):
        log.error("%sModule unavailable — %s", prefix, exc)
        return EXIT_COVERAGE_BLOCKED
    if isinstance(exc, ConfigurationError):
        log.error("%sConfiguration error — %s", prefix, exc)
        return EXIT_CONFIG
    if isinstance(exc, PipelineExecutionError):
        log.error("%sPipeline failed — %s", prefix, exc)
        return EXIT_RUNTIME
    if isinstance(exc, MedResearchError):
        log.error("%s%s", prefix, exc)
        return EXIT_RUNTIME

    log.error("%sUnexpected error — %s", prefix, exc)
    return EXIT_RUNTIME
