"""FastAPI exception handlers mapping typed errors to HTTP status codes."""

from __future__ import annotations

import logging

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from med_research.biomed.errors import BiomedicalStoreNotReadyError
from med_research.biomed.store_readiness import BIOMED_STORE_INIT_HINT
from med_research.exceptions import (
    ConfigurationError,
    DataValidationError,
    ExternalAPIError,
    MedResearchError,
    ModuleNotAvailableError,
)
from med_research.web.models.universal import BiomedicalStoreStateView

logger = logging.getLogger(__name__)


def _error_response(status_code: int, exc: Exception) -> JSONResponse:
    if status_code >= 500:
        logger.exception("Unhandled application error", exc_info=exc)
        detail = "An internal server error occurred."
    else:
        detail = str(exc)
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


async def biomedical_store_not_ready_handler(
    _request: Request, exc: BiomedicalStoreNotReadyError
) -> JSONResponse:
    hint = str(exc) or BIOMED_STORE_INIT_HINT
    return JSONResponse(
        status_code=503,
        content={
            "detail": hint,
            "error_type": type(exc).__name__,
            "store_state": BiomedicalStoreStateView(
                status="uninitialized",
                initialization_hint=hint,
            ).model_dump(),
        },
    )


def register_error_handlers(app: FastAPI) -> None:
    """Register typed exception handlers on a FastAPI application."""
    app.add_exception_handler(RequestValidationError, request_validation_error_handler)  # type: ignore[arg-type]
    app.add_exception_handler(ExternalAPIError, external_api_error_handler)  # type: ignore[arg-type]
    app.add_exception_handler(DataValidationError, data_validation_error_handler)  # type: ignore[arg-type]
    app.add_exception_handler(ModuleNotAvailableError, module_not_available_handler)  # type: ignore[arg-type]
    app.add_exception_handler(ConfigurationError, configuration_error_handler)  # type: ignore[arg-type]
    app.add_exception_handler(MedResearchError, med_research_error_handler)  # type: ignore[arg-type]
    app.add_exception_handler(
        BiomedicalStoreNotReadyError,
        biomedical_store_not_ready_handler,  # type: ignore[arg-type]
    )
