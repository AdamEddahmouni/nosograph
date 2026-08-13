"""FastAPI exception handlers mapping typed errors to HTTP status codes."""

from __future__ import annotations

import logging

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from med_research.exceptions import (
    ConfigurationError,
    DataValidationError,
    ExternalAPIError,
    MedResearchError,
    ModuleNotAvailableError,
)
from med_research.web.config import DEBUG

logger = logging.getLogger(__name__)


def _error_response(status_code: int, exc: Exception) -> JSONResponse:
    detail = str(exc) if DEBUG or status_code < 500 else "An internal server error occurred."
    if status_code >= 500 and not DEBUG:
        logger.exception("Unhandled application error", exc_info=exc)
    return JSONResponse(
        status_code=status_code,
        content={"detail": detail, "error_type": type(exc).__name__},
    )


async def request_validation_error_handler(
    _request: Request, exc: RequestValidationError
) -> JSONResponse:
    return JSONResponse(
        status_code=422,
        content={"detail": exc.errors(), "error_type": "ValidationError"},
    )


async def external_api_error_handler(_request: Request, exc: ExternalAPIError) -> JSONResponse:
    return _error_response(502, exc)


async def data_validation_error_handler(
    _request: Request, exc: DataValidationError
) -> JSONResponse:
    return _error_response(422, exc)


async def module_not_available_handler(
    _request: Request, exc: ModuleNotAvailableError
) -> JSONResponse:
    return _error_response(409, exc)


async def configuration_error_handler(_request: Request, exc: ConfigurationError) -> JSONResponse:
    return _error_response(503, exc)


async def med_research_error_handler(_request: Request, exc: MedResearchError) -> JSONResponse:
    return _error_response(500, exc)


def register_error_handlers(app: FastAPI) -> None:
    """Register typed exception handlers on a FastAPI application."""
    app.add_exception_handler(RequestValidationError, request_validation_error_handler)  # type: ignore[arg-type]
    app.add_exception_handler(ExternalAPIError, external_api_error_handler)  # type: ignore[arg-type]
    app.add_exception_handler(DataValidationError, data_validation_error_handler)  # type: ignore[arg-type]
    app.add_exception_handler(ModuleNotAvailableError, module_not_available_handler)  # type: ignore[arg-type]
    app.add_exception_handler(ConfigurationError, configuration_error_handler)  # type: ignore[arg-type]
    app.add_exception_handler(MedResearchError, med_research_error_handler)  # type: ignore[arg-type]
